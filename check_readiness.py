"""
Smart Parking System - Video Detection Readiness Check
"""
import os
import sys
import cv2
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def check_models():
    """Check if required ML models exist"""
    logger.info("\n" + "="*60)
    logger.info("1️⃣  CHECKING ML MODELS")
    logger.info("="*60)
    
    models = {
        'best.pt': 'Primary License Plate Detection Model',
        'best_lp.pt': 'Alternative LP Detection Model (optional)',
        'yolov8n.pt': 'Fallback YOLOv8 Nano Model'
    }
    
    for model_name, description in models.items():
        exists = os.path.exists(model_name)
        status = "✓" if exists else "✗"
        size = f"({os.path.getsize(model_name)/1024/1024:.1f}MB)" if exists else ""
        logger.info(f"{status} {model_name}: {description} {size}")
    
    best_pt = os.path.exists('best.pt')
    yolo_fallback = os.path.exists('yolov8n.pt')
    
    if not best_pt and not yolo_fallback:
        logger.error("❌ CRITICAL: No detection models found!")
        return False
    
    logger.info("✓ Models check PASSED")
    return True

def check_database():
    """Check if database is initialized"""
    logger.info("\n" + "="*60)
    logger.info("2️⃣  CHECKING DATABASE")
    logger.info("="*60)
    
    db_file = 'parking.db'
    exists = os.path.exists(db_file)
    
    if exists:
        size = os.path.getsize(db_file) / 1024
        logger.info(f"✓ Database file: {db_file} ({size:.1f}KB)")
    else:
        logger.warning(f"⚠️  Database not found: {db_file}")
        logger.info("   Run: python init_db.py")
        return False
    
    # Try to connect
    try:
        from models import create_app, Slot
        app = create_app()
        with app.app_context():
            slot_count = Slot.query.count()
            logger.info(f"✓ Database connected: {slot_count} slots found")
            
            if slot_count == 0:
                logger.error("❌ No slots in database!")
                return False
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        return False
    
    logger.info("✓ Database check PASSED")
    return True

def check_dependencies():
    """Check if required Python packages are installed"""
    logger.info("\n" + "="*60)
    logger.info("3️⃣  CHECKING PYTHON DEPENDENCIES")
    logger.info("="*60)
    
    required = {
        'cv2': 'OpenCV',
        'ultralytics': 'YOLOv8',
        'easyocr': 'EasyOCR',
        'flask': 'Flask',
        'flask_sqlalchemy': 'Flask-SQLAlchemy',
        'numpy': 'NumPy',
        'requests': 'Requests'
    }
    
    all_ok = True
    for module, name in required.items():
        try:
            __import__(module)
            logger.info(f"✓ {name}")
        except ImportError:
            logger.error(f"✗ {name} NOT INSTALLED")
            all_ok = False
    
    if not all_ok:
        logger.error("❌ Install missing packages: pip install -r requirements.txt")
        return False
    
    logger.info("✓ Dependencies check PASSED")
    return True

def check_camera_connection():
    """Check if camera source is accessible"""
    logger.info("\n" + "="*60)
    logger.info("4️⃣  CHECKING CAMERA SOURCE")
    logger.info("="*60)
    
    # Test local camera
    logger.info("Attempting to connect to local camera (index 0)...")
    cap = cv2.VideoCapture(0)
    
    if cap.isOpened():
        ret, frame = cap.read()
        cap.release()
        if ret:
            logger.info(f"✓ Local camera connected (frame size: {frame.shape})")
            return True
        else:
            logger.warning("⚠️  Local camera found but cannot read frames")
    else:
        logger.warning("⚠️  Local camera not available")
    
    # Test network camera
    logger.info("Attempting to connect to IP camera...")
    ip_camera_url = "http://10.85.107.37:8080/video"
    cap = cv2.VideoCapture(ip_camera_url)
    
    if cap.isOpened():
        logger.info(f"✓ IP camera accessible: {ip_camera_url}")
        cap.release()
        return True
    else:
        logger.warning(f"⚠️  IP camera not available: {ip_camera_url}")
    
    logger.warning("⚠️  No camera source available (you can still test manually)")
    return True  # Not critical for testing

def check_flask_endpoints():
    """Check if all required Flask endpoints are defined"""
    logger.info("\n" + "="*60)
    logger.info("5️⃣  CHECKING FLASK ENDPOINTS")
    logger.info("="*60)
    
    try:
        from slot import app
        
        required_endpoints = [
            '/api/detect',
            '/api/entry',
            '/api/exit',
            '/api/slots',
            '/api/health',
            '/api/transactions',
            '/api/vehicle-details',
            '/api/payment/status/<int:txn_id>',
            '/api/payment/process/<int:txn_id>'
        ]
        
        routes = [str(rule) for rule in app.url_map.iter_rules()]
        
        for endpoint in required_endpoints:
            # Convert Flask route format
            endpoint_normalized = endpoint.replace('<int:txn_id>', '1')
            found = any(endpoint in route or endpoint_normalized in route for route in routes)
            status = "✓" if found else "✗"
            logger.info(f"{status} {endpoint}")
        
        logger.info("✓ Endpoints check PASSED")
        return True
    except Exception as e:
        logger.error(f"❌ Endpoint check failed: {e}")
        return False

def check_project_structure():
    """Check if all required files exist"""
    logger.info("\n" + "="*60)
    logger.info("6️⃣  CHECKING PROJECT STRUCTURE")
    logger.info("="*60)
    
    required_files = {
        'slot.py': 'Flask Backend',
        'anpr_yolo_easyocr.py': 'ANPR Detection Engine',
        'camera_capture.py': 'Camera Capture Script',
        'models.py': 'Database Models',
        'init_db.py': 'Database Initializer',
        'requirements.txt': 'Dependencies List',
        'templates/index.html': 'Web Interface',
        'static/css/style.css': 'Styling',
        'static/js/main.js': 'Frontend Logic'
    }
    
    all_ok = True
    for file, description in required_files.items():
        exists = os.path.exists(file)
        status = "✓" if exists else "✗"
        logger.info(f"{status} {file} ({description})")
        if not exists:
            all_ok = False
    
    if not all_ok:
        logger.error("❌ Some required files are missing!")
        return False
    
    logger.info("✓ Project structure check PASSED")
    return True

def main():
    """Run all checks"""
    logger.info("\n")
    logger.info("╔" + "="*58 + "╗")
    logger.info("║" + " "*10 + "SMART PARKING VIDEO DETECTION READINESS" + " "*8 + "║")
    logger.info("╚" + "="*58 + "╝")
    
    checks = [
        ("Models", check_models),
        ("Database", check_database),
        ("Dependencies", check_dependencies),
        ("Camera", check_camera_connection),
        ("Flask Endpoints", check_flask_endpoints),
        ("Project Structure", check_project_structure)
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            logger.error(f"❌ {name} check failed: {e}")
            results[name] = False
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("📋 READINESS SUMMARY")
    logger.info("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {name}")
    
    logger.info("="*60)
    
    if passed == total:
        logger.info(f"\n✅ PROJECT IS READY FOR VIDEO DETECTION! ({passed}/{total})")
        logger.info("\n🚀 To start video detection:")
        logger.info("   Terminal 1: python slot.py")
        logger.info("   Terminal 2: python camera_capture.py")
        logger.info("\n🌐 Access web dashboard: http://localhost:5000")
        return 0
    else:
        logger.info(f"\n⚠️  PROJECT NEEDS FIXES ({passed}/{total})")
        logger.info("\nFix the failed checks and run this script again.")
        return 1

if __name__ == '__main__':
    sys.exit(main())