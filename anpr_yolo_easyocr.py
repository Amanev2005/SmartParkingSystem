import numpy as np
import cv2
from ultralytics import YOLO
import easyocr
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load model - CPU mode
MODEL_PATH = 'best.pt'
try:
    logger.info('[MODEL] Loading best.pt...')
    model = YOLO(MODEL_PATH)
    # Use CPU - don't call .to('cuda')
    logger.info('[MODEL] ✓ Model loaded (CPU mode)')
except Exception as e:
    logger.warning(f'[MODEL] best.pt not found, loading YOLOv8n: {e}')
    model = YOLO('yolov8n.pt')
    logger.info('[MODEL] ✓ YOLOv8n loaded (CPU mode)')

# Initialize reader - CPU mode
logger.info('[OCR] Initializing EasyOCR reader...')
reader = easyocr.Reader(['en'], gpu=False)  # CPU mode
logger.info('[OCR] ✓ Reader initialized')

def preprocess_plate(plate_crop):
    """Fast preprocessing for CPU"""
    try:
        if len(plate_crop.shape) == 3:
            gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = plate_crop
        
        height, width = gray.shape
        if width < 300:
            gray = cv2.resize(gray, (300, int(300 * height / width)), 
                            interpolation=cv2.INTER_LINEAR)
        
        gray = cv2.bilateralFilter(gray, 9, 15, 15)
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        return binary
    except Exception as e:
        logger.error(f'[PREPROCESS] Error: {e}')
        return plate_crop

def smart_plate_correction(plate_text):
    """Position-based character correction for Indian plates: AA 00 AA 0000"""
    if not plate_text or len(plate_text) < 8:
        return None
    
    clean = plate_text.replace(' ', '').upper()
    
    corrections = {
        0: 'letter',   # AA 00 AA 0000
        1: 'letter',
        2: 'digit',
        3: 'digit',
        4: 'letter',
        5: 'letter',
        6: 'digit',
        7: 'digit',
        8: 'digit',
        9: 'digit',
    }
    
    corrected = []
    for i, char in enumerate(clean):
        if i >= len(corrections):
            corrected.append(char)
            continue
        
        expected = corrections[i]
        
        if expected == 'letter':
            if char.isalpha():
                corrected.append(char)
            elif char == '0':
                corrected.append('O')
            elif char == '1':
                corrected.append('I')
            elif char == '5':
                corrected.append('S')
            elif char == '8':
                corrected.append('B')
            else:
                corrected.append('A')
        else:
            if char.isdigit():
                corrected.append(char)
            elif char == 'O':
                corrected.append('0')
            elif char in 'IL':
                corrected.append('1')
            elif char == 'S':
                corrected.append('5')
            elif char == 'B':
                corrected.append('8')
            elif char == 'Z':
                corrected.append('2')
            else:
                corrected.append('0')
        
    return ''.join(corrected)

def recognize_plate_from_frame(frame_bgr):
    """Optimized for CPU - smaller image size"""
    try:
        h, w = frame_bgr.shape[:2]
        
        # More aggressive downsampling for CPU speed
        if max(h, w) > 384:
            scale = 384 / max(h, w)
            frame_small = cv2.resize(frame_bgr, 
                (int(w*scale), int(h*scale)), 
                interpolation=cv2.INTER_LINEAR)
        else:
            frame_small = frame_bgr
        
        img = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
    except Exception as e:
        logger.error(f'[FRAME] Error: {e}')
        return None

    # YOLO detection - CPU optimized
    try:
        results = model(img, imgsz=320, conf=0.5, iou=0.45, verbose=False, device='cpu')
    except Exception as e:
        logger.error(f'[YOLO] Detection error: {e}')
        return None
    
    best_plate = None
    best_confidence = 0
    
    for r in results:
        if not hasattr(r, 'boxes') or r.boxes is None:
            continue
        
        for box in r.boxes:
            try:
                xyxy = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = [int(v) for v in xyxy]
            except Exception:
                continue

            # Scale back to original
            if max(h, w) > 384:
                sx = w / frame_small.shape[1]
                sy = h / frame_small.shape[0]
                x1, x2 = int(x1 * sx), int(x2 * sx)
                y1, y2 = int(y1 * sy), int(y2 * sy)

            h0, w0 = frame_bgr.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w0-1, x2), min(h0-1, y2)
            
            plate_crop = frame_bgr[y1:y2, x1:x2]
            if plate_crop.size < 100:
                continue

            processed = preprocess_plate(plate_crop)
            
            try:
                ocr_result = reader.readtext(processed, detail=1)
            except Exception:
                continue
            
            texts = []
            confidences = []
            for seg in ocr_result:
                text = seg[1].strip()
                conf = seg[2]
                if text and len(text) > 1:
                    texts.append(text)
                    confidences.append(conf)
            
            if not texts:
                continue
            
            full_text = ''.join(texts)
            avg_confidence = np.mean(confidences) if confidences else 0
            
            plate_corrected = smart_plate_correction(full_text)
            
            if plate_corrected and len(plate_corrected) >= 8:
                if avg_confidence > best_confidence:
                    best_plate = plate_corrected
                    best_confidence = avg_confidence
    
    return best_plate