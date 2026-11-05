"""Render per-tile detections back onto the frame to verify alignment."""
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.cv import mosaic  # noqa: E402
from app.cv.detector import Detector  # noqa: E402


def main():
    video = sys.argv[1]
    at = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
    out = sys.argv[3] if len(sys.argv) > 3 else "mosaic_check.jpg"

    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_MSEC, at * 1000)
    ok, frame = cap.read()
    cap.release()
    assert ok, "could not read frame"

    grid = mosaic.detect_mosaic(frame)
    assert grid, "not detected as a mosaic"
    det = Detector("yolo26n.pt", 0.25, 640, "auto")
    tiles = mosaic.extract_tiles(frame, grid)
    per_tile = det.detect_many(tiles)

    vis = frame.copy()
    total = 0
    for idx, (cell, td) in enumerate(zip(mosaic.tile_starts(grid), per_tile)):
        mapped = mosaic.map_to_frame(td, cell)
        total += len(mapped)
        for x1, y1, x2, y2, c in mapped:
            cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 1)
        x0, y0, tw, th = cell
        cv2.putText(vis, f"CAM{idx+1}:{len(mapped)}", (x0 + 3, y0 + 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1, cv2.LINE_AA)

    for r in range(grid["rows"]):
        for c in range(grid["cols"]):
            cv2.rectangle(vis, (grid["xs"][c], grid["ys"][r]),
                          (grid["xs"][c + 1], grid["ys"][r + 1]), (60, 60, 60), 1)
    cv2.imwrite(out, vis)
    print(f"total {total} detections at t={at}s -> {out}")
    print("per camera:", [len(x) for x in per_tile])


if __name__ == "__main__":
    main()
