"""Crop single cameras at native resolution and draw detections, enlarged.

This is how we judge whether per-camera detection is trustworthy on this
footage, rather than trusting aggregate counts.
"""
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.cv import mosaic  # noqa: E402
from app.cv.detector import Detector  # noqa: E402


def main():
    video, at, outdir = sys.argv[1], float(sys.argv[2]), Path(sys.argv[3])
    cams = [int(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else [1, 3, 12, 16]
    outdir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_MSEC, at * 1000)
    ok, frame = cap.read()
    cap.release()
    assert ok
    grid = mosaic.detect_mosaic(frame)
    assert grid

    det = Detector("yolo26n.pt", 0.35, 640, "auto")
    cells = mosaic.tile_starts(grid)
    for cam in cams:
        idx = cam - 1
        x0, y0, tw, th = cells[idx]
        tile = frame[y0:y0 + th, x0:x0 + tw]
        # detect on the same upscaled image the pipeline uses
        up = cv2.resize(tile, (tw * mosaic.TILE_UPSCALE, th * mosaic.TILE_UPSCALE),
                        interpolation=cv2.INTER_CUBIC)
        dets = det.detect(up)
        vis = up.copy()
        for x1, y1, x2, y2, c in dets:
            cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 1)
            cv2.putText(vis, f"{c:.2f}", (int(x1), max(10, int(y1) - 3)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1, cv2.LINE_AA)
        p = outdir / f"cam{cam:02d}.png"
        cv2.imwrite(str(p), vis)
        print(f"CAM {cam:02d}: native {tw}x{th}px -> {len(dets)} detections -> {p}")


if __name__ == "__main__":
    main()
