"""RetailVision AI: configuration (single source of truth for paths/defaults)."""
from __future__ import annotations

import json
import os
from pathlib import Path

# Project root = backend/.. (repo root). Everything else is derived.
ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]

DATA_DIR = Path(os.environ.get("RV_DATA_DIR", ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"          # original videos
ARTIFACT_DIR = DATA_DIR / "artifacts"      # per-job outputs
DB_PATH = DATA_DIR / "retailvision.db"
STATIC_DIR = ROOT / "frontend"

MAX_UPLOAD_MB = 1024
ALLOWED_EXT = {".mp4", ".mov", ".avi"}
# Progressive scanning recommended: mp4/mov mostly fine with OpenCV.

DEFAULT_MODEL = "yolo26n.pt"
FALLBACK_MODEL = "yolov8n.pt"

DEFAULTS = {
    "model": DEFAULT_MODEL,
    "conf": 0.35,
    "imgsz": 640,
    "sample_step": 3,       # analyze every Nth frame
    "device": "auto",       # auto|cuda|cpu
    "min_track_len": 2,     # detections
    "max_lost": 8,          # frames before a track expires
    "iou_thresh": 0.30,
    "min_dwell_s": 2.0,     # track length qualifying as a "visit"
    "stationary_px": 8.0,   # px/frame below which a person is "stationary"
    "prolonged_presence_s": 180.0,
    "unusual_speed_px": 45.0,
    "queue_min_people": 2,
    "queue_min_duration_s": 20.0,
    "congestion_people": 4,
    "congestion_min_duration_s": 30.0,
    "detector_heatmap_cells": (36, 22),
    "artifact_thumb_scale": 0.5,
    # Small-object mode: split a single-view frame into an NxN grid of overlapping
    # tiles and detect on each. Needed when people are tiny (wide/high viewpoints,
    # low-res sources), where whole-frame detection misses most of them.
    # 0 or 1 = off. 3 costs about 4x a whole-frame pass.
    "tile_grid": 0,
    "tile_overlap": 0.15,
}

MODEL_REGISTRY = {
    "yolo26n.pt": {"display": "YOLO26n", "version": "8.4.202", "license": "AGPL-3.0 / Enterprise (Ultralytics)"},
    "yolov8n.pt": {"display": "YOLOv8n", "version": "8.4.202", "license": "AGPL-3.0 / Enterprise (Ultralytics)"},
}


def defaults() -> dict:
    return dict(DEFAULTS)


def get_model_meta(model_id: str) -> dict:
    return MODEL_REGISTRY.get(model_id, {"display": model_id, "version": "?", "license": "?"})


def job_config_from_request(body: dict | None) -> dict:
    cfg = defaults()
    if body:
        for k in ("model", "conf", "imgsz", "sample_step", "device",
                  "tile_grid", "tile_overlap"):
            if k in body and body[k] is not None:
                cfg[k] = body[k]
    return cfg


def ensure_dirs() -> None:
    for p in (DATA_DIR, UPLOAD_DIR, ARTIFACT_DIR):
        p.mkdir(parents=True, exist_ok=True)
