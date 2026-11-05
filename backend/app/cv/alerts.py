"""Event generation. Everything here is a heuristic and every output is meant
for human review. We never label a person as a threat; labels are neutral
("review required", "possible ..."). Unsupported detections are absent, not faked."""
from __future__ import annotations

from typing import Dict, List

import cv2
import numpy as np

from .tracker import Track
from .zones import Zone

MIN_BLOB_AREA_RATIO = 0.004
MAX_BLOB_AREA_RATIO = 0.25
BLOB_MIN_AGE_S = 6.0
# Above this many people in view, foreground-blob heuristics are unreliable.
CROWD_PEOPLE = 8


class AlertsEngine:
    """Runs on sampled frames; detects persistent foreground blobs that are not
    persons (experimental spill/debris/unattended-object detector)."""

    def __init__(self, width: int, height: int, fps: float):
        self.w, self.h, self.fps = width, height, fps
        self.sub = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=20,
                                                      detectShadows=True)
        self._blobs: Dict[int, dict] = {}
        self._next_blob = 1
        self.events: List[dict] = []
        self._emitted = set()
        self.crowd_frames = 0
        self.frames_seen = 0

    def on_frame(self, frame: np.ndarray, dets: List, t: float):
        self.frames_seen += 1
        # Background subtraction cannot separate a dropped bag from a crowd of
        # people: in a busy scene it reports people as "blobs" and floods the
        # review queue with false unattended-object/debris events. Measured on a
        # crowded mall atrium, this produced 274 false events out of 280. So the
        # blob heuristics only run while the scene is genuinely quiet.
        if len(dets) >= CROWD_PEOPLE:
            self.crowd_frames += 1
            self._blobs.clear()
            return
        mask = self.sub.apply(frame)
        mask = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)[1]
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        mask = cv2.dilate(mask, np.ones((5, 5), np.uint8))
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_area = self.w * self.h * MIN_BLOB_AREA_RATIO
        max_area = self.w * self.h * MAX_BLOB_AREA_RATIO
        seen = set()
        for c in cnts:
            area = cv2.contourArea(c)
            if area < min_area or area > max_area:
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            cx, cy = x + bw / 2, y + bh / 2
            if cy < self.h * 0.10 or cy > self.h * 0.92:
                continue
            # Skip blobs covered by a detected person.
            if any(_blob_covered(cx, cy, bw, bh, d) for d in dets):
                continue
            best_id, best_d = None, 1e9
            for bid, b in self._blobs.items():
                d = ((b["cx"] - cx) ** 2 + (b["cy"] - cy) ** 2) ** 0.5
                if d < best_d:
                    best_d, best_id = d, bid
            if best_id is not None and best_d < self.w * 0.06:
                b = self._blobs[best_id]
                b.update(cx=cx, cy=cy, area=area, last_t=t, w=bw, h=bh)
                seen.add(best_id)
                if t - b["born_t"] >= BLOB_MIN_AGE_S and b["emit_id"] not in self._emitted:
                    self._emitted.add(b["emit_id"])
                    if cy > self.h * 0.5:
                        self._push("operational", "debris", "Possible debris or spill on floor (experimental)",
                                   b["born_t"] + 0.5, 0.4, {"blob_area": int(area), "x": int(cx), "y": int(cy)})
                    else:
                        self._push("operational", "unattended", "Unattended object (experimental)",
                                   b["born_t"] + 0.5, 0.4, {"blob_area": int(area), "x": int(cx), "y": int(cy)})
            else:
                self._blobs[self._next_blob] = {
                    "cx": cx, "cy": cy, "area": area, "born_t": t, "last_t": t,
                    "w": bw, "h": bh, "emit_id": self._next_blob}
                self._next_blob += 1
        # expire
        dead = [k for k, b in self._blobs.items() if t - b["last_t"] > 10 and k not in seen]
        for k in dead:
            self._blobs.pop(k, None)

    def _push(self, type_, subtype, label, ts, conf, evidence):
        self.events.append({"type": type_, "subtype": subtype, "label": label,
                            "ts_s": float(ts), "confidence": conf, "evidence_json": evidence})


def _blob_covered(cx, cy, bw, bh, det) -> bool:
    x1, y1, x2, y2 = det[0], det[1], det[2], det[3]
    if x1 <= cx <= x2 and y1 <= cy <= y2:
        return True
    inter_w = max(0, min(x2, cx + bw / 2) - max(x1, cx - bw / 2))
    inter_h = max(0, min(y2, cy + bh / 2) - max(y1, cy - bh / 2))
    return inter_w * inter_h > 0.3 * bw * bh


def analyze_tracks(tracks: List[Track], zones: List[Zone], cfg: dict) -> List[dict]:
    """Security/operational events derived from track motion."""
    events: List[dict] = []
    restricted = [z for z in zones if z.kind == "restricted"]

    for trk in tracks:
        if trk.hits < 3:
            continue
        # Restricted zone entry.
        for z in restricted:
            for ts, cx, cy in trk.path:
                if z.contains((cx, cy)):
                    events.append({"type": "security", "subtype": "restricted_zone",
                                   "label": f"Restricted zone entry detected ({z.name})",
                                   "ts_s": float(ts), "confidence": 0.7,
                                   "evidence_json": {"zone": z.name, "track": trk.id}})
                    break
        # Unusual movement: sustained high speed.
        speeds = []
        for i in range(1, len(trk.path)):
            dt = trk.path[i][0] - trk.path[i - 1][0]
            if dt <= 0:
                continue
            dx = trk.path[i][1] - trk.path[i - 1][1]
            dy = trk.path[i][2] - trk.path[i - 1][2]
            speeds.append(((dx ** 2 + dy ** 2) ** 0.5) / dt)
        if speeds:
            fast = sum(1 for s in speeds if s > cfg["unusual_speed_px"])
            if len(speeds) >= 5 and fast >= 0.6 * len(speeds):
                events.append({"type": "security", "subtype": "unusual_movement",
                               "label": "Unusual movement pattern (review required)",
                               "ts_s": trk.path[0][0], "confidence": 0.45,
                               "evidence_json": {"track": trk.id, "peak_speed_px_s": round(max(speeds), 1)}})
        # Prolonged presence of a stationary person.
        if trk.dwell_s >= cfg["prolonged_presence_s"] and trk.stationary >= 0.6 * trk.hits:
            events.append({"type": "security", "subtype": "prolonged_presence",
                           "label": "Prolonged presence in view (review required)",
                           "ts_s": trk.born_t, "confidence": 0.5,
                           "evidence_json": {"track": trk.id, "dwell_s": round(trk.dwell_s, 1)}})
    return events


def detect_queue_congestion(tracks: List[Track], zones: List[Zone],
                            cfg: dict, width: int, height: int) -> List[dict]:
    """Queue heuristic: stationary people clustered together over time.
    Congestion: configured zone crowded over time. Both clearly approximations."""
    events: List[dict] = []
    if not tracks:
        return events

    t0 = min(t.born_t for t in tracks)
    t1 = max(t.last_t for t in tracks)
    step = 2.0
    cluster_dist = max(90.0, width * 0.08)
    min_people = cfg["queue_min_people"]
    min_dur = cfg["queue_min_duration_s"]
    queue_cluster = None
    queue_since = None

    t = t0
    while t <= t1:
        alive = [trk for trk in tracks if trk.born_t <= t <= trk.last_t]
        stationary = []
        for trk in alive:
            # position at time t by interpolation
            pt = _pos_at(trk, t)
            if pt is None:
                continue
            # stationary: low speed path
            if _speed_near(trk, t) < cfg["stationary_px"]:
                stationary.append((trk, pt))
        clusters = _cluster(stationary, cluster_dist)
        best = max(clusters, key=len) if clusters else []
        if len(best) >= min_people:
            if queue_cluster is None:
                queue_cluster = best
                queue_since = t
            elif len(best) > len(queue_cluster):
                queue_cluster = best
        else:
            if queue_cluster is not None and (t - queue_since) >= min_dur:
                events.append({"type": "queue", "subtype": "queue",
                               "label": f"Possible queue detected ({len(queue_cluster)} people)",
                               "ts_s": queue_since, "confidence": 0.4,
                               "evidence_json": {"people": len(queue_cluster),
                                                 "duration_s": round(t - queue_since, 1)}})
            queue_cluster = None

        # congestion per zone
        for z in zones:
            if z.kind not in ("display", "queue"):
                continue
            inzone = [p for _, p in stationary if z.contains(p)]
            if len(inzone) >= cfg["congestion_people"]:
                key = ("cong", z.id)
                if key not in _cong_state:
                    _cong_state[key] = t
            else:
                if key in _cong_state and (t - _cong_state[key]) >= cfg["congestion_min_duration_s"]:
                    events.append({"type": "congestion", "subtype": "congestion",
                                   "label": f"Congestion in zone {z.name}",
                                   "ts_s": _cong_state[key], "confidence": 0.5,
                                   "evidence_json": {"zone": z.name, "people": len(inzone)}})
                _cong_state.pop(key, None)
        t += step

    if queue_cluster is not None and (t1 - queue_since) >= min_dur:
        events.append({"type": "queue", "subtype": "queue",
                       "label": f"Possible queue detected ({len(queue_cluster)} people)",
                       "ts_s": queue_since, "confidence": 0.4,
                       "evidence_json": {"people": len(queue_cluster),
                                         "duration_s": round(t1 - queue_since, 1)}})
    return events


_cong_state: dict = {}


def _pos_at(trk: Track, t: float):
    path = trk.path
    if not path:
        return None
    if t <= path[0][0]:
        return (path[0][1], path[0][2])
    if t >= path[-1][0]:
        return (path[-1][1], path[-1][2])
    for i in range(1, len(path)):
        if path[i][0] >= t:
            t0, x0, y0 = path[i - 1]
            t1, x1, y1 = path[i]
            f = (t - t0) / max(t1 - t0, 1e-6)
            return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)
    return (path[-1][1], path[-1][2])


def _speed_near(trk: Track, t: float, window: float = 4.0) -> float:
    pts = [p for p in trk.path if abs(p[0] - t) <= window]
    if len(pts) < 2:
        return 0.0
    d = ((pts[-1][1] - pts[0][1]) ** 2 + (pts[-1][2] - pts[0][2]) ** 2) ** 0.5
    return d / max(pts[-1][0] - pts[0][0], 1e-6)


def _cluster(items: List[tuple], dist: float) -> List[List[tuple]]:
    clusters = []
    for it in items:
        placed = False
        for c in clusters:
            if any(((it[1][0] - o[1][0]) ** 2 + (it[1][1] - o[1][1]) ** 2) ** 0.5 < dist for o in c):
                c.append(it)
                placed = True
                break
        if not placed:
            clusters.append([it])
    return clusters
