import numpy as np
import cv2
from ultralytics import YOLO
import easyocr
import re
import logging
from datetime import datetime
from collections import defaultdict, Counter
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Frame Aggregation System - Vote on plates across multiple frames
class FrameAggregator:
    """Aggregate plate detections across frames to reduce false positives"""
    
    def __init__(self, window_size=5, threshold=2):
        """
        Args:
            window_size: Number of frames to aggregate (default 5)
            threshold: Minimum votes to accept a plate (default 2 out of 5 - more forgiving)
        """
        self.window_size = window_size
        self.threshold = threshold
        self.detection_history = []  # List of (plate, confidence) tuples
        self.last_confirmed = None
        self.confirmed_time = None
    
    def add_detection(self, plate, confidence=1.0):
        """Add a detection to the aggregation window"""
        if plate is None:
            self.detection_history.append((None, 0.0))
        else:
            self.detection_history.append((plate, confidence))
        
        # Keep only recent detections
        if len(self.detection_history) > self.window_size:
            self.detection_history.pop(0)
    
    def get_consensus(self):
        """
        Get the consensus plate from aggregated detections.
        Returns: (plate, confidence) or (None, 0) if no consensus
        """
        if not self.detection_history:
            return None, 0.0
        
        # Count non-None detections
        valid_detections = [(p, c) for p, c in self.detection_history if p is not None]
        
        if not valid_detections:
            logger.debug('[AGGREGATE] No valid detections in window')
            return None, 0.0
        
        # Get most common plate
        plates = [p for p, _ in valid_detections]
        plate_counts = Counter(plates)
        most_common_plate, vote_count = plate_counts.most_common(1)[0]
        
        # Check if consensus threshold is met
        if vote_count < self.threshold:
            logger.debug(f'[AGGREGATE] Plate {most_common_plate} has {vote_count}/{self.threshold} votes (threshold not met)')
            return None, 0.0
        
        # Calculate average confidence for this plate
        confidences = [c for p, c in valid_detections if p == most_common_plate]
        avg_conf = np.mean(confidences)
        
        logger.info(f'[AGGREGATE] ✓ Consensus: {most_common_plate} ({vote_count}/{self.window_size} votes, conf={avg_conf:.2f})')
        return most_common_plate, avg_conf
    
    def is_new_plate(self):
        """Check if consensus plate is different from last confirmed"""
        consensus, conf = self.get_consensus()
        
        if consensus is None:
            return False
        
        if consensus != self.last_confirmed:
            self.last_confirmed = consensus
            self.confirmed_time = time.time()
            return True
        
        return False
    
    def reset(self):
        """Reset the aggregation window"""
        self.detection_history = []
        self.last_confirmed = None
        self.confirmed_time = None


# Global frame aggregator instance
frame_aggregator = FrameAggregator(window_size=5, threshold=3)

# Load model - CPU mode
MODEL_PATH = 'best.pt'
try:
    logger.info('[MODEL] Loading best.pt...')
    model = YOLO(MODEL_PATH)
    logger.info('[MODEL] ✓ Model loaded (CPU mode)')
except Exception as e:
    logger.warning(f'[MODEL] best.pt not found, loading YOLOv8n: {e}')
    model = YOLO('yolov8n.pt')
    logger.info('[MODEL] ✓ YOLOv8n loaded (CPU mode)')

# Initialize reader - CPU mode
logger.info('[OCR] Initializing EasyOCR reader...')
reader = easyocr.Reader(['en'], gpu=False)
logger.info('[OCR] ✓ Reader initialized')

def enhance_plate_image(plate_crop):
    """Enhanced preprocessing for better OCR"""
    try:
        # Convert to grayscale
        if len(plate_crop.shape) == 3:
            gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = plate_crop
        
        # Upscale if too small
        h, w = gray.shape
        if w < 200:
            scale_factor = max(2, 300 / w)
            gray = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor, 
                            interpolation=cv2.INTER_CUBIC)
        
        # Histogram equalization
        gray = cv2.equalizeHist(gray)
        
        # Denoise
        gray = cv2.fastNlMeansDenoising(gray, h=10)
        
        # Bilateral filter
        gray = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Contrast and brightness adjustment
        alpha = 1.5  # Contrast
        beta = 30    # Brightness
        gray = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
        
        # Thresholding - try multiple approaches
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        return binary
    except Exception as e:
        logger.error(f'[ENHANCE] Error: {e}')
        return plate_crop

def correct_ocr_text(raw_text):
    """
    Conservative OCR error correction based on Indian plate format
    Format: XX DD XX DDDD (state code, district, series, registration)
    Only fix obvious mistakes, NO aggressive character conversion
    """
    if not raw_text:
        return None
    
    # Remove spaces and convert to uppercase
    text = re.sub(r'\s+', '', raw_text.upper())
    
    # CONSERVATIVE: Only fix pipe and lowercase L to I
    text = text.replace('|', 'I')
    text = text.replace('l', 'I')
    
    # Remove non-alphanumeric
    text = re.sub(r'[^A-Z0-9]', '', text)
    
    # STRICT: Must be EXACTLY 10 characters
    if len(text) != 10:
        logger.debug(f'[CORRECT] Invalid length: {raw_text} (len={len(text)})')
        return None
    
    corrected = list(text)
    
    # Position-based STRICT validation (no conversions)
    try:
        # Positions 0,1: State code - MUST be LETTERS
        if not (corrected[0].isalpha() and corrected[1].isalpha()):
            logger.debug(f'[CORRECT] Invalid state at 0-1: {text}')
            return None
        
        # Positions 2,3: District - MUST be alphanumeric
        if not (corrected[2].isalnum() and corrected[3].isalnum()):
            logger.debug(f'[CORRECT] Invalid district at 2-3: {text}')
            return None
        
        # Positions 4,5: Series - MUST be LETTERS
        if not (corrected[4].isalpha() and corrected[5].isalpha()):
            logger.debug(f'[CORRECT] Invalid series at 4-5: {text}')
            return None
        
        # Positions 6-9: Registration - MUST be DIGITS
        if not all(corrected[i].isdigit() for i in [6, 7, 8, 9]):
            logger.debug(f'[CORRECT] Invalid registration at 6-9: {text}')
            return None
    
    except IndexError:
        return None
    
    result = ''.join(corrected)
    logger.debug(f'[CORRECT] ✓ Valid plate: {result}')
    return result

def recognize_plate_from_frame(frame_bgr, debug=False):
    """Optimized plate detection"""
    try:
        h, w = frame_bgr.shape[:2]
        
        # Resize for faster YOLO processing
        if max(h, w) > 1024:
            scale = 1024 / max(h, w)
            frame_resized = cv2.resize(frame_bgr, 
                (int(w*scale), int(h*scale)), 
                interpolation=cv2.INTER_LINEAR)
        else:
            frame_resized = frame_bgr
        
        img_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
    except Exception as e:
        logger.error(f'[FRAME] Error: {e}')
        return None

    # YOLO detection - Balanced confidence threshold (0.2 to catch plates)
    try:
        results = model(img_rgb, imgsz=640, conf=0.2, iou=0.4, verbose=False, device='cpu')
    except Exception as e:
        logger.error(f'[YOLO] Error: {e}')
        return None
    
    best_plate = None
    best_confidence = 0
    boxes_found = 0
    
    for r in results:
        if not hasattr(r, 'boxes') or r.boxes is None:
            continue
        
        for box in r.boxes:
            boxes_found += 1
            try:
                xyxy = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = [int(v) for v in xyxy]
                yolo_conf = float(box.conf[0].cpu().numpy())
            except Exception:
                continue

            # Scale back if needed
            if max(h, w) > 1024:
                sx = w / frame_resized.shape[1]
                sy = h / frame_resized.shape[0]
                x1, x2 = int(x1 * sx), int(x2 * sx)
                y1, y2 = int(y1 * sy), int(y2 * sy)

            # Clamp to frame bounds
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w-1, x2), min(h-1, y2)
            
            if x2 <= x1 or y2 <= y1:
                continue
            
            plate_crop = frame_bgr[y1:y2, x1:x2]
            
            # Minimum size check (more lenient)
            if plate_crop.shape[0] < 15 or plate_crop.shape[1] < 40:
                continue
            
            # Enhance and OCR
            enhanced = enhance_plate_image(plate_crop)
            
            try:
                # Stricter: require min confidence 0.3
                ocr_results = reader.readtext(enhanced, detail=1)
            except Exception as e:
                logger.error(f'[OCR] Error: {e}')
                continue
            
            if not ocr_results:
                logger.debug('[OCR] No text detected')
                continue
            
            # Filter by confidence threshold
            texts = []
            confidences = []
            
            for (bbox, text, conf) in ocr_results:
                text = text.strip()
                if text and len(text) > 0 and conf >= 0.2:
                    texts.append(text)
                    confidences.append(conf)
            
            if not texts:
                logger.debug('[OCR] All results filtered (conf < 0.2)')
                continue
            
            full_text = ''.join(texts)
            avg_ocr_conf = np.mean(confidences) if confidences else 0.2
            
            # More forgiving: require average OCR confidence >= 0.3
            if avg_ocr_conf < 0.3:
                logger.debug(f'[OCR] Low avg conf {avg_ocr_conf:.2f}')
                continue
            
            # Correct OCR errors (conservative)
            corrected = correct_ocr_text(full_text)
            
            if not corrected:
                logger.debug(f'[DETECT] Correction failed for: {full_text}')
                continue
            
            # Combined confidence - more forgiving
            combined_conf = (yolo_conf * 0.4) + (avg_ocr_conf * 0.6)
            
            # More forgiving: require combined confidence >= 0.35
            if combined_conf < 0.35:
                logger.debug(f'[DETECT] Low combined conf {combined_conf:.2f}')
                continue
            
            if debug:
                logger.info(f'[CANDIDATE] Raw: {full_text} → {corrected} (YOLO: {yolo_conf:.2f}, OCR: {avg_ocr_conf:.2f}, Combined: {combined_conf:.2f})')
            
            if combined_conf > best_confidence:
                best_plate = corrected
                best_confidence = combined_conf
    
    if best_plate:
        logger.info(f'[✓ DETECTION] Plate: {best_plate} (Confidence: {best_confidence:.2f}) [Found {boxes_found} boxes]')
    else:
        if boxes_found > 0:
            logger.debug(f'[DETECTION] Found {boxes_found} boxes but no valid plate detected')
        else:
            logger.debug('[DETECTION] No plate boxes detected in frame')
    
    return best_plate


def recognize_plate_with_aggregation(frame_bgr, debug=False):
    """
    Detect plate from frame with frame aggregation voting.
    Requires 3 out of 5 consecutive frames to confirm a plate.
    
    Returns: (plate, is_new_detection)
    """
    # Get detection from current frame
    plate = recognize_plate_from_frame(frame_bgr, debug=debug)
    
    # Add to aggregation window
    confidence = 1.0 if plate else 0.0
    frame_aggregator.add_detection(plate, confidence)
    
    # Check for consensus
    if frame_aggregator.is_new_plate():
        consensus_plate, _ = frame_aggregator.get_consensus()
        logger.info(f'[AGGREGATION] New plate confirmed: {consensus_plate}')
        return consensus_plate, True
    else:
        consensus_plate, _ = frame_aggregator.get_consensus()
        if consensus_plate:
            logger.debug(f'[AGGREGATION] Ongoing detection: {consensus_plate}')
        return consensus_plate, False

def process_image_batch(image_paths):
    """Process multiple images for testing"""
    results = []
    for img_path in image_paths:
        logger.info(f'\n[TEST] Processing: {img_path}')
        img = cv2.imread(img_path)
        if img is None:
            logger.error(f'[TEST] Cannot read: {img_path}')
            results.append({'image': img_path, 'plate': None})
            continue
        
        plate = recognize_plate_from_frame(img, debug=True)
        results.append({
            'image': img_path,
            'plate': plate
        })
        
        logger.info(f'[TEST] Result: {plate}\n')
    
    return results

def get_plate_with_metadata(frame_bgr):
    plate = recognize_plate_from_frame(frame_bgr)
    if plate:
        return {
            'plate': plate,
            'timestamp': datetime.now().isoformat(),
            'detected': True
        }
    return {
        'plate': None,
        'timestamp': datetime.now().isoformat(),
        'detected': False
    }

PLATE_CACHE = {}
CACHE_TIMEOUT = 30

def clear_old_cache():
    import time
    current_time = time.time()
    to_remove = []
    for plate, timestamp in PLATE_CACHE.items():
        if current_time - timestamp > CACHE_TIMEOUT:
            to_remove.append(plate)
    for plate in to_remove:
        del PLATE_CACHE[plate]

def process_video_realtime(video_source=0, callback=None, display=True):
    import time
    cap = cv2.VideoCapture(video_source)
    
    if not cap.isOpened():
        logger.error(f'[VIDEO] Cannot open: {video_source}')
        return False
    
    logger.info(f'[VIDEO] Starting real-time from: {video_source}')
    
    frame_counter = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(1)
                continue
            
            frame_counter += 1
            
            if frame_counter % 3 == 0:
                clear_old_cache()
                plate = recognize_plate_from_frame(frame)
                
                if plate and plate not in PLATE_CACHE:
                    PLATE_CACHE[plate] = time.time()
                    logger.info(f'[VIDEO] Detected: {plate}')
                    
                    if callback:
                        callback(plate, frame)
            
            if display and cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    except KeyboardInterrupt:
        logger.info('[VIDEO] Interrupted')
    finally:
        cap.release()
        if display:
            cv2.destroyAllWindows()
    
    return True