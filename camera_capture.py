import cv2
import time
import requests
import threading
import queue
import logging
from difflib import SequenceMatcher
from anpr_yolo_easyocr import recognize_plate_from_frame

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_DETECT = 'http://localhost:5000/api/detect'
API_HEALTH = 'http://localhost:5000/api/health'

# Store detected plates with timestamps for confidence voting
plate_detections = {}  # plate -> [timestamps]
DUPLICATE_IGNORE_SECONDS = 25  # Ignore same plate within 25 seconds
REQUIRED_DETECTIONS = 3  # Require 3 confirmations (increased for accuracy)
DETECTION_TIME_WINDOW = 6  # Within 6 seconds
SIMILARITY_THRESHOLD = 0.85  # 85% string similarity to consider as same plate

FRAME_QUEUE_MAX = 2
PROCESS_EVERY_N = 3
DISPLAY_UPDATE_EVERY = 3

def check_api_health():
    """Check if Flask API is running"""
    try:
        resp = requests.get(API_HEALTH, timeout=2)
        if resp.status_code == 200:
            logger.info('✓ Flask API is healthy')
            return True
    except Exception as e:
        logger.error(f'✗ Flask API health check failed: {e}')
        return False

def string_similarity(a: str, b: str) -> float:
    """Calculate similarity between two strings (0-1)"""
    return SequenceMatcher(None, a, b).ratio()

def _open_capture(source="http://10.16.120.123:8080/video"):
    """
    Try multiple backends depending on source type.
    """
    is_url = isinstance(source, str)
    backends = []

    if is_url:
        for api in (getattr(cv2, 'CAP_FFMPEG', cv2.CAP_ANY), cv2.CAP_ANY):
            backends.append(api)
    else:
        for api in (getattr(cv2, 'CAP_DSHOW', cv2.CAP_ANY),
                    getattr(cv2, 'CAP_MSMF', cv2.CAP_ANY),
                    cv2.CAP_ANY):
            backends.append(api)

    for api in backends:
        try:
            cap = cv2.VideoCapture(source, api) if api is not None else cv2.VideoCapture(source)
        except Exception:
            cap = None

        if cap is None:
            continue
        time.sleep(0.2)
        if cap.isOpened():
            try:
                if not is_url:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 720)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            except Exception:
                pass
            logger.info(f"✓ Camera opened successfully")
            return cap
        try:
            cap.release()
        except Exception:
            pass

    return None

def should_process_plate(plate):
    """
    Enhanced confidence voting:
    - Detect same plate N times within time window
    - Also detect similar plates (85%+ match)
    - Only then send to API
    """
    now = time.time()
    
    # Check for existing plate or similar plate
    existing_plate = None
    max_similarity = 0
    
    for stored_plate in plate_detections.keys():
        similarity = string_similarity(plate, stored_plate)
        if similarity > SIMILARITY_THRESHOLD and similarity > max_similarity:
            max_similarity = similarity
            existing_plate = stored_plate
    
    # Use existing plate if found, otherwise use new
    target_plate = existing_plate if existing_plate else plate
    
    if target_plate not in plate_detections:
        plate_detections[target_plate] = []
    
    # Add current detection
    plate_detections[target_plate].append((now, plate))
    
    # Remove old detections outside time window
    plate_detections[target_plate] = [
        (ts, p) for ts, p in plate_detections[target_plate]
        if now - ts <= DETECTION_TIME_WINDOW
    ]
    
    # Check if we have enough confirmations
    detection_count = len(plate_detections[target_plate])
    
    if detection_count < REQUIRED_DETECTIONS:
        logger.debug(f'[CONFIDENCE] Plate {target_plate} detected {detection_count}/{REQUIRED_DETECTIONS} times')
        return False, target_plate
    
    logger.info(f'[CONFIDENCE] Plate {target_plate} confirmed after {detection_count} detections')
    # Clear detections after confirmation
    plate_detections[target_plate] = []
    return True, target_plate

def _worker_process(q: queue.Queue, stop_event: threading.Event):
    """Worker thread that processes frames and handles plate detection"""
    processed_counter = 0
    
    while not stop_event.is_set():
        try:
            frame = q.get(timeout=0.5)
        except queue.Empty:
            continue
        
        processed_counter += 1
        if processed_counter % PROCESS_EVERY_N != 0:
            continue
        
        plate = recognize_plate_from_frame(frame)
        if not plate:
            continue

        plate = plate.upper().strip()
        logger.info(f"[DETECT] Plate detected: {plate}")
        
        # Confidence voting: require multiple detections
        should_send, confirmed_plate = should_process_plate(plate)
        if not should_send:
            continue
        
        # Send to API - let server decide if entry or exit
        try:
            logger.info(f'[API] Sending confirmed plate {confirmed_plate} to API...')
            resp = requests.post(API_DETECT, data={'plate': confirmed_plate}, timeout=5)
            j = resp.json()
            
            if j.get('success'):
                action = j.get('action', 'unknown').upper()
                
                if action == 'ENTRY':
                    slot_number = j.get('slot_number', 'N/A')
                    logger.info(f'[✓ ENTRY] Plate {confirmed_plate} -> Slot {slot_number}')
                    
                elif action == 'EXIT':
                    charge = j.get('charge', 'N/A')
                    duration = j.get('duration_hours', 'N/A')
                    slot_number = j.get('slot_number', 'N/A')
                    logger.info(f'[✓ EXIT] Plate {confirmed_plate} from Slot {slot_number} (Duration: {duration}h, Charge: ${charge})')
                else:
                    logger.info(f'[✓ {action}] {j.get("message", "")}')
            else:
                error = j.get('error', 'Unknown error')
                logger.warning(f'[✗ FAIL] API error for {confirmed_plate}: {error}')
                
        except requests.exceptions.ConnectionError:
            logger.error(f'[✗ API] Cannot connect to Flask API at localhost:5000')
        except requests.exceptions.Timeout:
            logger.error(f'[✗ API] Request timeout for plate {confirmed_plate}')
        except Exception as e:
            logger.error(f'[✗ API] Error for {confirmed_plate}: {e}')

def main_loop(source=0, show_window=True):
    """Main capture loop"""
    
    # Check if API is running before starting
    logger.info('Checking Flask API health...')
    if not check_api_health():
        logger.error('⚠️ Flask API is not responding. Please start the Flask server first.')
        logger.error('Run in another terminal: python slot.py')
        time.sleep(2)
    
    cap = _open_capture(source)
    if not cap:
        raise RuntimeError(f'Could not open capture source={source}')

    q = queue.Queue(maxsize=FRAME_QUEUE_MAX)
    stop_event = threading.Event()
    worker = threading.Thread(target=_worker_process, args=(q, stop_event), daemon=True)
    worker.start()

    logger.info("="*70)
    logger.info("Smart Parking - ANPR Camera Capture")
    logger.info("="*70)
    logger.info(f"Confidence System: Requires {REQUIRED_DETECTIONS} detections within {DETECTION_TIME_WINDOW}s")
    logger.info(f"Similarity Matching: {SIMILARITY_THRESHOLD*100:.0f}% threshold")
    logger.info(f"Duplicate Filter: {DUPLICATE_IGNORE_SECONDS}s between API calls")
    logger.info("Press 'q' to quit")
    logger.info("="*70)
    
    disp_counter = 0
    api_check_counter = 0
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.warning('[CAMERA] No frame received. Reconnecting...')
                cap.release()
                time.sleep(1.0)
                cap = _open_capture(source)
                if not cap:
                    time.sleep(2.0)
                    continue
                continue

            frame_count += 1
            
            if not q.full():
                q.put(frame.copy())
            else:
                try:
                    _ = q.get_nowait()
                    q.put(frame.copy())
                except Exception:
                    pass

            # Periodic API health check
            api_check_counter += 1
            if api_check_counter % 300 == 0:
                if not check_api_health():
                    logger.warning('⚠️ API connection lost!')
                api_check_counter = 0

            if show_window:
                disp_counter += 1
                if disp_counter % DISPLAY_UPDATE_EVERY == 0:
                    cv2.putText(frame, f'Frames: {frame_count}', (10, 30), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.imshow('Smart Parking - Camera Feed (Press Q to quit)', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        logger.info("[USER] Quit requested")
                        break
    except KeyboardInterrupt:
        logger.info("[SYSTEM] Keyboard interrupt received")
    finally:
        logger.info("[SHUTDOWN] Cleaning up...")
        stop_event.set()
        worker.join(timeout=1.0)
        try:
            cap.release()
        except Exception:
            pass
        cv2.destroyAllWindows()
        logger.info("[SHUTDOWN] Camera closed successfully")

if __name__ == '__main__':
    # Use IP camera stream URL
    main_loop(source="http://10.16.120.123:8080/video", show_window=True)