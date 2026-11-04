"""Analysis pipeline: decode -> detect -> track -> analytics -> artifacts.

One video at a time. All heavy work happens here in the worker thread."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, List

import cv2

from ..utils import probe_video
from . import alerts
from .analytics import compute_analytics
from .detector import Detector
from .heatmap import build_heatmap, save_reference
from .tracker import Tracker
from .zones import Zone, zones_from_json

ProgressCb = Callable[[str, float], None]


class PipelineResult:
    def __init__(self):
        self.summary: dict = {}
        self.events: List[dict] = []
        self.tracks: List[dict] = []
        self.heatmap_path = ""
        self.reference_path = ""
        self.processed_frames = 0
        self.detected_frames = 0
        self.inference_device = ""
        self.inference_ms_avg = 0.0
        self.model_meta: dict = {}
        self.scene: dict = {}


def run_pipeline(video_path: str, cfg: dict, artifacts_dir: Path,
                 zones_json=None, progress: ProgressCb | None = None) -> PipelineResult:
    res = PipelineResult()
    alerts._cong_state.clear()

    meta = probe_video(video_path)
    width, height = meta["width"], meta["height"]
    fps = meta["fps"]
    n_frames = meta["frames"]

    detector = Detector(cfg["model"], cfg["conf"], cfg["imgsz"], cfg["device"])
    res.model_meta = detector.meta()
    tracker = Tracker(iou_thresh=cfg["iou_thresh"], max_lost=cfg["max_lost"],
                      min_hits=cfg["min_track_len"], stationary_px=cfg["stationary_px"])
    zones: List[Zone] = zones_from_json(zones_json)
    alert_engine = alerts.AlertsEngine(width, height, fps)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Could not open video.")
    step = max(1, int(cfg["sample_step"]))

    occupancy: List[tuple] = []
    reference = None
    analyzed = 0
    import time as _time
    inference_times = []
    motion_ratios: List[float] = []
    prev_gray = None

    for frame_idx in range(0, n_frames, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        if not ok:
            break
        t = frame_idx / fps
        if reference is None:
            reference = frame.copy()
            save_reference(reference, artifacts_dir / "reference.jpg")
            res.reference_path = str(artifacts_dir / "reference.jpg")

        # scene-suitability: rough global motion (camera pan/shake detection)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray)
            motion_ratios.append(float(cv2.mean(diff)[0] / 255.0))
        prev_gray = gray

        t0 = _time.perf_counter()
        dets = detector.detect(frame)
        inference_times.append((_time.perf_counter() - t0) * 1000)
        tracker.update(dets, t)
        alert_engine.on_frame(frame, dets, t)
        occupancy.append((t, len(dets)))
        analyzed += 1
        if dets:
            res.detected_frames += 1
        # thumbnails progress
        if progress and analyzed % 20 == 0:
            progress("analyzing", min(0.95, analyzed * step / n_frames))

    if motion_ratios:
        avg_motion = sum(motion_ratios) / len(motion_ratios)
        res.scene = {
            "avg_motion_ratio": round(avg_motion, 4),
            "max_motion_ratio": round(max(motion_ratios), 4),
            "moving_camera": avg_motion > 0.12,
        }

    cap.release()
    res.processed_frames = analyzed
    res.inference_device = detector.meta()["device"]
    res.inference_ms_avg = round(sum(inference_times) / len(inference_times), 2) if inference_times else 0.0

    tracks = tracker.finish()

    # Events from tracks + heuristics.
    events = alert_engine.events + alerts.analyze_tracks(tracks, zones, cfg)
    events += alerts.detect_queue_congestion(tracks, zones, cfg, width, height)
    events.sort(key=lambda e: e["ts_s"])

    # Thumbnails for events (seek capture again, memory-safe).
    cap = cv2.VideoCapture(video_path)
    for e in events:
        pos_ms = max(0, int(e["ts_s"] * 1000))
        cap.set(cv2.CAP_PROP_POS_MSEC, pos_ms)
        ok, frame = cap.read()
        if not ok:
            continue
        # draw boxes for confidence evidence: annotate persons from path? skip, keep raw
        thumb = frame
        p = artifacts_dir / f"event_{len(res.events):03d}.jpg"
        cv2.imwrite(str(p), thumb)
        e["thumb_path"] = str(p)
        res.events.append(e)
    cap.release()

    # Heatmap.
    hm = artifacts_dir / "heatmap.jpg"
    build_heatmap(tracks, cv2.imread(str(artifacts_dir / "reference.jpg")),
                  hm, cells=cfg["detector_heatmap_cells"])
    res.heatmap_path = str(hm)

    # Analytics.
    summary = compute_analytics(tracks, occupancy, zones, fps, width, height)
    res.summary = summary
    res.tracks = [_track_row(t) for t in tracks]
    return res


def _track_row(t) -> dict:
    xs = [p[1] for p in t.path]
    ys = [p[2] for p in t.path]
    return {
        "track_id": t.id,
        "first_seen_s": round(t.born_t, 2),
        "last_seen_s": round(t.last_t, 2),
        "dwell_s": round(t.dwell_s, 2),
        "avg_x": round(sum(xs) / len(xs), 1) if xs else 0,
        "avg_y": round(sum(ys) / len(ys), 1) if ys else 0,
        "min_x": round(min(xs), 1) if xs else 0,
        "min_y": round(min(ys), 1) if ys else 0,
        "max_x": round(max(xs), 1) if xs else 0,
        "max_y": round(max(ys), 1) if ys else 0,
        "path_json": t.path,
        "stationary_ratio": round(t.stationary / max(t.hits, 1), 2),
        "flagged": 0,
    }
