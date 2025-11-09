# ...existing code...
import cv2
import time
import requests
import threading
import queue
from anpr_yolo_easyocr import recognize_plate_from_frame

API_ENTRY = 'http://localhost:5000/api/entry'
API_EXIT = 'http://localhost:5000/api/exit'

recent_plates = {}  # plate -> (last_seen_ts, last_action)
COOLDOWN_SECONDS = 10

FRAME_QUEUE_MAX = 2
PROCESS_EVERY_N = 3        # process every 3rd captured frame (tune)
DISPLAY_UPDATE_EVERY = 3   # update displayed frame this often

# ...existing code...
def _open_capture(source="http://192.168.100.166:8080/video"):
    """
    Try multiple backends depending on source type.
    - For string URLs (http/rtsp) prefer FFMPEG/ANY.
    - For numeric device indices prefer DirectShow/MSMF/ANY.
    Returns an opened cv2.VideoCapture or None.
    """
    is_url = isinstance(source, str)
    backends = []

    if is_url:
        # prefer FFMPEG when available for network streams
        for api in (getattr(cv2, 'CAP_FFMPEG', cv2.CAP_ANY), cv2.CAP_ANY):
            backends.append(api)
    else:
        # local camera: try DirectShow first on Windows, then MSMF, then any
        for api in (getattr(cv2, 'CAP_DSHOW', cv2.CAP_ANY),
                    getattr(cv2, 'CAP_MSMF', cv2.CAP_ANY),
                    cv2.CAP_ANY):
            backends.append(api)

    for api in backends:
        try:
            cap = cv2.VideoCapture(source, api) if api is not None else cv2.VideoCapture(source)
        except Exception:
            cap = None

        if cap is None:
            continue
        # Give OpenCV a short moment to initialize backend
        time.sleep(0.2)
        if cap.isOpened():
            # Only set resolution for local device indices (numeric)
            try:
                if not is_url:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 720)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            except Exception:
                pass
            return cap
        try:
            cap.release()
        except Exception:
            pass

    return None
# ...existing code...

def _worker_process(q: queue.Queue, stop_event: threading.Event):
    processed_counter = 0
    while not stop_event.is_set():
        try:
            frame = q.get(timeout=0.5)
        except queue.Empty:
            continue
        processed_counter += 1
        if processed_counter % PROCESS_EVERY_N != 0:
            continue
        plate = recognize_plate_from_frame(frame)
        if plate:
            now = time.time()
            last_ts, last_action = recent_plates.get(plate, (0, None))
            if now - last_ts > COOLDOWN_SECONDS:
                try:
                    resp = requests.post(API_ENTRY, data={'plate': plate}, timeout=5)
                    j = resp.json()
                    if not j.get('success'):
                        resp2 = requests.post(API_EXIT, data={'plate': plate}, timeout=5)
                        print('Tried exit:', resp2.status_code, resp2.text)
                        recent_plates[plate] = (now, 'exit')
                    else:
                        print('Entry registered:', j)
                        recent_plates[plate] = (now, 'entry')
                except Exception as e:
                    print('API error:', e)

def main_loop(source=0, show_window=True):
    cap = _open_capture(source)
    if not cap:
        raise RuntimeError(f'Could not open capture source={source}')

    q = queue.Queue(maxsize=FRAME_QUEUE_MAX)
    stop_event = threading.Event()
    worker = threading.Thread(target=_worker_process, args=(q, stop_event), daemon=True)
    worker.start()

    disp_counter = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print('[WARN] Could not grab frame. Reopening...')
                cap.release()
                time.sleep(1.0)
                cap = _open_capture(source)
                if not cap:
                    time.sleep(2.0)
                    continue
                continue

            # only keep latest frames to avoid backlog
            if not q.full():
                q.put(frame.copy())
            else:
                try:
                    _ = q.get_nowait()  # drop oldest
                    q.put(frame.copy())
                except Exception:
                    pass

            if show_window:
                disp_counter += 1
                if disp_counter % DISPLAY_UPDATE_EVERY == 0:
                    cv2.imshow('Camera', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
    finally:
        stop_event.set()
        worker.join(timeout=1.0)
        try:
            cap.release()
        except Exception:
            pass
        cv2.destroyAllWindows()

# ...existing code...
if __name__ == '__main__':
    # for IP camera use the stream url as source, e.g. "http://192.168.100.166:8080/video"
    main_loop(source="http://192.168.100.166:8080/video")
# ...existing code...