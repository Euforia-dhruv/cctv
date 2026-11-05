"""Self-check for mosaic (camera-wall) detection.

Run: python tests/test_mosaic.py
Uses the downloaded demo clip if present, otherwise synthetic grids.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.cv import mosaic  # noqa: E402

YT = (Path(__file__).resolve().parents[2]
      / "data" / "videos_demo" / "yt_1cBjmb0rDoU.mp4")


def synthetic(rows, cols, size=(640, 360), seed=0):
    """Bright cells on a black background: a synthetic camera wall."""
    w, h = size
    frame = np.zeros((h, w, 3), np.uint8)
    rng = np.random.default_rng(seed)
    for r in range(rows):
        for c in range(cols):
            x0, x1 = round(c * w / cols) + 2, round((c + 1) * w / cols) - 2
            y0, y1 = round(r * h / rows) + 2, round((r + 1) * h / rows) - 2
            frame[y0:y1, x0:x1] = rng.integers(90, 200, 3)
    return frame


def check(name, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got} want {want}")
    return ok


def main():
    ok = True
    ok &= check("synthetic 4x4", _grid(mosaic.detect_mosaic(synthetic(4, 4))), (4, 4))
    ok &= check("synthetic 3x3", _grid(mosaic.detect_mosaic(synthetic(3, 3))), (3, 3))
    ok &= check("synthetic 2x2", _grid(mosaic.detect_mosaic(synthetic(2, 2))), (2, 2))
    # A flat frame with no dividers must NOT be a wall.
    flat = np.full((360, 640, 3), 120, np.uint8)
    ok &= check("flat frame", _grid(mosaic.detect_mosaic(flat)), None)

    # Real single-camera clips must not be misread as walls.
    singles = sorted((YT.parent).glob("*.mp4"))
    for p in singles:
        if p.stem.startswith("yt_"):
            continue
        cap = cv2.VideoCapture(str(p))
        okf, f = cap.read()
        cap.release()
        if okf:
            ok &= check(f"single view {p.name}", _grid(mosaic.detect_mosaic(f)), None)

    if YT.exists():
        cap = cv2.VideoCapture(str(YT))
        cap.set(cv2.CAP_PROP_POS_MSEC, 30_000)
        okf, f = cap.read()
        cap.release()
        ok &= check("real 4x4 wall", _grid(mosaic.detect_mosaic(f)), (4, 4))
        # tile geometry must cover the frame without gaps
        spec = mosaic.detect_mosaic(f)
        cells = mosaic.tile_starts(spec)
        ok &= check("tile count", len(cells), 16)
        ok &= check("all tiles non-empty", all(w > 0 and h > 0 for _, _, w, h in cells), True)

    # Motion detection must not call a still camera wall "moving", while a pan
    # must be caught. Both are regressions we already hit once.
    ok &= check("still wall is still", _motion(YT.parent / "yt_1cBjmb0rDoU.mp4", grid=True), False)
    ok &= check("still single view is still", _motion(YT.parent / "mall_23249_720.mp4"), False)
    ok &= check("panning camera is flagged", _motion_pan(), True)

    print("\nALL MOSAIC CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1

def _grid(spec):
    return (spec["rows"], spec["cols"]) if spec else None


def _motion(path, grid=False):
    """True if measure_motion() flags the clip as a moving camera."""
    from app.cv.pipeline import _sample_frames, measure_motion
    if not path.exists():
        return None
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    spec = (mosaic.detect_mosaic_multiframe(_sample_frames(cap, n, 30.0, 3))
            if grid else None)
    out = measure_motion(cap, n, spec).get("moving_camera")
    cap.release()
    return out


def _motion_pan(tmpdir=None):
    """Render a synthetic panning clip and confirm it is flagged as moving."""
    import tempfile
    from app.cv.pipeline import measure_motion
    rng = np.random.default_rng(0)
    base = cv2.GaussianBlur(rng.integers(0, 255, (360, 700, 3), dtype=np.uint8),
                            (9, 9), 0)
    path = Path(tempfile.gettempdir()) / "rv_pan_check.mp4"
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (640, 360))
    for i in range(60):
        vw.write(base[:, i:i + 640])
    vw.release()
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = measure_motion(cap, n, None).get("moving_camera")
    cap.release()
    try:
        path.unlink()
    except OSError:
        pass
    return out


if __name__ == "__main__":
    raise SystemExit(main())
