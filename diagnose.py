import cv2
import requests
import time
from anpr_yolo_easyocr import recognize_plate_from_frame, model, reader
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

print("\n" + "="*70)
print("DIAGNOSTIC: Plate Detection System")
print("="*70 + "\n")

# 1. Check API
print("1. Checking Flask API...")
try:
    resp = requests.get('http://localhost:5000/api/health', timeout=2)
    print(f"   ✓ API Status: {resp.status_code}")
except Exception as e:
    print(f"   ✗ API Error: {e}")

# 2. Check YOLO Model
print("\n2. Checking YOLO Model...")
try:
    print(f"   ✓ Model loaded: {model}")
    print(f"   ✓ Model device: {model.device}")
except Exception as e:
    print(f"   ✗ Model Error: {e}")

# 3. Check OCR Reader
print("\n3. Checking OCR Reader...")
try:
    print(f"   ✓ Reader loaded: {reader}")
except Exception as e:
    print(f"   ✗ Reader Error: {e}")

# 4. Test with webcam
print("\n4. Testing IP Webcam Connection...")
IP_WEBCAM_URL = "http://10.109.18.31:8080/video"
try:
    cap = cv2.VideoCapture(IP_WEBCAM_URL, cv2.CAP_FFMPEG)
    time.sleep(1)
    
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            h, w = frame.shape[:2]
            print(f"   ✓ Webcam connected: {w}x{h}")
            
            # Test plate detection on this frame
            print("\n5. Testing Plate Detection...")
            start = time.time()
            plate = recognize_plate_from_frame(frame, debug=True)
            elapsed = time.time() - start
            
            if plate:
                print(f"   ✓ Plate detected: {plate} ({elapsed:.2f}s)")
            else:
                print(f"   ✗ No plate detected ({elapsed:.2f}s)")
                print("   → Try: Adjust webcam angle, lighting, or move vehicle")
        else:
            print(f"   ✗ Cannot read frames from webcam")
    else:
        print(f"   ✗ Cannot open webcam at {IP_WEBCAM_URL}")
    
    cap.release()
except Exception as e:
    print(f"   ✗ Webcam Error: {e}")

print("\n" + "="*70 + "\n")
