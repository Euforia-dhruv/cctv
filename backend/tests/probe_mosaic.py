"""Does the detector actually see people in the YouTube mosaic?

Compares full-frame detection vs per-camera-tile crops.
Run: python tests/probe_mosaic.py <video> <frame_time_seconds>...
"""
import sys
import cv2
import numpy as np


def load(path, t):
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, f = cap.read()
    cap.release()
    return f if ok else None


def det(model, img, conf=0.25, imgsz=640):
    r = model.predict(source=img, conf=conf, imgsz=imgsz, classes=[0], verbose=False)[0]
    b = r.boxes
    if b is None or len(b) == 0:
        return []
    return [(tuple(map(float, xy)), float(c)) for xy, c in zip(b.xyxy.cpu().numpy(), b.conf.cpu().numpy())]


def main():
    path = sys.argv[1]
    times = [float(x) for x in sys.argv[2:]] or [30.0]
    from ultralytics import YOLO
    model = YOLO("yolo26n.pt")

    for t in times:
        f = load(path, t)
        if f is None:
            print(f"t={t}: frame read failed")
            continue
        h, w = f.shape[:2]
        full = det(model, f)
        print(f"\n=== t={t}s full frame {w}x{h} ===")
        print(f"  full-frame detections: {len(full)}")
        for (x1, y1, x2, y2), c in full[:6]:
            print(f"    box {x1:.0f},{y1:.0f}-{x2:.0f},{y2:.0f} "
                  f"({x2-x1:.0f}x{y2-y1:.0f}px) conf {c:.2f}")

        # 4x4 mosaic: crop each camera tile and upscale 4x before detection
        gh, gw = 4, 4
        th, tw = h // gh, w // gw
        total = 0
        for r in range(gh):
            for c in range(gw):
                tile = f[r*th:(r+1)*th, c*tw:(c+1)*tw]
                up = cv2.resize(tile, (tw*4, th*4), interpolation=cv2.INTER_CUBIC)
                d = det(model, up, conf=0.20, imgsz=640)
                if d:
                    total += len(d)
                    name = f"CAM {r*gw+c+1:02d}"
                    print(f"    {name}: {len(d)} det(s) "
                          f"max_conf={max(x[1] for x in d):.2f} tile={tw}x{th}px")
        print(f"  tiled per-camera detections: {total}")


if __name__ == "__main__":
    main()
