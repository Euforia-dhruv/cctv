"""Quick scan: run detection+tracking on each demo clip to pick demo footage.
Run: python tests/scan_demo.py — CPU mode, sample_step=6."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.cv.detector import Detector      # noqa: E402
from app.cv.tracker import Tracker         # noqa: E402
import cv2                                 # noqa: E402

CLIP_DIR = "D:/New folder (2)/retailvision/data/videos_demo"
CLIPS = [os.path.join(CLIP_DIR, f) for f in sorted(os.listdir(CLIP_DIR))
         if f.endswith(".mp4")]

det = Detector("yolo26n.pt", conf=0.35, imgsz=640, device="auto")
print("device:", det.meta()["device"])

rows = []
for path in CLIPS:
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    tr = Tracker(max_lost=8)
    total_dets = 0
    t0 = time.perf_counter()
    step = 6
    for i in range(0, n, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, frame = cap.read()
        if not ok:
            break
        dets = det.detect(frame)
        total_dets += len(dets)
        tr.update(dets, i / fps)
    cap.release()
    fin = tr.finish()
    el = time.perf_counter() - t0
    tracks = len(fin)
    real = sum(1 for t in fin if t.hits > 2 and t.dwell_s > 2)
    rows.append((real, tracks, total_dets, os.path.basename(path), round(el, 1), round(n / fps, 1)))

rows.sort(reverse=True)
print(f"{'people':>6} {'tracks':>6} {'dets':>6}  file  (scan_s, dur_s)")
for r in rows:
    print(f"{r[0]:>6} {r[1]:>6} {r[2]:>6}  {r[3]}  ({r[4]}, {r[5]})")
