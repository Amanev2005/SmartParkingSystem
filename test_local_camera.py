#!/usr/bin/env python
"""Test local camera detection"""
import sys
sys.path.insert(0, '.')

import cv2
import time
from anpr_yolo_easyocr import recognize_plate_from_frame
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("\nTesting Local Camera Detection...")
print("="*70)

# Try to open local camera
print("\n1. Opening local camera (ID: 0)...")
cap = cv2.VideoCapture(0)
time.sleep(1)

if not cap.isOpened():
    print("✗ FAILED: Cannot open local camera")
    print("\nSolutions:")
    print("  1. Check if webcam is connected and working")
    print("  2. Try camera ID 1, 2, etc: python test_local_camera.py")
    print("  3. Use IP camera: python camera_capture.py --url http://YOUR_IP:8080/video")
    sys.exit(1)

ret, frame = cap.read()
if not ret:
    print("✗ FAILED: Cannot read from camera")
    cap.release()
    sys.exit(1)

h, w = frame.shape[:2]
print(f"✓ Camera connected: {w}x{h} resolution")

# Test plate detection
print("\n2. Testing plate detection (5 seconds)...")
frames_tested = 0
plates_detected = 0

start_time = time.time()
while time.time() - start_time < 5:
    ret, frame = cap.read()
    if not ret:
        print("✗ Lost camera connection")
        break
    
    frames_tested += 1
    plate = recognize_plate_from_frame(frame)
    
    if plate:
        plates_detected += 1
        print(f"  ✓ Plate detected: {plate}")

cap.release()

print(f"\nResults:")
print(f"  Frames tested: {frames_tested}")
print(f"  Plates detected: {plates_detected}")

if plates_detected > 0:
    print(f"\n✓ SUCCESS: Camera and detection working!")
    print(f"\nTo start the full system:")
    print(f"  python camera_capture.py --local 0")
else:
    print(f"\n⚠ No plates detected yet. Check:")
    print(f"  • Vehicle with clear license plate in frame")
    print(f"  • Good lighting conditions")
    print(f"  • Camera angle and focus")

print("="*70 + "\n")
