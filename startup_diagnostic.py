#!/usr/bin/env python
"""
Startup diagnostic script - checks all system requirements before running detection
"""
import os
import sys
import logging
import time

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_python_modules():
    """Check if all required modules are installed"""
    logger.info("="*70)
    logger.info("CHECKING PYTHON MODULES")
    logger.info("="*70)
    
    required = ['cv2', 'ultralytics', 'easyocr', 'flask', 'flask_sqlalchemy', 'numpy', 'requests']
    missing = []
    
    for module in required:
        try:
            __import__(module)
            logger.info(f"✓ {module}")
        except ImportError:
            logger.error(f"✗ {module} - MISSING")
            missing.append(module)
    
    if missing:
        logger.error(f"\n✗ Missing modules: {', '.join(missing)}")
        logger.info("Install with: pip install -r requirements.txt")
        return False
    
    logger.info("✓ All modules OK\n")
    return True

def check_model_files():
    """Check if YOLO and other model files exist"""
    logger.info("="*70)
    logger.info("CHECKING MODEL FILES")
    logger.info("="*70)
    
    models = ['best.pt', 'best_lp.pt', 'yolov8n.pt']
    found = []
    missing = []
    
    for model in models:
        if os.path.exists(model):
            size_mb = os.path.getsize(model) / (1024*1024)
            logger.info(f"✓ {model} ({size_mb:.1f} MB)")
            found.append(model)
        else:
            logger.warning(f"? {model} - NOT FOUND (will download on first run)")
            missing.append(model)
    
    if found:
        logger.info("✓ At least one model file found\n")
        return True
    else:
        logger.warning("⚠ No model files found - they will auto-download\n")
        return True

def init_database():
    """Initialize database with slots"""
    logger.info("="*70)
    logger.info("INITIALIZING DATABASE")
    logger.info("="*70)
    
    from models import create_app, db, Slot
    
    try:
        app = create_app()
        
        with app.app_context():
            # Create tables
            db.create_all()
            logger.info("✓ Database tables created")
            
            # Check if slots exist
            existing_slots = Slot.query.count()
            if existing_slots == 0:
                logger.info("Creating 10 parking slots...")
                for i in range(1, 11):
                    slot = Slot(number=i, status='free')
                    db.session.add(slot)
                db.session.commit()
                logger.info(f"✓ Created 10 slots")
            else:
                logger.info(f"✓ Database has {existing_slots} slots already")
            
            logger.info("✓ Database OK\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ Database error: {e}\n")
        return False

def start_flask_server():
    """Start Flask server in background"""
    logger.info("="*70)
    logger.info("STARTING FLASK SERVER")
    logger.info("="*70)
    
    import subprocess
    import threading
    
    try:
        # Start Flask in background
        process = subprocess.Popen(
            [sys.executable, 'slot.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info("✓ Flask server started (PID: {})".format(process.pid))
        
        # Give server time to start
        time.sleep(3)
        
        # Check health
        try:
            if HAS_REQUESTS:
                resp = requests.get('http://localhost:5000/api/health', timeout=2)
                if resp.status_code == 200:
                    logger.info("✓ Flask API is responding\n")
                    return process
            else:
                logger.warning("⚠ requests module not available, skipping API health check")
        except Exception as e:
            logger.warning(f"⚠ Health check failed: {e}")
        
        logger.warning("⚠ Flask server started but not responding yet\n")
        return process
        
    except Exception as e:
        logger.error(f"✗ Failed to start Flask: {e}\n")
        return None

def check_anpr():
    """Test ANPR system"""
    logger.info("="*70)
    logger.info("TESTING ANPR DETECTION")
    logger.info("="*70)
    
    try:
        from anpr_yolo_easyocr import recognize_plate_from_frame
        import cv2
        import numpy as np
        
        # Create a dummy frame
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Try recognition
        result = recognize_plate_from_frame(dummy_frame)
        logger.info("✓ ANPR system loaded\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ ANPR error: {e}\n")
        return False

def check_camera():
    """Check if camera is accessible"""
    logger.info("="*70)
    logger.info("CHECKING CAMERA")
    logger.info("="*70)
    
    try:
        import cv2
        
        # Try local camera
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret:
                logger.info("✓ Local camera is accessible\n")
                return True
        
        logger.warning("⚠ Local camera not accessible (may need IP camera)\n")
        return True
        
    except Exception as e:
        logger.error(f"⚠ Camera check failed: {e}\n")
        return True

def main():
    logger.info("\n")
    logger.info("╔" + "="*68 + "╗")
    logger.info("║" + " "*15 + "SMART PARKING SYSTEM STARTUP DIAGNOSTIC" + " "*15 + "║")
    logger.info("╚" + "="*68 + "╝")
    logger.info("")
    
    steps = [
        ("Python Modules", check_python_modules),
        ("Model Files", check_model_files),
        ("Database Init", init_database),
        ("ANPR System", check_anpr),
        ("Camera", check_camera),
    ]
    
    results = {}
    for name, check_func in steps:
        try:
            results[name] = check_func()
        except Exception as e:
            logger.error(f"✗ {name} check failed: {e}")
            results[name] = False
    
    logger.info("="*70)
    logger.info("SUMMARY")
    logger.info("="*70)
    
    all_ok = all(results.values())
    
    for name, status in results.items():
        status_str = "✓ OK" if status else "✗ FAIL"
        logger.info(f"{status_str:8} - {name}")
    
    logger.info("="*70)
    
    if all_ok:
        logger.info("\n✓ SYSTEM READY TO RUN\n")
        logger.info("Start detection with:")
        logger.info("  python camera_capture.py --photo --dedup 20")
        logger.info("or (continuous):")
        logger.info("  python camera_capture.py --local 0 --dedup 20")
        return True
    else:
        logger.error("\n✗ SYSTEM NOT READY - Fix issues above")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
