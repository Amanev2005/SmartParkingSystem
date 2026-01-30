#!/usr/bin/env python3
"""
Smart Parking System - Main Entry Point
Supports image and video processing with multi-plate detection
"""

import argparse
import cv2
import sys
import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from anpr_yolo_easyocr import (
        recognize_plate_from_frame,
        smart_plate_correction
    )
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure all dependencies are installed:")
    print("pip install opencv-python ultralytics easyocr numpy flask requests")
    sys.exit(1)

def process_single_image(image_path):
    """Process a single image for plate detection"""
    print(f"\n{'='*60}")
    print(f"Processing image: {image_path}")
    print(f"{'='*60}")
    
    image = cv2.imread(image_path)
    if image is None:
        print(f"✗ Error: Could not read image {image_path}")
        return
    
    plate = recognize_plate_from_frame(image)
    
    if plate:
        print(f"✓ Plate detected: {plate}")
        
        # Display result
        annotated = image.copy()
        h, w = annotated.shape[:2]
        
        # Add text overlay
        cv2.rectangle(annotated, (10, 10), (w-10, 100), (0, 200, 0), -1)
        cv2.putText(annotated, f'Plate: {plate}', 
                    (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 
                    1.5, (255, 255, 255), 2)
        
        cv2.imshow('Plate Detection Result', annotated)
        print("✓ Press any key to close...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print("✗ No plate detected")
        cv2.imshow('Original Image (No plate detected)', image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

def process_video_file(video_path, send_to_api=False):
    """
    Process video file and detect ALL plates
    """
    print(f"\n{'='*60}")
    print(f"Processing video file: {video_path}")
    print(f"{'='*60}")
    print("Detecting ALL plates in video...\n")
    
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"✗ Error: Cannot open video {video_path}")
        return False
    
    frame_count = 0
    all_detections = {}  # plate -> count
    unique_plates = set()
    process_count = 0
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Video FPS: {fps}, Processing every 2nd frame for speed\n")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # Process every 2nd frame for speed
            if frame_count % 2 != 0:
                continue
            
            process_count += 1
            
            # Detect plate
            plate = recognize_plate_from_frame(frame)
            
            if plate:
                unique_plates.add(plate)
                
                if plate not in all_detections:
                    all_detections[plate] = 0
                all_detections[plate] += 1
                
                print(f"[FRAME {frame_count}] ✓ Plate: {plate}")
                
                # Send to API if enabled
                if send_to_api:
                    try:
                        import requests
                        resp = requests.post(
                            'http://localhost:5000/api/detect',
                            data={'plate': plate},
                            timeout=5
                        )
                        
                        if resp.status_code == 200:
                            result = resp.json()
                            if result.get('success'):
                                action = result.get('action', 'UNKNOWN').upper()
                                slot = result.get('slot_number', 'N/A')
                                print(f"  → API [{action}] Slot: {slot}")
                            else:
                                error = result.get('error', 'Unknown error')
                                print(f"  → API Error: {error}")
                    except Exception as e:
                        print(f"  → API Error: {e}")
            
            if process_count % 50 == 0:
                print(f"[PROGRESS] Processed {frame_count} frames, Found {len(unique_plates)} unique plates")
    
    except Exception as e:
        print(f"✗ Video processing error: {e}")
        return False
    finally:
        cap.release()
    
    print(f"\n{'='*60}")
    print(f"✓ Video processing completed!")
    print(f"{'='*60}")
    print(f"Total frames processed: {frame_count}")
    print(f"Unique plates detected: {len(unique_plates)}")
    
    if unique_plates:
        print("\nPlates found:")
        for i, plate in enumerate(sorted(unique_plates), 1):
            print(f"  {i}. {plate}")
    
    print(f"{'='*60}\n")
    
    return True

def process_video_stream_with_api(video_source):
    """
    Stream video processing with API integration
    """
    print(f"\n{'='*60}")
    print("Starting real-time plate detection")
    print(f"{'='*60}\n")
    
    cap = cv2.VideoCapture(video_source)
    
    if not cap.isOpened():
        print(f"✗ Error: Cannot open video source: {video_source}")
        return False
    
    frame_count = 0
    detected_plates = set()
    detection_buffer = {}  # plate -> frame count
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("End of stream")
                break
            
            frame_count += 1
            
            # Process every 2nd frame
            if frame_count % 2 != 0:
                continue
            
            plate = recognize_plate_from_frame(frame)
            
            if plate:
                # Deduplicate - wait 30 frames between detections
                if plate in detection_buffer:
                    if frame_count - detection_buffer[plate] < 30:
                        continue
                
                detection_buffer[plate] = frame_count
                detected_plates.add(plate)
                
                print(f"[FRAME {frame_count}] ✓ Plate: {plate}")
                
                # Send to API
                try:
                    import requests
                    resp = requests.post(
                        'http://localhost:5000/api/detect',
                        data={'plate': plate},
                        timeout=5
                    )
                    
                    if resp.status_code == 200:
                        result = resp.json()
                        if result.get('success'):
                            action = result.get('action', 'UNKNOWN').upper()
                            slot = result.get('slot_number', 'N/A')
                            print(f"  → API [{action}] Slot: {slot}")
                        else:
                            error = result.get('error', 'Unknown error')
                            print(f"  → API Error: {error}")
                except Exception as e:
                    print(f"  → API Error: {e}")
            
            if frame_count % 100 == 0:
                print(f"[PROGRESS] {frame_count} frames, {len(detected_plates)} unique plates")
    
    except KeyboardInterrupt:
        print("\nDetection interrupted by user")
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        cap.release()
    
    print(f"\n{'='*60}")
    print(f"✓ Detection completed!")
    print(f"Total unique plates: {len(detected_plates)}")
    print(f"Detected: {sorted(detected_plates)}")
    print(f"{'='*60}\n")
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description='Smart Parking System - ANPR (Automatic Number Plate Recognition)'
    )
    
    parser.add_argument('--source', type=str, default='0',
                       help='Input: 0=webcam, image file, or video file')
    parser.add_argument('--mode', type=str, choices=['image', 'video', 'realtime'],
                       default='realtime', help='Processing mode')
    parser.add_argument('--api', action='store_true',
                       help='Send detections to Flask API')
    parser.add_argument('--no-display', action='store_true',
                       help='Run without displaying windows')
    
    args = parser.parse_args()
    
    source = args.source
    
    if args.mode == 'image':
        # Process single image
        process_single_image(source)
    
    elif args.mode == 'video':
        # Process video file - detects all plates
        process_video_file(source, send_to_api=args.api)
    
    elif args.mode == 'realtime':
        # Real-time camera processing
        try:
            source = int(source)
        except ValueError:
            pass  # Keep as string (URL or file path)
        
        if args.api:
            process_video_stream_with_api(source)
        else:
            print("Real-time mode requires --api flag")
            print("Usage: python main.py --mode realtime --source 0 --api")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Smart Parking System - ANPR")
    print("="*60)
    print("\nModes:")
    print("  --mode image    : Process single image for plate")
    print("  --mode video    : Process video file - detects ALL plates")
    print("  --mode realtime : Real-time camera processing")
    print("\nExamples:")
    print("  python main.py --mode image --source car.jpg")
    print("  python main.py --mode video --source test_parking.mp4")
    print("  python main.py --mode video --source test_parking.mp4 --api")
    print("  python main.py --mode realtime --source 0 --api")
    print("  python main.py --mode realtime --source http://10.85.107.37:8080/video --api")
    print("="*60 + "\n")
    
    main()