#!/usr/bin/env python
"""Quick test of plate detection"""
import logging
import cv2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Testing plate detection on 3 camera frames...")

try:
    from anpr_yolo_easyocr import recognize_plate_from_frame
    
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        logger.error("Camera not available")
        exit(1)
    
    detections = []
    
    for i in range(3):
        ret, frame = cap.read()
        if ret:
            plate = recognize_plate_from_frame(frame, debug=True)
            if plate:
                detections.append(plate)
                logger.info(f"Frame {i+1}: ✓ {plate}")
            else:
                logger.info(f"Frame {i+1}: No plate detected")
        else:
            logger.warning(f"Frame {i+1}: Failed to read")
    
    cap.release()
    
    if detections:
        logger.info(f"\n✓ Detection working - Found: {detections}")
    else:
        logger.warning("\n⚠ No plates detected in 3 frames")
        logger.info("Ensure camera is pointed at a license plate with good lighting")

except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
