import os
os.environ["OPENCV_LOG_LEVEL"] = "OFF"  # Suppress FFmpeg warnings
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"  # Suppress FFmpeg overread warnings

import cv2
import time
import requests
import threading
import queue
import logging
import argparse
from difflib import SequenceMatcher
from anpr_yolo_easyocr import recognize_plate_from_frame

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('parking_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

API_DETECT = 'http://localhost:5000/api/detect'
API_EXIT = 'http://localhost:5000/api/exit-vehicle'
API_HEALTH = 'http://localhost:5000/api/health'

# Confidence and deduplication settings
REQUIRED_DETECTIONS = 1  # Fast detection (1 high-confidence detection)
DETECTION_TIME_WINDOW = 10  # seconds
SIMILARITY_THRESHOLD = 0.85
DUPLICATE_IGNORE_SECONDS = 20
GLOBAL_DETECTION_COOLDOWN = 3  # Minimum seconds between ANY detections

# Performance tuning
FRAME_QUEUE_MAX = 3
PROCESS_EVERY_N = 2
DISPLAY_UPDATE_EVERY = 2

# IP Webcam configuration (Change to your IP camera address)
IP_WEBCAM_URL = "http://10.109.18.31:8080/video"  # Update this IP address
LOCAL_CAMERA_ID = 0  # Fallback to local camera (0=default webcam)

# Plate detection tracking
plate_detections = {}  # plate -> [(timestamp, confidence)]
processed_plates = {}  # plate -> last_api_time
last_global_detection_time = 0  # Track last detection time globally

def string_similarity(a, b):
    """Calculate string similarity (0-1)"""
    return SequenceMatcher(None, a, b).ratio()  



def check_api_health():
    """Check if Flask API is running"""
    try:
        resp = requests.get('http://localhost:5000/api/health', timeout=2)
        if resp.status_code == 200:
            logger.info('✓ Flask server is healthy')
            return True
    except requests.exceptions.ConnectionError:
        logger.error('✗ Cannot connect to Flask server at localhost:5000')
        return False
    except Exception as e:
        logger.error(f'✗ Flask server check failed: {e}')
        return False

def open_ip_webcam():
    """Open IP webcam stream with retry logic, fallback to local camera"""
    # Try IP webcam first
    backends = [cv2.CAP_FFMPEG, cv2.CAP_ANY]
    
    for api_idx, api in enumerate(backends):
        try:
            cap = cv2.VideoCapture(IP_WEBCAM_URL, api)
        except Exception:
            cap = None

        if cap is None:
            continue
        
        time.sleep(0.5)
        
        if cap.isOpened():
            ret, test_frame = cap.read()
            if ret and test_frame is not None:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                logger.info(f"✓ IP Webcam connected: {width}x{height} @ {fps:.1f} FPS")
                return cap
            else:
                logger.warning(f"Cannot read frames with backend {api_idx}")
        
        try:
            cap.release()
        except Exception:
            pass

    logger.warning(f"✗ Failed to connect to IP webcam: {IP_WEBCAM_URL}")
    logger.info(f"Attempting to use local camera (ID: {LOCAL_CAMERA_ID})...")
    
    # Fallback to local camera
    try:
        cap = cv2.VideoCapture(LOCAL_CAMERA_ID)
        time.sleep(0.5)
        
        if cap.isOpened():
            ret, test_frame = cap.read()
            if ret and test_frame is not None:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                logger.info(f"✓ Local camera connected: {width}x{height} @ {fps:.1f} FPS")
                return cap
        cap.release()
    except Exception as e:
        logger.warning(f"Local camera failed: {e}")
    
    logger.error(f"✗ No camera available (IP: {IP_WEBCAM_URL}, Local: {LOCAL_CAMERA_ID})")
    return None

def should_process_plate(plate):
    """
    Confidence voting system:
    - Require N detections within time window
    - Avoid duplicate API calls
    """
    now = time.time()
    
    # Check for similar plate
    existing_plate = None
    max_similarity = 0
    
    for stored_plate in plate_detections.keys():
        similarity = string_similarity(plate, stored_plate)
        if similarity > SIMILARITY_THRESHOLD and similarity > max_similarity:
            max_similarity = similarity
            existing_plate = stored_plate
    
    target_plate = existing_plate if existing_plate else plate
    
    if target_plate not in plate_detections:
        plate_detections[target_plate] = []
    
    # Add detection with confidence
    plate_detections[target_plate].append(now)
    
    # Keep only recent detections
    plate_detections[target_plate] = [
        ts for ts in plate_detections[target_plate]
        if now - ts <= DETECTION_TIME_WINDOW
    ]
    
    detection_count = len(plate_detections[target_plate])
    
    # Check if we have enough confirmations
    if detection_count < REQUIRED_DETECTIONS:
        logger.debug(f'[CONFIDENCE] {target_plate}: {detection_count}/{REQUIRED_DETECTIONS}')
        return False, target_plate
    
    # Check if recently processed
    if target_plate in processed_plates:
        time_since_last = now - processed_plates[target_plate]
        if time_since_last < DUPLICATE_IGNORE_SECONDS:
            logger.debug(f'[DUPLICATE] {target_plate} processed {time_since_last:.0f}s ago')
            return False, target_plate
    
    # Check global cooldown (prevent rapid detections of different plates)
    global last_global_detection_time
    time_since_last_global = now - last_global_detection_time
    if time_since_last_global < GLOBAL_DETECTION_COOLDOWN:
        logger.debug(f'[COOLDOWN] Global cooldown active ({time_since_last_global:.1f}s < {GLOBAL_DETECTION_COOLDOWN}s)')
        return False, target_plate
    
    logger.info(f'[CONFIDENCE] {target_plate} confirmed ({detection_count} detections)')
    processed_plates[target_plate] = now
    last_global_detection_time = now
    plate_detections[target_plate] = []
    
    return True, target_plate

def send_to_api(plate_text):
    """Send detected plate to Flask API"""
    try:
        logger.info(f'[API] Sending plate: {plate_text}')
        resp = requests.post(API_DETECT, data={'plate': plate_text}, timeout=5)
        
        if resp.status_code == 200:
            result = resp.json()
            if result.get('success'):
                action = result.get('action', 'UNKNOWN').upper()
                message = result.get('message', 'Success')
                logger.info(f'[✓ {action}] {plate_text}: {message}')
                # Mark as processed to prevent re-sending
                processed_plates[plate_text] = time.time()
                return True
            else:
                error = result.get('error', 'Unknown error')
                logger.warning(f'[✗ API] {plate_text}: {error}')
                return False
        
        elif resp.status_code == 409:
            # 409 = Vehicle already parked (vehicle is exiting!)
            result = resp.json()
            slot_num = result.get('slot_number', '?')
            logger.info(f'[EXIT-DETECTED] {plate_text} leaving from slot {slot_num}')
            
            # Call exit endpoint to free the slot
            try:
                exit_resp = requests.post(API_EXIT, data={'plate': plate_text}, timeout=5)
                if exit_resp.status_code == 200:
                    exit_result = exit_resp.json()
                    goodbye_msg = exit_result.get('goodbye_message', 'Thank you. Visit again..Bye')
                    logger.info(f'[✓ EXIT] {plate_text}: {goodbye_msg}')
                else:
                    logger.warning(f'[✗ EXIT] HTTP {exit_resp.status_code}')
            except Exception as e:
                logger.error(f'[✗ EXIT-API] Error: {e}')
            
            # Mark as processed
            processed_plates[plate_text] = time.time()
            return True  # Treat as handled
        
        else:
            logger.error(f'[✗ API] HTTP {resp.status_code}: {resp.text}')
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f'[✗ API] Timeout sending {plate_text}')
        return False
    except requests.exceptions.ConnectionError:
        logger.error(f'[✗ API] Cannot connect to Flask API')
        return False
    except Exception as e:
        logger.error(f'[✗ API] Error: {e}')
        return False

def _worker_process(q: queue.Queue, stop_event: threading.Event):
    """Worker thread for frame processing"""
    processed_count = 0
    
    while not stop_event.is_set():
        try:
            frame = q.get(timeout=0.5)
        except queue.Empty:
            continue
        
        processed_count += 1
        if processed_count % PROCESS_EVERY_N != 0:
            continue
        
        # Simple plate detection (single frame, no aggregation overhead)
        plate = recognize_plate_from_frame(frame)
        if not plate:
            continue

        plate = plate.upper().strip()
        logger.info(f"[DETECT] Plate: {plate}")
        
        # Confidence voting
        should_send, confirmed_plate = should_process_plate(plate)
        if not should_send:
            continue
        
        # Send to API
        send_to_api(confirmed_plate)

def display_frame_info(frame, frame_count, last_plate=None):
    """Display frame with detection info"""
    h, w = frame.shape[:2]
    
    # Semi-transparent overlay
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (w-10, 140), (20, 100, 50), -1)
    cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
    
    # Text info
    cv2.putText(frame, f'Frame: {frame_count}', (20, 40),
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.putText(frame, 'Status: Monitoring', (20, 75),
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    
    if last_plate:
        cv2.putText(frame, f'Last: {last_plate}', (20, 110),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
    
    cv2.putText(frame, 'Press Q to quit, S to save', (w-400, h-20),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

def ip_webcam_detection(show_window=True):
    """Main IP webcam detection loop"""
    
    logger.info('Checking Flask API health...')
    if not check_api_health():
        logger.error('Flask API not responding. Start with: python slot.py')
        return False
    
    logger.info(f'Connecting to IP Webcam: {IP_WEBCAM_URL}')
    cap = open_ip_webcam()
    if not cap:
        logger.error('Failed to connect to IP webcam')
        return False

    # Initialize worker thread
    q = queue.Queue(maxsize=FRAME_QUEUE_MAX)
    stop_event = threading.Event()
    worker = threading.Thread(target=_worker_process, args=(q, stop_event), daemon=True)
    worker.start()

    logger.info("="*70)
    logger.info("Smart Parking - IP Webcam ANPR Detection (Multi-Plate)")
    logger.info("="*70)
    logger.info(f"Source: {IP_WEBCAM_URL}")
    logger.info(f"Confidence: {REQUIRED_DETECTIONS} detections within {DETECTION_TIME_WINDOW}s")
    logger.info(f"Dedup: {DUPLICATE_IGNORE_SECONDS}s between API calls")
    logger.info("Press Q to quit, S to save frame")
    logger.info("="*70 + "\n")
    
    frame_count = 0
    disp_counter = 0
    last_detected_plate = None
    last_detection_time = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.warning('[WEBCAM] No frame. Reconnecting...')
                cap.release()
                time.sleep(2)
                cap = open_ip_webcam()
                if not cap:
                    logger.error('Reconnection failed')
                    break
                continue

            frame_count += 1
            
            # Add to processing queue
            if not q.full():
                q.put(frame.copy())
            else:
                try:
                    q.get_nowait()
                    q.put(frame.copy())
                except:
                    pass

            # Display frame
            if show_window:
                disp_counter += 1
                if disp_counter % DISPLAY_UPDATE_EVERY == 0:
                    display_frame_info(frame, frame_count, last_detected_plate)
                    cv2.imshow('Smart Parking - Detection', frame)
                    
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        logger.info("[USER] Quit requested")
                        break
                    elif key == ord('s'):
                        filename = f"frame_{frame_count}_{int(time.time())}.jpg"
                        cv2.imwrite(filename, frame)
                        logger.info(f"[USER] Saved: {filename}")
    
    except KeyboardInterrupt:
        logger.info("[SYSTEM] Keyboard interrupt")
    except Exception as e:
        logger.error(f'[WEBCAM] Error: {e}', exc_info=True)
        return False
    
    finally:
        logger.info("[SHUTDOWN] Cleaning up...")
        stop_event.set()
        worker.join(timeout=1)
        try:
            cap.release()
        except:
            pass
        cv2.destroyAllWindows()
        logger.info("[SHUTDOWN] Complete")
    
    return True


def capture_video(show_window=True):
    """Continuous video capture with plate detection and slot allocation."""
    logger.info('Checking Flask API health...')
    if not check_api_health():
        logger.error('Flask API not responding. Start with: python slot.py')
        return False

    logger.info(f'Connecting to camera for video capture: {IP_WEBCAM_URL}')
    cap = open_ip_webcam()
    if not cap:
        logger.error('Failed to open camera')
        return False

    logger.info("="*70)
    logger.info("Smart Parking - Video Mode Detection")
    logger.info("="*70)
    logger.info(f"Source: {IP_WEBCAM_URL}")
    logger.info(f"Dedup: {DUPLICATE_IGNORE_SECONDS}s between detections")
    logger.info("Press Ctrl+C to stop")
    logger.info("="*70 + "\n")
    
    try:
        frame_count = 0
        last_detected_plate = None
        
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.warning('[VIDEO] No frame. Reconnecting...')
                cap.release()
                time.sleep(2)
                cap = open_ip_webcam()
                if not cap:
                    logger.error('Reconnection failed')
                    break
                continue

            frame_count += 1
            
            # Process every 2nd frame for speed
            if frame_count % PROCESS_EVERY_N != 0:
                if show_window:
                    cv2.imshow('Smart Parking - Video', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        logger.info("[USER] Quit requested")
                        break
                continue

            # Simple single-frame detection (no aggregation overhead)
            plate = recognize_plate_from_frame(frame)
            
            if not plate:
                if show_window:
                    cv2.imshow('Smart Parking - Video', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        logger.info("[USER] Quit requested")
                        break
                continue

            plate = plate.upper().strip()
            logger.info(f"[DETECT] Plate: {plate}")
            last_detected_plate = plate
            
            # Confidence voting and dedup check
            should_send, confirmed_plate = should_process_plate(plate)
            if not should_send:
                if show_window:
                    cv2.imshow('Smart Parking - Video', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        logger.info("[USER] Quit requested")
                        break
                continue
            
            # Send to API and allocate slot
            send_to_api(confirmed_plate)
            
            # Show detection success
            if show_window:
                overlay = frame.copy()
                h, w = frame.shape[:2]
                cv2.rectangle(overlay, (10, 10), (w-10, 100), (0, 255, 0), -1)
                cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
                cv2.putText(frame, f'✓ DETECTED: {confirmed_plate}', (20, 50),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2)
                cv2.imshow('Smart Parking - Video', frame)
                cv2.waitKey(2000)  # Show for 2 seconds
    
    except KeyboardInterrupt:
        logger.info("[SYSTEM] Keyboard interrupt")
    except Exception as e:
        logger.error(f'[VIDEO] Error: {e}', exc_info=True)
        return False
    
    finally:
        logger.info("[SHUTDOWN] Cleaning up...")
        try:
            cap.release()
        except:
            pass
        cv2.destroyAllWindows()
        logger.info("[SHUTDOWN] Complete")
    
    return True

def main():
    global IP_WEBCAM_URL, LOCAL_CAMERA_ID
    
    parser = argparse.ArgumentParser(description='Smart Parking - IP Webcam ANPR')
    parser.add_argument('--url', type=str, default=IP_WEBCAM_URL,
                       help='IP Webcam URL (default: %(default)s)')
    parser.add_argument('--video', action='store_true',
                       help='Run in video mode (continuous detection)')
    parser.add_argument('--local', type=int, default=None,
                       help='Use local camera ID instead of IP webcam (e.g., 0 for default, 1 for external)')
    parser.add_argument('--no-display', action='store_true',
                       help='Run without display window')
    parser.add_argument('--photo', action='store_true',
                       help='Capture a single photo and exit')
    parser.add_argument('--dedup', type=int, default=None,
                       help='Seconds to ignore duplicate plates (overrides default)')
    
    args = parser.parse_args()
    
    # Override IP webcam URL if provided
    if args.url != IP_WEBCAM_URL:
        IP_WEBCAM_URL = args.url
    
    # Use local camera if specified
    if args.local is not None:
        LOCAL_CAMERA_ID = args.local
        logger.info(f"Using local camera ID: {LOCAL_CAMERA_ID}")

    # Override duplicate-ignore seconds if provided
    if args.dedup is not None:
        global DUPLICATE_IGNORE_SECONDS
        DUPLICATE_IGNORE_SECONDS = int(args.dedup)
        logger.info(f"Dedup interval set to: {DUPLICATE_IGNORE_SECONDS}s")
    
    if args.photo:
        success = capture_video(show_window=not args.no_display)  # Photo mode redirects to video
    elif args.video:
        success = capture_video(show_window=not args.no_display)
    else:
        success = ip_webcam_detection(show_window=not args.no_display)
    
    if success:
        logger.info("✓ Detection completed successfully")
    else:
        logger.error("✗ Detection failed")

if __name__ == '__main__':
    print("\n" + "="*70)
    print("Smart Parking System - IP Webcam ANPR (Enhanced)")
    print("="*70)
    print("Features:")
    print("  • Multi-plate detection per frame")
    print("  • Improved character recognition for confusing pairs")
    print("  • Faster processing (every 2nd frame)")
    print("  • Confidence-based filtering")
    print("  • Duplicate detection prevention")
    print("  • IP camera + Local camera fallback support")
    print("")
    print("Usage:")
    print("  python camera_capture.py                          # Continuous detection (default)")
    print("  python camera_capture.py --video                  # Explicit video mode")
    print("  python camera_capture.py --local 0                # Use local camera")
    print("  python camera_capture.py --local 0 --video        # Local camera, video mode")
    print("  python camera_capture.py --video --no-display     # Headless video mode")
    print("")
    print("Controls (when display enabled):")
    print("  • Press Q to quit")
    print("  • Press S to save current frame")
    print("="*70 + "\n")
    
    main()