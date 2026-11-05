"""Detect mosaic grids (NxM camera wall) and measure tiled detection cost."""
import sys
import time

import cv2
import numpy as np


def read_at(path, t):
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, f = cap.read()
    cap.release()
    return f if ok else None


def grid_axes(gray, axis):
    """Find dark separator lines: near-zero mean brightness rows/cols."""
    prof = gray.mean(axis=axis)  # along the other axis
    thr = max(8.0, prof.mean() * 0.35)
    dark = prof < thr
    # group consecutive dark indices
    groups, cur = [], []
    for i, d in enumerate(dark):
        if d:
            cur.append(i)
        elif cur:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return [int(np.mean(g)) for g in groups if len(g) <= 12]


def main():
    path = sys.argv[1]
    times = [float(x) for x in sys.argv[2:]] or [30.0]
    for t in times:
        f = read_at(path, t)
        if f is None:
            print(f"t={t}: no frame")
            continue
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        h, w = g.shape
        cols = grid_axes(g, 0)
        rows = grid_axes(g, 1)
        print(f"t={t}s {w}x{h} dark verticals={cols} horizontals={rows}")
        if len(cols) == 3 and len(rows) == 3:
            print("  -> looks like a 4x4 mosaic")
            xs = [0] + cols + [w]
            ys = [0] + rows + [h]
            print("  cell sizes:", [(xs[i+1]-xs[i], ys[j+1]-ys[j])
                                    for j in range(4) for i in range(4)][:4])

    # Cost: 1 full pass vs 16 tiles.
    from ultralytics import YOLO
    m = YOLO("yolo26n.pt")
    f = read_at(path, times[0])
    h, w = f.shape[:2]
    th, tw = h // 4, w // 4

    for _ in range(2):
        m.predict(source=f, conf=0.25, imgsz=640, classes=[0], verbose=False)
    t0 = time.perf_counter()
    for _ in range(10):
        m.predict(source=f, conf=0.25, imgsz=640, classes=[0], verbose=False)
    full_ms = (time.perf_counter() - t0) / 10 * 1000

    tiles = [cv2.resize(f[r*th:(r+1)*th, c*tw:(c+1)*tw], (tw*4, th*4),
                        interpolation=cv2.INTER_CUBIC)
             for r in range(4) for c in range(4)]
    m.predict(source=tiles, conf=0.2, imgsz=640, classes=[0], verbose=False)
    t0 = time.perf_counter()
    m.predict(source=tiles, conf=0.2, imgsz=640, classes=[0], verbose=False)
    tiled_ms = (time.perf_counter() - t0) * 1000
    print(f"\nfull-frame pass: {full_ms:.0f} ms | 16-tile batch: {tiled_ms:.0f} ms "
          f"({tiled_ms/16:.0f} ms/tile)")


if __name__ == "__main__":
    main()
