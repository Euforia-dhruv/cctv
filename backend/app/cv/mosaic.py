"""Camera-wall (mosaic) detection.

Many CCTV exports are a grid of cameras in one frame (e.g. 4x4). Running the
detector once on the whole grid makes people ~10x smaller than the model wants,
so we split the frame into per-camera tiles, detect on each, and map the boxes
back to frame coordinates. Detected from the footage itself, never assumed.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

MIN_CELL_PX = 64          # below this a tile is hopeless for detection
MAX_CELLS_PER_AXIS = 8
TILE_UPSCALE = 4          # tile -> detector input size


def _dark_lines(profile: np.ndarray, limit: int = 12) -> List[int]:
    """Indices of near-black separator lines in a brightness profile."""
    thr = max(8.0, float(np.median(profile)) * 0.30)
    dark = profile < thr
    groups: List[List[int]] = []
    cur: List[int] = []
    for i, d in enumerate(dark):
        if d:
            cur.append(i)
        elif cur:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return [int(round(np.mean(g))) for g in groups if len(g) <= limit]


CANDIDATES = [(2, 2), (2, 3), (3, 3), (2, 4), (4, 4), (3, 4), (4, 5), (5, 5),
              (3, 6), (6, 6), (4, 8), (8, 8)]

LINE_DARK = 30.0        # separator pixels are near-black
LINE_COVERAGE = 0.92    # a real separator runs the full width/height


def _line_coverage(gray: np.ndarray, pos: int, axis: int) -> float:
    """Fraction of a separator line that is near-black.

    Takes the darkest value within a +/-3px band so a 1px line at an uneven
    position still registers as fully covered."""
    h, w = gray.shape
    if axis == 0:
        band = gray[:, max(0, pos - 3):min(w, pos + 4)]
        line = band.min(axis=1) if band.size else band
    else:
        band = gray[max(0, pos - 3):min(h, pos + 4), :]
        line = band.min(axis=0) if band.size else band
    if line.size == 0:
        return 0.0
    return float((line < LINE_DARK).mean())


def _grid_coverage(gray: np.ndarray, rows: int, cols: int) -> float:
    """Mean coverage of every internal separator a (rows,cols) grid implies."""
    h, w = gray.shape
    vals = []
    if cols >= 2:
        for i in range(1, cols):
            vals.append(_line_coverage(gray, round(i * w / cols), 0))
    if rows >= 2:
        for i in range(1, rows):
            vals.append(_line_coverage(gray, round(i * h / rows), 1))
    return sum(vals) / len(vals) if vals else 0.0


def detect_mosaic(frame: np.ndarray) -> Optional[dict]:
    """Return {'rows','cols','xs','ys'} if the frame is a camera wall, else None.

    Uses separator-line coverage: divider lines are near-black for their whole
    length. Picks the FINEST grid that passes, so a 4x4 wall is not mis-read as
    2x2 (which also has real dividers, just fewer of them)."""
    if frame is None or frame.size == 0:
        return None
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    passing = []
    for rows, cols in CANDIDATES:
        if w / cols < MIN_CELL_PX or h / rows < MIN_CELL_PX:
            continue
        cov = _grid_coverage(gray, rows, cols)
        if cov >= LINE_COVERAGE:
            passing.append((rows * cols, rows, cols, cov))
    if not passing:
        return None
    _, rows, cols, cov = max(passing)
    # separators sit between cells; nudge cuts to the darkest row/col nearby
    xs = [0] + [_snap_dark(gray, round(i * w / cols), 0) for i in range(1, cols)] + [w]
    ys = [0] + [_snap_dark(gray, round(i * h / rows), 1) for i in range(1, rows)] + [h]
    return {"rows": rows, "cols": cols, "xs": xs, "ys": ys, "score": round(cov, 3)}


def _snap_dark(gray: np.ndarray, pos: int, axis: int, reach: int = 5) -> int:
    """Nearest separator position: highest line coverage, ties broken by darkness."""
    h, w = gray.shape
    span = w if axis == 0 else h
    best_cov, cands = -1.0, []
    for p in range(max(1, pos - reach), min(span - 1, pos + reach + 1)):
        v = _line_coverage(gray, p, axis)
        if v > best_cov:
            best_cov, cands = v, [p]
        elif v == best_cov:
            cands.append(p)
    # a +/-3px band makes neighbours tie; pick the darkest of the tied positions
    return min(cands, key=lambda p: float(gray[:, p].mean() if axis == 0
                                          else gray[p, :].mean()))


def detect_mosaic_multiframe(frames: List[np.ndarray]) -> Optional[dict]:
    """Vote across several frames. Dark or busy scenes make a single frame
    unreliable (a quiet camera can hide its separator line), so the wall is
    confirmed when the same grid appears in most frames."""
    votes: dict = {}
    first = None
    for f in frames:
        spec = detect_mosaic(f)
        if not spec:
            continue
        key = (spec["rows"], spec["cols"])
        votes[key] = votes.get(key, 0) + 1
        if first is None:
            first = spec
    if not votes:
        return None
    key, n = max(votes.items(), key=lambda kv: kv[1])
    if n < max(2, len(frames) // 2):
        return None
    return {"rows": key[0], "cols": key[1],
            "xs": first["xs"], "ys": first["ys"],
            "score": first.get("score", 0.0)}


def sliding_tiles(frame: np.ndarray, n: int,
                  overlap: float = 0.15) -> List[Tuple[np.ndarray, Tuple[int, int, int, int]]]:
    """NxN overlapping crops for small-object detection on a single view.

    Returns (crop, (x0, y0, w, h)) pairs, upscaled so a distant person reaches a
    size the detector can see. Overlap stops a person on a seam being cut in two."""
    h, w = frame.shape[:2]
    tw, th = int(w / n), int(h / n)
    ox, oy = int(tw * overlap), int(th * overlap)
    out = []
    for r in range(n):
        for c in range(n):
            x0 = max(0, c * tw - ox)
            y0 = max(0, r * th - oy)
            x1 = min(w, x0 + tw + 2 * ox)
            y1 = min(h, y0 + th + 2 * oy)
            crop = frame[y0:y1, x0:x1]
            if crop.size == 0:
                continue
            up = cv2.resize(crop, (crop.shape[1] * TILE_UPSCALE,
                                   crop.shape[0] * TILE_UPSCALE),
                            interpolation=cv2.INTER_CUBIC)
            out.append((up, (x0, y0, x1 - x0, y1 - y0)))
    return out


def merge_boxes(boxes: List[Tuple[float, float, float, float, float]],
                iou_thresh: float = 0.55) -> List[Tuple[float, float, float, float, float]]:
    """Drop duplicates produced where overlapping tiles both saw the same person.

    Keeps the highest-confidence box. NMS by IoU is enough here because the boxes
    being merged come from the same detector on the same pixels."""
    kept: List[Tuple[float, float, float, float, float]] = []
    for box in sorted(boxes, key=lambda b: b[4], reverse=True):
        if all(_iou(box, k) <= iou_thresh for k in kept):
            kept.append(box)
    return kept


def _iou(a, b) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, x2 - x1), max(0.0, y2 - y1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def tile_starts(spec: dict) -> List[Tuple[int, int, int, int]]:
    """(x0, y0, w, h) for every cell, inset to skip separator lines."""
    xs, ys = spec["xs"], spec["ys"]
    out = []
    for r in range(spec["rows"]):
        for c in range(spec["cols"]):
            x0, x1 = xs[c], xs[c + 1]
            y0, y1 = ys[r], ys[r + 1]
            # drop the 2px border so black lines do not become detection context
            x0, y0 = min(x0 + 2, x1 - 1), min(y0 + 2, y1 - 1)
            out.append((x0, y0, max(1, x1 - x0 - 2), max(1, y1 - y0 - 2)))
    return out


def extract_tiles(frame: np.ndarray, spec: dict,
                  upscale: int = TILE_UPSCALE) -> List[np.ndarray]:
    """Crop each camera and upscale it so people are detector-sized."""
    tiles = []
    for x0, y0, tw, th in tile_starts(spec):
        t = frame[y0:y0 + th, x0:x0 + tw]
        tiles.append(cv2.resize(t, (tw * upscale, th * upscale),
                                interpolation=cv2.INTER_CUBIC))
    return tiles


def map_to_frame(dets: List[Tuple[float, float, float, float, float]],
                 cell: Tuple[int, int, int, int],
                 upscale: int = TILE_UPSCALE) -> List[Tuple[float, float, float, float, float]]:
    """Tile-space detections -> full-frame coordinates."""
    x0, y0 = cell[0], cell[1]
    return [(x0 + x1 / upscale, y0 + y1 / upscale,
             x0 + x2 / upscale, y0 + y2 / upscale, c)
            for x1, y1, x2, y2, c in dets]
