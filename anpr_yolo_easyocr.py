# ...existing code...
import numpy as np
import cv2
from ultralytics import YOLO
import easyocr
import re

# Try to load a custom plate-detection model first, fall back to yolov8n (smaller)
MODEL_PATH = 'best_lp.pt'  # put your trained plate-detector here
try:
    model = YOLO(MODEL_PATH)
except Exception:
    # yolov8n is smallest and fastest on CPU
    model = YOLO('yolov8n.pt')

# Initialize EasyOCR reader (English + digits). Set gpu=False for CPU
reader = easyocr.Reader(['en'], gpu=False)

plate_regex = re.compile(r'[A-Z0-9]{2,}')

def clean_text(s: str) -> str:
    """Normalize OCR output and extract plausible plate (letters/numbers)."""
    if not s:
        return None
    s = s.upper()
    s = re.sub(r'[^A-Z0-9]', '', s)
    m = plate_regex.search(s)
    return m.group(0) if m else None
    
# ...existing code...
def recognize_plate_from_frame(frame_bgr):
    """Input: frame as BGR numpy array. Output: plate text (string) or None"""
    try:
        # resize to reduce work (keep aspect)
        h, w = frame_bgr.shape[:2]
        target_w = 640
        if max(h, w) > target_w:
            scale = target_w / max(h, w)
            frame_small = cv2.resize(frame_bgr, (int(w*scale), int(h*scale)))
        else:
            frame_small = frame_bgr

        img = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
    except Exception:
        return None

    # smaller imgsz and slightly higher conf => fewer boxes, faster OCR
    results = model(img, imgsz=320, conf=0.35)  # changed from imgsz=640
    for r in results:
        if not hasattr(r, 'boxes') or r.boxes is None:
            continue
        for box in r.boxes:
            # ...existing code...
            # when cropping back to original coordinates, scale accordingly
            try:
                xyxy = box.xyxy[0].cpu().numpy() if hasattr(box, 'xyxy') and getattr(box.xyxy, '__len__', lambda: 0)() else box.xyxy
            except Exception:
                continue
            try:
                x1, y1, x2, y2 = [int(v) for v in xyxy]
            except Exception:
                continue

            # map back to original frame coordinates if we resized earlier
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

            # aggressive preprocessing to help OCR and be fast
            gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
            gray = cv2.medianBlur(gray, 3)
            try:
                _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            except Exception:
                th = gray
            try:
                ocr_result = reader.readtext(th, detail=1)
            except Exception:
                ocr_result = reader.readtext(plate_crop, detail=1)
            text = ''.join([seg[1] for seg in ocr_result]).strip()
            plate = clean_text(text)
            if plate:
                return plate
    return None