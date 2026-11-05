"""Does auto-tiling stay OFF for normal single-camera footage?

Run: python tests/test_auto_tile_real.py
Prints measured person height and the chosen grid per demo clip.
"""
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.cv.detector import Detector  # noqa: E402
from app.cv.pipeline import _auto_tile_grid  # noqa: E402

VIDEOS = Path(__file__).resolve().parents[2] / "data" / "videos_demo"


def main():
    det = Detector("yolo26n.pt", 0.25, 640, "auto")
    print(f"{'clip':42} {'person px':>9} {'grid':>5}")
    results = []
    for p in sorted(VIDEOS.glob("*.mp4")):
        if p.stem.startswith("yt_"):
            continue  # long-form clips are measured by their own runs
        cap = cv2.VideoCapture(str(p))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        grid = _auto_tile_grid(det, cap, n, fps, 3, int(cap.get(3)), h)
        px = getattr(_auto_tile_grid, "last_person_px", None)
        cap.release()
        results.append((p.name, px, grid))
        print(f"{p.name:42} {str(px):>9} {grid:>5}")

    triggered = [r for r in results if r[2] > 1]
    print(f"\nclips: {len(results)}, tiling triggered on {len(triggered)}")
    if triggered:
        print("triggered:", [r[0] for r in triggered])
    print("\nALL NORMAL CLIPS UNTILED (good)" if not triggered
          else "\nSOME NORMAL CLIPS TILED (check whether that is justified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
