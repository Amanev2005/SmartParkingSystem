import cv2
import time
from anpr_yolo_easyocr import recognize_plate_from_frame
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_with_image(image_path):
    """Test plate detection with a single image"""
    print(f"\n{'='*60}")
    print(f"Testing with image: {image_path}")
    print('='*60)
    
    image = cv2.imread(image_path)
    if image is None:
        print(f"ERROR: Could not read image {image_path}")
        return
    
    print(f"Image size: {image.shape[1]}x{image.shape[0]}")
    
    # Test multiple times
    for i in range(3):
        print(f"\n--- Attempt {i+1} ---")
        start_time = time.time()
        plate = recognize_plate_from_frame(image)
        elapsed = time.time() - start_time
        
        if plate:
            print(f"✓ Plate detected: {plate}")
            print(f"  Time: {elapsed:.2f}s")
            
            # Display with plate
            annotated = image.copy()
            cv2.putText(annotated, f'Plate: {plate}', 
                       (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 
                       1.5, (0, 255, 0), 3)
            cv2.imshow(f'Detection Result - {image_path}', annotated)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            return True
        else:
            print(f"✗ No plate detected")
            print(f"  Time: {elapsed:.2f}s")
    
    # Show original image if no detection
    cv2.imshow(f'Original Image - {image_path}', image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    return False

def test_with_video(video_path, duration=10):
    """Test plate detection with video"""
    print(f"\n{'='*60}")
    print(f"Testing with video: {video_path}")
    print('='*60)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"ERROR: Could not open video {video_path}")
        return
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"Video: {width}x{height} @ {fps:.1f} FPS")
    print("Press 'q' to quit, 's' to skip to next test")
    
    frame_count = 0
    start_time = time.time()
    detections = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        
        # Process every 10th frame
        if frame_count % 10 == 0:
            plate = recognize_plate_from_frame(frame)
            
            if plate:
                detections += 1
                print(f"\nFrame {frame_count}: ✓ Plate detected: {plate}")
                
                # Display with annotation
                annotated = frame.copy()
                cv2.putText(annotated, f'Plate: {plate}', 
                           (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 
                           1, (0, 255, 0), 2)
                cv2.putText(annotated, f'Frame: {frame_count}', 
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.7, (255, 255, 255), 2)
                cv2.imshow('Video Test - Plate Detection', annotated)
            else:
                cv2.imshow('Video Test - Plate Detection', frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                break
        
        # Stop after duration
        if time.time() - start_time > duration:
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    print(f"\n{'='*60}")
    print(f"Test Summary:")
    print(f"  Frames processed: {frame_count}")
    print(f"  Plates detected: {detections}")
    print(f"  Detection rate: {detections/max(frame_count/10, 1):.1%}")
    print('='*60)

def test_with_ip_webcam():
    """Test with IP webcam"""
    print(f"\n{'='*60}")
    print("Testing with IP Webcam")
    print('='*60)
    
    import requests
    from camera_capture import open_ip_webcam
    
    # Test connection first
    try:
        resp = requests.get("http://10.85.107.37:8080", timeout=2)
        print("✓ IP Webcam server is reachable")
    except:
        print("✗ Cannot reach IP Webcam server")
        return
    
    cap = open_ip_webcam()
    if not cap:
        print("✗ Failed to open IP webcam stream")
        return
    
    print("✓ IP Webcam connected")
    print("Press 'q' to quit")
    
    frame_count = 0
    detections = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("No frame received")
                time.sleep(1)
                continue
            
            frame_count += 1
            
            # Process every 5th frame
            if frame_count % 5 == 0:
                plate = recognize_plate_from_frame(frame)
                
                if plate:
                    detections += 1
                    print(f"\nFrame {frame_count}: ✓ Plate detected: {plate}")
                    
                    # Display with annotation
                    annotated = frame.copy()
                    cv2.putText(annotated, f'Plate: {plate}', 
                               (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 
                               1, (0, 255, 0), 2)
                    cv2.imshow('IP Webcam Test', annotated)
                else:
                    cv2.imshow('IP Webcam Test', frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
    
    except KeyboardInterrupt:
        print("\nTest interrupted")
    finally:
        cap.release()
        cv2.destroyAllWindows()
    
    print(f"\n{'='*60}")
    print(f"IP Webcam Test Summary:")
    print(f"  Frames processed: {frame_count}")
    print(f"  Plates detected: {detections}")
    print('='*60)

if __name__ == '__main__':
    print("Smart Parking System - Plate Detection Test")
    print("Choose test mode:")
    print("1. Test with image")
    print("2. Test with video file")
    print("3. Test with IP webcam")
    print("4. Test all")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    if choice == '1':
        image_path = input("Enter image path (or press Enter for default): ").strip()
        if not image_path:
            image_path = "test_plate.jpg"  # Change to your test image
        test_with_image(image_path)
    
    elif choice == '2':
        video_path = input("Enter video path (or press Enter for default): ").strip()
        if not video_path:
            video_path = "test_video.mp4"  # Change to your test video
        test_with_video(video_path)
    
    elif choice == '3':
        test_with_ip_webcam()
    
    elif choice == '4':
        # Test with sample image
        test_with_image("test_plate.jpg")
        
        # Test with video
        test_with_video("test_video.mp4", duration=5)
        
        # Test with IP webcam
        test_with_ip_webcam()
    
    else:
        print("Invalid choice")