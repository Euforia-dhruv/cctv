"""Lightweight IoU tracker with constant-velocity prediction.

Design notes:
- Follows the ByteTrack association idea (IoU + motion gating) but is our own
  implementation: no ReID, no appearance model, license-clean (MIT-style here).
- IDs are temporary and anonymous per analysis; never reused across videos.
- Persons are tracked by bounding-box center; foot point = bottom center.
"""
from __future__ import annotations

from typing import List

from .detector import Det


class Track:
    __slots__ = ("id", "bbox", "cx", "cy", "vx", "vy", "hits", "misses",
                 "stationary", "path", "born_t", "last_t", "finalized", "cell")

    def __init__(self, tid: int, det: Det, t: float, cell: int | None = None):
        self.id = tid
        self.cell = cell
        self.bbox = (det[0], det[1], det[2], det[3])
        self.cx, self.cy = (det[0] + det[2]) / 2, (det[1] + det[3]) / 2
        self.vx = self.vy = 0.0
        self.hits = 1
        self.misses = 0
        self.stationary = 0
        self.path = [(t, self.cx, self.cy)]
        self.born_t = t
        self.last_t = t
        self.finalized = False

    def predicted_box(self, dt: float):
        cx, cy = self.cx + self.vx * dt, self.cy + self.vy * dt
        w, h = self.bbox[2] - self.bbox[0], self.bbox[3] - self.bbox[1]
        return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

    def foot(self):
        return self.cx, self.bbox[3]

    @property
    def dwell_s(self) -> float:
        return self.last_t - self.born_t


def iou(a: tuple, b: tuple) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


class Tracker:
    def __init__(self, iou_thresh: float = 0.30, max_lost: int = 8,
                 min_hits: int = 2, stationary_px: float = 8.0):
        self.iou_thresh = iou_thresh
        self.max_lost = max_lost
        self.min_hits = min_hits
        self.stationary_px = stationary_px
        self._tracks: List[Track] = []
        self._next_id = 1
        self.finalized: List[Track] = []
        self._last_frame_speed = {}
        self._last_t = 0.0

    def update(self, dets: List[Det], t: float, cell: int | None = None) -> List[Track]:
        """Match detections to tracks; returns the live (unfinalized) tracks.

        `cell` tags new tracks with a camera index; existing tracks keep theirs.
        A camera wall is many independent scenes, so the pipeline calls this once
        per frame with all cells' detections (use `update_multi`)."""
        if cell is None:
            return self.update_multi([(d, None) for d in dets], t)
        return self.update_multi([(d, cell) for d in dets], t)

    def update_multi(self, dets_by_cell: List[tuple], t: float) -> List[Track]:
        """One tracking step for all cameras at once.

        dets_by_cell: [(detection, cell_index), ...]. Association never crosses
        cells, so two people in different cameras can never share an identity.
        Missing a camera in a frame is normal (nobody there), so tracks expire
        only via `max_lost` consecutive misses, counted once per frame."""
        dets = [d for d, _ in dets_by_cell]
        cells = [c for _, c in dets_by_cell]
        if self._tracks:
            dt = max(t - self._last_t, 0.001)
        else:
            dt = 0.001
        # Predict, using each track's own time gap (it may have been missed).
        preds = [trk.predicted_box(max(t - trk.last_t, 0.001)) for trk in self._tracks]

        # Greedy IoU matching.
        matched = [False] * len(dets)
        used = [False] * len(self._tracks)
        matched_ids = set()
        for _ in range(max(len(dets), len(self._tracks))):
            best = (0.0, -1, -1)
            for i, det in enumerate(dets):
                if matched[i]:
                    continue
                for j, trk in enumerate(self._tracks):
                    if used[j]:
                        continue
                    # never associate across cameras: each tile is a separate scene
                    if trk.cell != cells[i]:
                        continue
                    s = iou(preds[j], (det[0], det[1], det[2], det[3]))
                    if s > best[0]:
                        best = (s, i, j)
            if best[0] < self.iou_thresh:
                break
            _, i, j = best
            matched[i] = True
            used[j] = True
            matched_ids.add(self._tracks[j].id)
            trk = self._tracks[j]
            d = dets[i]
            prev_cx, prev_cy = trk.cx, trk.cy
            trk_dt = max(t - trk.last_t, 0.001)
            trk.bbox = (d[0], d[1], d[2], d[3])
            trk.cx, trk.cy = (d[0] + d[2]) / 2, (d[1] + d[3]) / 2
            trk.vx = (trk.cx - prev_cx) / trk_dt
            trk.vy = (trk.cy - prev_cy) / trk_dt
            speed = ((trk.vx ** 2 + trk.vy ** 2) ** 0.5) * trk_dt
            trk.stationary += 1 if speed < self.stationary_px else 0
            trk.hits += 1
            trk.misses = 0
            trk.last_t = t
            trk.path.append((t, trk.cx, trk.cy))
            if len(trk.path) > 400:
                trk.path = trk.path[200:]

        # New tracks for unmatched detections.
        for i, det in enumerate(dets):
            if not matched[i]:
                self._tracks.append(Track(self._next_id, det, t, cells[i]))
                self._next_id += 1

        self._last_t = t

        # Expire lost tracks.
        alive = []
        for trk in self._tracks:
            if trk.id in matched_ids:
                alive.append(trk)
                continue
            trk.misses += 1
            if trk.misses > self.max_lost:
                self._finalize(trk)
            else:
                alive.append(trk)
        self._tracks = alive
        return [t for t in self._tracks if t.hits >= 1]

    def _finalize(self, trk: Track):
        if not trk.finalized:
            trk.finalized = True
            self.finalized.append(trk)

    def finish(self) -> List[Track]:
        for trk in self._tracks:
            self._finalize(trk)
        self._tracks = []
        self.finalized.sort(key=lambda t: t.born_t)
        return self.finalized
