import numpy as np
import cv2
from ultralytics import YOLO
import easyocr
import re
from difflib import SequenceMatcher

# Try to load a custom plate-detection model first, fall back to yolov8n (smaller)
MODEL_PATH = 'best.pt'  # put your trained plate-detector here
try:
    model = YOLO(MODEL_PATH)
except Exception:
    print("Custom model not found, using YOLOv8n")
    model = YOLO('yolov8n.pt')

# Initialize EasyOCR reader (English + digits). Set gpu=False for CPU
reader = easyocr.Reader(['en'], gpu=False)

# Valid plate patterns - adjust based on your region
# Example: KA 01 AB 1234 (Indian format) or similar
plate_patterns = [
    re.compile(r'^[A-Z]{2}\s?\d{2}\s?[A-Z]{2}\s?\d{4}$'),  # KA 01 AB 1234
    re.compile(r'^[A-Z]{2}\d{2}[A-Z]{2}\d{4}$'),  # KA01AB1234
    re.compile(r'^[A-Z]{2}\s?\d{2}\s?[A-Z]\s?\d{4}$'),  # KA 01 A 1234
]

# Character confusion mapping - common OCR misreads
CHAR_CORRECTIONS = {
    # Letter to Letter confusion
    'H': 'M',  # H often read as M
    'M': 'H',  # M often read as H
    'Q': 'O',  # Q often read as O
    'O': 'Q',  # O often read as Q
    'I': '1',  # I often read as 1
    'L': '1',  # L often read as 1
    'Z': '2',  # Z often read as 2
    'S': '5',  # S often read as 5
    'B': '8',  # B often read as 8
    '0': 'O',  # 0 often read as O
    '1': 'I',  # 1 often read as I
    '5': 'S',  # 5 often read as S
    '8': 'B',  # 8 often read as B
}

def fix_similar_characters(text, position_type='letter'):
    """
    Fix common OCR confusions based on position in plate.
    
    Args:
        text: OCR recognized text
        position_type: 'letter' for letter positions, 'digit' for digit positions
    """
    if not text:
        return text
    
    corrected = []
    for i, char in enumerate(text):
        if char in CHAR_CORRECTIONS:
            # Apply position-based correction logic
            if position_type == 'letter':
                # In letter positions, prefer letters
                if char.isdigit():
                    # Convert digits that should be letters
                    if char == '0':
                        corrected.append('O')
                    elif char == '1':
                        corrected.append('I')
                    elif char == '5':
                        corrected.append('S')
                    elif char == '8':
                        corrected.append('B')
                    else:
                        corrected.append(char)
                else:
                    # Keep letters but fix confusions
                    corrected.append(char)
            else:
                # In digit positions, prefer digits
                if char.isalpha():
                    # Convert letters that should be digits
                    if char == 'O':
                        corrected.append('0')
                    elif char == 'I' or char == 'L':
                        corrected.append('1')
                    elif char == 'S':
                        corrected.append('5')
                    elif char == 'B':
                        corrected.append('8')
                    elif char == 'Z':
                        corrected.append('2')
                    else:
                        corrected.append(char)
                else:
                    corrected.append(char)
        else:
            corrected.append(char)
    
    return ''.join(corrected)

def smart_plate_correction(plate_text):
    """
    Apply intelligent corrections based on Indian license plate format:
    Format: AA 00 AA 0000
    - Positions 0-1: Must be LETTERS
    - Positions 3-4: Must be DIGITS
    - Positions 6-7: Must be LETTERS
    - Positions 9-12: Must be DIGITS
    """
    if not plate_text:
        return None
    
    # Remove all spaces first
    clean = plate_text.replace(' ', '')
    
    # Ensure minimum length
    if len(clean) < 8:
        return None
    
    corrected = []
    
    for i, char in enumerate(clean):
        # State machine based on expected format: AANNAA NNNN
        if i < 2:  # First 2 should be LETTERS
            corrected.append(fix_similar_characters(char, 'letter').upper())
        elif i < 4:  # Next 2 should be DIGITS
            corrected.append(fix_similar_characters(char, 'digit').upper())
        elif i < 6:  # Next 2 should be LETTERS
            corrected.append(fix_similar_characters(char, 'letter').upper())
        else:  # Last 4 should be DIGITS
            corrected.append(fix_similar_characters(char, 'digit').upper())
    
    result = ''.join(corrected)
    return result

def clean_text(s: str) -> str:
    """Normalize OCR output and extract plausible plate."""
    if not s:
        return None
    
    s = s.upper().strip()
    # Remove special characters but keep spaces
    s = re.sub(r'[^A-Z0-9\s]', '', s)
    # Remove extra spaces
    s = ' '.join(s.split())
    
    return s if s else None

def is_valid_plate(plate: str) -> bool:
    """Check if plate matches valid patterns"""
    if not plate or len(plate) < 8:
        return False
    
    # Try each pattern
    for pattern in plate_patterns:
        if pattern.match(plate):
            return True
    
    # Fallback: check if it has letters and numbers in reasonable proportions
    letters = sum(1 for c in plate if c.isalpha())
    digits = sum(1 for c in plate if c.isdigit())
    
    # Should have at least 4 letters and 4 digits
    return letters >= 4 and digits >= 4

def preprocess_plate(plate_crop):
    """Advanced preprocessing for better OCR accuracy"""
    try:
        # Convert to grayscale
        if len(plate_crop.shape) == 3:
            gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = plate_crop
        
        # Resize if too small (improves OCR)
        height, width = gray.shape
        if width < 400 or height < 60:
            scale = max(400 / width, 60 / height)
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        
        # Apply bilateral filter to reduce noise while keeping edges sharp
        gray = cv2.bilateralFilter(gray, 11, 17, 17)
        
        # Adaptive histogram equalization (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        
        # Denoise
        gray = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
        
        # Threshold using Otsu's method
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        return binary
    except Exception as e:
        print(f"Preprocessing error: {e}")
        return plate_crop

def recognize_plate_from_frame(frame_bgr):
    """
    Input: frame as BGR numpy array
    Output: plate text (string) or None
    
    Enhanced with character-level corrections
    """
    try:
        # Resize to reduce work (keep aspect)
        h, w = frame_bgr.shape[:2]
        target_w = 640
        if max(h, w) > target_w:
            scale = target_w / max(h, w)
            frame_small = cv2.resize(frame_bgr, (int(w*scale), int(h*scale)))
        else:
            frame_small = frame_bgr

        img = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
    except Exception as e:
        print(f"Frame conversion error: {e}")
        return None

    # Detect plates using YOLO
    results = model(img, imgsz=320, conf=0.35)
    
    best_plate = None
    best_confidence = 0
    
    for r in results:
        if not hasattr(r, 'boxes') or r.boxes is None:
            continue
        
        for box in r.boxes:
            try:
                xyxy = box.xyxy[0].cpu().numpy() if hasattr(box, 'xyxy') else box.xyxy
                x1, y1, x2, y2 = [int(v) for v in xyxy]
            except Exception:
                continue

            # Map back to original frame coordinates if we resized earlier
            if max(h, w) > target_w:
                sx = w / frame_small.shape[1]
                sy = h / frame_small.shape[0]
                x1, x2 = int(x1 * sx), int(x2 * sx)
                y1, y2 = int(y1 * sy), int(y2 * sy)

            h0, w0 = frame_bgr.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w0-1, x2), min(h0-1, y2)
            
            plate_crop = frame_bgr[y1:y2, x1:x2]
            if plate_crop.size == 0:
                continue

            # Preprocess plate for better OCR
            processed = preprocess_plate(plate_crop)
            
            # Run OCR with preprocessing
            try:
                ocr_result = reader.readtext(processed, detail=1)
            except Exception:
                # Fallback to original if preprocessing OCR fails
                try:
                    ocr_result = reader.readtext(plate_crop, detail=1)
                except Exception:
                    continue
            
            # Extract and clean text with confidence scores
            texts = []
            confidences = []
            for seg in ocr_result:
                text = seg[1].strip()
                conf = seg[2]  # Confidence score
                if text:
                    texts.append(text)
                    confidences.append(conf)
            
            if not texts:
                continue
            
            # Combine text
            full_text = ' '.join(texts)
            avg_confidence = np.mean(confidences) if confidences else 0
            
            # Clean text
            plate = clean_text(full_text)
            
            if not plate:
                continue
            
            # Apply smart character corrections based on position
            plate_corrected = smart_plate_correction(plate)
            
            if not plate_corrected:
                continue
            
            # Validate plate format
            if is_valid_plate(plate_corrected):
                # Keep the plate with highest confidence
                if avg_confidence > best_confidence:
                    best_plate = plate_corrected
                    best_confidence = avg_confidence
                    print(f"[OCR] Original: {plate} → Corrected: {plate_corrected} (Confidence: {avg_confidence:.2f})")
    
    return best_plate