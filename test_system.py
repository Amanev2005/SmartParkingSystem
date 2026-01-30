#!/usr/bin/env python
"""
Debug script to test each component of the parking system
"""
import os
import sys
import logging
import time
import cv2
import numpy as np

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_models():
    """Test YOLO and EasyOCR models load correctly"""
    logger.info("\n" + "="*70)
    logger.info("TEST 1: Model Loading")
    logger.info("="*70)
    
    try:
        from anpr_yolo_easyocr import model, reader
        logger.info("✓ YOLO model loaded")
        logger.info("✓ EasyOCR reader loaded")
        return True
    except Exception as e:
        logger.error(f"✗ Model loading failed: {e}")
        return False

def test_flask_api():
    """Test Flask API connectivity"""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: Flask API")
    logger.info("="*70)
    
    try:
        import requests
        
        # Test health
        resp = requests.get('http://localhost:5000/api/health', timeout=2)
        if resp.status_code == 200:
            logger.info("✓ Flask API /api/health responding")
        else:
            logger.error(f"✗ Health check returned {resp.status_code}")
            return False
        
        # Test database
        resp = requests.get('http://localhost:5000/api/slots', timeout=2)
        if resp.status_code == 200:
            slots = resp.json()
            logger.info(f"✓ Database has {len(slots)} slots")
            free = [s for s in slots if s['status'] == 'free']
            occupied = [s for s in slots if s['status'] == 'occupied']
            logger.info(f"  - Free: {len(free)}, Occupied: {len(occupied)}")
        else:
            logger.error(f"✗ /api/slots returned {resp.status_code}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"✗ Flask API test failed: {e}")
        return False

def test_camera():
    """Test camera/webcam access"""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Camera Access")
    logger.info("="*70)
    
    try:
        # Try local camera
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            logger.warning("⚠ Local camera (ID 0) not available")
            logger.info("  Trying IP camera...")
            
            # This would need user's IP camera URL
            logger.warning("  Skipping IP camera test - requires setup")
            return True
        
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            logger.info(f"✓ Camera working - captured {frame.shape[1]}x{frame.shape[0]} frame")
            return True
        else:
            logger.error("✗ Could not read frame from camera")
            return False
            
    except Exception as e:
        logger.error(f"✗ Camera test failed: {e}")
        return False

def test_anpr_detection():
    """Test ANPR detection on a dummy image"""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: ANPR Detection (Dummy Image)")
    logger.info("="*70)
    
    try:
        from anpr_yolo_easyocr import recognize_plate_from_frame
        
        # Create dummy frame (usually no plates detected in random noise)
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        plate = recognize_plate_from_frame(dummy_frame)
        
        if plate is None:
            logger.info("✓ ANPR working (no plates in dummy image - expected)")
        else:
            logger.warning(f"⚠ Detected '{plate}' in dummy image (may be false positive)")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ ANPR test failed: {e}")
        return False

def test_camera_capture_anpr():
    """Test ANPR detection on actual camera frame"""
    logger.info("\n" + "="*70)
    logger.info("TEST 5: ANPR Detection (Real Camera Frame)")
    logger.info("="*70)
    
    try:
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            logger.warning("⚠ Camera not available - skipping real frame test")
            return True
        
        logger.info("Capturing 5 frames for detection...")
        from anpr_yolo_easyocr import recognize_plate_from_frame
        
        detections = []
        for i in range(5):
            ret, frame = cap.read()
            if ret:
                plate = recognize_plate_from_frame(frame)
                if plate:
                    detections.append(plate)
                    logger.info(f"  Frame {i+1}: ✓ Detected {plate}")
                else:
                    logger.info(f"  Frame {i+1}: No plate detected")
            time.sleep(0.5)
        
        cap.release()
        
        if detections:
            logger.info(f"✓ Detected {len(detections)} plates across 5 frames")
            return True
        else:
            logger.warning("⚠ No plates detected in 5 frames (may need to point camera at a plate)")
            return True
            
    except Exception as e:
        logger.error(f"✗ Camera ANPR test failed: {e}")
        return False

def test_api_detection():
    """Test the full /api/detect endpoint"""
    logger.info("\n" + "="*70)
    logger.info("TEST 6: API Detection Endpoint")
    logger.info("="*70)
    
    try:
        import requests
        
        test_plate = "DL01AB1234"
        
        resp = requests.post(
            'http://localhost:5000/api/detect',
            data={'plate': test_plate},
            timeout=5
        )
        
        if resp.status_code == 200:
            result = resp.json()
            logger.info(f"✓ API accepted plate: {test_plate}")
            logger.info(f"  Response: {result}")
            
            if result.get('success'):
                logger.info(f"  → Slot allocated: {result.get('slot_number')}")
            else:
                logger.warning(f"  → Error: {result.get('error')}")
            
            return True
        else:
            logger.error(f"✗ API returned {resp.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"✗ API test failed: {e}")
        return False

def diagnose_issue():
    """Run all tests and summarize findings"""
    logger.info("\n")
    logger.info("╔" + "="*68 + "╗")
    logger.info("║" + " "*20 + "PARKING SYSTEM DIAGNOSTICS" + " "*22 + "║")
    logger.info("╚" + "="*68 + "╝")
    
    tests = [
        ("Model Loading", test_models),
        ("Flask API", test_flask_api),
        ("Camera Access", test_camera),
        ("ANPR Detection (Dummy)", test_anpr_detection),
        ("ANPR Detection (Real)", test_camera_capture_anpr),
        ("API Endpoint", test_api_detection),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            logger.error(f"✗ {name} crashed: {e}")
            results[name] = False
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("SUMMARY")
    logger.info("="*70)
    
    for name, status in results.items():
        status_str = "✓ PASS" if status else "✗ FAIL"
        logger.info(f"{status_str:10} - {name}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    logger.info(f"\n{passed}/{total} tests passed")
    
    # Recommendations
    logger.info("\n" + "="*70)
    logger.info("RECOMMENDATIONS")
    logger.info("="*70)
    
    if not results.get("Flask API", False):
        logger.error("→ Start Flask server: python slot.py")
    
    if not results.get("Model Loading", False):
        logger.error("→ Install dependencies: pip install -r requirements.txt")
    
    if not results.get("Camera Access", False):
        logger.error("→ Camera not working. Update IP_WEBCAM_URL in camera_capture.py or connect local webcam")
    
    if not results.get("ANPR Detection (Real)", False):
        logger.warning("→ ANPR not detecting plates. Point camera at a visible license plate")
        logger.warning("→ Check lighting and plate orientation")
    
    if results.get("API Detection", False) and results.get("ANPR Detection (Real)", False):
        logger.info("\n✓ System is ready. Run:")
        logger.info("  python camera_capture.py --photo --dedup 20")
    
    logger.info("="*70 + "\n")

if __name__ == '__main__':
    diagnose_issue()
