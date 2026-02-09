# Smart Parking System - Camera Detection Guide

## Problem: System Not Detecting Plates

The main issue is **camera connection failure**. Your IP webcam at `10.109.18.31:8080` is unreachable.

---

## Solutions

### Option 1: Use Local Webcam (EASIEST - Start Here)

If your computer has a built-in webcam or USB camera:

```bash
python camera_capture.py --local 0
```

**With display window:**
```bash
python camera_capture.py --local 0   # Shows live detection feed
```

**Headless mode (no window):**
```bash
python camera_capture.py --local 0 --no-display
```

---

### Option 2: Use IP Webcam (With Correct IP Address)

If you have an IP camera, you need the correct IP address:

#### Find Your IP Webcam Address

1. **Open IP Webcam App** on your phone/device
2. **Note the URL** - Usually looks like: `http://192.168.x.x:8080/video`
3. **Update the command:**

```bash
python camera_capture.py --url http://192.168.x.x:8080/video
```

**Example:**
```bash
python camera_capture.py --url http://192.168.1.100:8080/video
```

---

### Option 3: Multiple Camera Support

If you have multiple cameras, try different IDs:

```bash
python camera_capture.py --local 0    # Default/Built-in camera
python camera_capture.py --local 1    # External USB camera
python camera_capture.py --local 2    # Another camera
```

---

## Testing Your Setup

Before running full system, test the camera:

```bash
python test_local_camera.py
```

This will:
- ✓ Check if camera is connected
- ✓ Test plate detection on live feed
- ✓ Show detection results

---

## Troubleshooting

### "Cannot open camera" Error

**Solution 1:** Check camera is connected
```bash
# Windows - See connected devices
Get-PnpDevice -Class Camera
```

**Solution 2:** Try different camera ID
```bash
python camera_capture.py --local 1
python camera_capture.py --local 2
```

### "No plates detected" 

Ensure:
- ✓ Good lighting (not too dark)
- ✓ License plate clearly visible in frame
- ✓ Vehicle is in camera view
- ✓ Camera is focused properly

### IP Webcam Connection Fails

**Check IP is correct:**
```bash
ping 192.168.x.x
```

**Find IP using IP Webcam app settings:**
- Start IP Webcam on phone
- Note the URL
- Use that URL with camera_capture.py

---

## Full Command Examples

```bash
# Option 1: Local camera (easiest)
python camera_capture.py --local 0

# Option 2: IP camera with correct IP
python camera_capture.py --url http://192.168.1.100:8080/video

# Option 3: IP camera + display window
python camera_capture.py --url http://192.168.1.100:8080/video

# Option 4: Headless/background mode
python camera_capture.py --local 0 --no-display

# Option 5: Test before full run
python test_local_camera.py
```

---

## Controls (When Display Enabled)

- **Q** = Quit
- **S** = Save current frame

---

## What Happens During Detection

1. **Camera connects** - Streams video frames
2. **YOLO detects plates** - Uses AI to find license plates
3. **EasyOCR reads text** - Extracts plate numbers
4. **Confidence voting** - Requires 2+ detections to confirm
5. **API sends data** - Posts to Flask server
6. **Server processes** - Updates parking lot status

---

## System Status

✓ Flask API: Running on localhost:5000  
✓ YOLO Model: best.pt loaded  
✓ OCR Engine: EasyOCR ready  
⚠ Camera: **Need to specify --local or correct --url**

**Next step:** Run one of the commands above with YOUR camera details!

