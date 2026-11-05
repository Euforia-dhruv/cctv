"""Analysis pipeline: decode -> detect -> track -> analytics -> artifacts.

One video at a time. All heavy work happens here in the worker thread."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, List

import cv2
import numpy as np

from ..utils import probe_video
from . import alerts, mosaic
from .analytics import compute_analytics
from .detector import Detector
from .heatmap import build_heatmap, save_reference
from .tracker import Tracker
from .zones import Zone, zones_from_json

ProgressCb = Callable[[str, float], None]

# Upper bound on analyzed frames for a camera wall (16 inferences per frame).
# 1800 frames = a 1-hour recording sampled every 2 s, about 5-6 minutes of
# processing on a laptop GPU. Coarser sampling (4 s+) fragments tracks.
MAX_MOSAIC_FRAMES = 1800

# Global image shift above this (pixels between consecutive frames) means the
# camera is panning, not that people are moving.
PAN_PX = 0.5


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
    # A camera wall costs one inference per camera per frame, so long recordings
    # would take hours. Keep processing time bounded; the sampling interval is
    # reported in the results and is honest about the lower time resolution.
    grid_probe = mosaic.detect_mosaic_multiframe(_sample_frames(cap, n_frames, fps, step))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    if grid_probe:
        max_frames = int(cfg.get("mosaic_max_frames") or MAX_MOSAIC_FRAMES)
        needed = max(1, -(-n_frames // step))
        if needed > max_frames:
            step = max(step, -(-n_frames // max_frames))
    grid_cfg = grid_probe

    occupancy: List[tuple] = []
    reference = None
    analyzed = 0
    import time as _time
    inference_times = []
    prev_gray = None
    grid = grid_cfg
    if grid:
        res.scene["mosaic"] = {"rows": grid["rows"], "cols": grid["cols"],
                               "cameras": grid["rows"] * grid["cols"]}

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
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

        # Scene-suitability: camera pan/shake is measured separately on a
        # consecutive-frame burst (see measure_motion), not on sampled frames.

        t0 = _time.perf_counter()
        if grid is not None:
            # Camera wall: detect per tile so small people are still found.
            per_tile = detector.detect_many(mosaic.extract_tiles(frame, grid))
            dets = []
            by_cell = []
            for idx, (cell, td) in enumerate(zip(mosaic.tile_starts(grid), per_tile)):
                mapped = mosaic.map_to_frame(td, cell)
                dets.extend(mapped)
                by_cell.extend((d, idx) for d in mapped)
            # One tracking step for the whole wall, so no camera's tracks are
            # expired just because a different camera was processed.
            tracker.update_multi(by_cell, t)
        else:
            dets = detector.detect(frame)
            tracker.update(dets, t)

        # Blob/object heuristics must not run across a camera wall.
        if grid is None:
            alert_engine.on_frame(frame, dets, t)
        inference_times.append((_time.perf_counter() - t0) * 1000)
        occupancy.append((t, len(dets)))
        analyzed += 1
        if dets:
            res.detected_frames += 1
        # thumbnails progress
        if progress and analyzed % 20 == 0:
            progress("analyzing", min(0.95, analyzed * step / n_frames))

    res.scene.update(measure_motion(cap, n_frames, grid))
    res.scene["sample_step"] = step
    res.scene["sample_interval_s"] = round(step / fps, 2) if fps else None

    cap.release()
    res.processed_frames = analyzed
    res.inference_device = detector.meta()["device"]
    res.inference_ms_avg = round(sum(inference_times) / len(inference_times), 2) if inference_times else 0.0

    tracks = tracker.finish()

    # Events from tracks + heuristics.
    events = alert_engine.events + alerts.analyze_tracks(tracks, zones, cfg)
    if grid is not None:
        # A camera wall is many independent scenes: cluster queues per camera so
        # people in unrelated cameras are never treated as one queue.
        by_cell: dict = {}
        for trk in tracks:
            by_cell.setdefault(trk.cell, []).append(trk)
        for cell_tracks in by_cell.values():
            events += alerts.detect_queue_congestion(cell_tracks, [], cfg, width, height)
        for e in events:
            e["evidence_json"] = dict(e.get("evidence_json") or {})
            e["evidence_json"]["scene"] = "camera wall"
    else:
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
    hm_ch, hm_cw = cfg["detector_heatmap_cells"]
    if grid:
        # 36x22 across a 4x4 wall gives each camera ~9x5 cells: mushy blobs.
        # Keep roughly the same detail per camera instead of per frame.
        hm_ch *= grid["cols"]
        hm_cw *= grid["rows"]
    build_heatmap(tracks, cv2.imread(str(artifacts_dir / "reference.jpg")),
                  hm, cells=(hm_ch, hm_cw), grid_spec=grid)
    res.heatmap_path = str(hm)

    # Analytics.
    summary = compute_analytics(tracks, occupancy, zones, fps, width, height)
    if grid:
        # A camera wall is many scenes; report per-camera counts alongside totals.
        summary["per_camera"] = _per_camera_counts(tracks, grid)
        # Honest data-quality signal: with sparse sampling, tracks break up.
        steps = [t["dwell_s"] for t in (_track_row(x) for x in tracks)]
        short = sum(1 for d in steps if d < max(1.0, 3 * step / fps))
        summary["track_quality"] = {
            "sample_interval_s": round(step / fps, 2) if fps else None,
            "short_track_ratio": round(short / len(steps), 2) if steps else None,
            "note": ("Tracks shorter than a few sample intervals usually mean the "
                     "sampling interval was too coarse for this footage; visit "
                     "counts are inflated and should be read as activity, not "
                     "headcount."),
        }
    res.summary = summary
    res.tracks = [_track_row(t) for t in tracks]
    return res


def _per_camera_counts(tracks, grid) -> list:
    """Visits per camera tile. A person moving between cameras cannot be
    re-identified without ReID, so this counts per camera, never across."""
    visits: dict = {}
    for cell in range(grid["rows"] * grid["cols"]):
        in_cam = [t for t in tracks if t.cell == cell]
        visits[cell] = sum(
            1 for t in in_cam
            if t.hits >= 2 and (t.dwell_s >= 2.0 or _displacement(t) > 40.0)
        )
    out = []
    for cell in range(grid["rows"] * grid["cols"]):
        r, c = divmod(cell, grid["cols"])
        out.append({"camera": f"CAM {cell + 1:02d}", "row": r, "col": c,
                    "visits_est": visits[cell]})
    return out


def _displacement(t) -> float:
    if len(t.path) < 2:
        return 0.0
    x0, y0 = t.path[0][1], t.path[0][2]
    x1, y1 = t.path[-1][1], t.path[-1][2]
    return ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5


def _tile_motion(gray, prev_gray, grid, cam: int = 0) -> list:
    """Frame-to-frame motion inside one camera, on consecutive source frames.

    A camera wall is 16 unrelated scenes; comparing whole frames would report
    motion even with a perfectly still wall, so we sample inside one camera."""
    if prev_gray is None:
        return []
    x0, y0, tw, th = mosaic.tile_starts(grid)[cam]
    a, b = gray[y0:y0 + th, x0:x0 + tw], prev_gray[y0:y0 + th, x0:x0 + tw]
    if a.shape != b.shape or a.size == 0:
        return []
    return [float(cv2.mean(cv2.absdiff(a, b))[0] / 255.0)]


def measure_motion(cap, n_frames: int, grid=None, burst: int = 12) -> dict:
    """Camera pan/shake evidence from CONSECUTIVE frames.

    Sampled frames are seconds apart, so differencing them measures scene change
    rather than camera motion. This reads a short burst of consecutive frames in
    the middle of the clip instead.

    Uses global phase correlation (a shift estimate in pixels), not mean pixel
    difference: people walking produce plenty of pixel difference on a perfectly
    still camera, while a panning camera shifts the whole image. On a wall, each
    camera is measured separately, since 16 still cameras must not look like one
    moving one."""
    if n_frames <= burst + 2:
        return {}
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, n_frames // 2))
    prev = None
    per_cam: dict = {}
    whole: list = []
    for _ in range(burst):
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        g = cv2.GaussianBlur(g.astype(np.float32), (5, 5), 0)
        if prev is not None:
            if grid:
                for idx, (x0, y0, tw, th) in enumerate(mosaic.tile_starts(grid)):
                    a, b = g[y0:y0 + th, x0:x0 + tw], prev[y0:y0 + th, x0:x0 + tw]
                    if a.shape != b.shape or a.size == 0:
                        continue
                    per_cam.setdefault(idx, []).append(_shift_px(a, b))
            else:
                whole.append(_shift_px(g, prev))
        prev = g
    if grid:
        cam = [sum(v) / len(v) for v in per_cam.values() if v]
        if not cam:
            return {}
        cam.sort()
        median = cam[len(cam) // 2]
        # A wall of still cameras is still even if one small tile yields a noisy
        # shift estimate, so the wall decision uses the median, not the worst.
        return {"avg_motion_px": round(sum(cam) / len(cam), 2),
                "max_motion_px": round(cam[-1], 2),
                "median_motion_px": round(median, 2),
                "moving_cameras": sum(1 for m in cam if m > PAN_PX),
                "moving_camera": median > PAN_PX}
    if not whole:
        return {}
    avg = sum(whole) / len(whole)
    return {"avg_motion_px": round(avg, 2),
            "max_motion_px": round(max(whole), 2),
            "moving_camera": avg > PAN_PX}


def _shift_px(a, b) -> float:
    """Estimated global translation between two frames, in pixels."""
    try:
        (dx, dy), _ = cv2.phaseCorrelate(a, b)
    except cv2.error:
        return 0.0
    return (dx * dx + dy * dy) ** 0.5


def _sample_frames(cap, n_frames: int, fps: float, step: int, count: int = 5) -> list:
    """Grab a few spread-out frames to decide the scene layout."""
    if n_frames <= 0:
        return []
    picks = [int(n_frames * (i + 0.5) / count) for i in range(count)]
    frames = []
    for idx in picks:
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(idx, max(0, n_frames - 1)))
        ok, f = cap.read()
        if ok:
            frames.append(f)
    return frames


def _track_row(t) -> dict:
    xs = [p[1] for p in t.path]
    ys = [p[2] for p in t.path]
    return {
        "track_id": t.id,
        "cell": t.cell,
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
