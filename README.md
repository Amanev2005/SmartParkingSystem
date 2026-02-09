# Smart Parking System (YOLOv8 + EasyOCR)

This project detects license plates using YOLOv8 and reads them with EasyOCR,
allocating parking slots and calculating charges via a Flask backend.

## Quickstart

1. Create virtualenv and install requirements:

   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\\Scripts\\activate
   pip install -r requirements.txt
   ```

2. Initialize DB:

   ```bash
   python init_db.py
   ```

3. Start Flask backend:

   ```bash
   python app.py
   ```

4. Start webcam capture in another terminal:

   ```bash
   python camera_capture.py
   ```

## Notes
- Put a trained YOLOv8 plate-detection model named `best_lp.pt` in the project folder for best results.
- You can use Google Colab (GPU) to train a custom model and then download `best_lp.pt`.
