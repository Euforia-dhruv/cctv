"""Small shared helpers: video probe, ids, artifact paths."""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

import cv2

from . import config

_ID_RE = re.compile(r"[^a-zA-Z0-9_.-]")


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def new_token() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


def probe_video(path: str | Path) -> dict:
    """Open a video and return metadata. Raises ValueError if not a decodable video."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("Could not open video file (unsupported or corrupt).")
    fps = cap.get(cv2.CAP_PROP_FPS)
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    cap.release()
    if fps <= 0 or n <= 0 or w <= 0 or h <= 0:
        raise ValueError("Video has no readable stream (zero fps/frames).")
    return {"fps": fps, "frames": int(n), "width": int(w), "height": int(h),
            "duration_s": n / fps}


def safe_name(name: str) -> str:
    return _ID_RE.sub("_", name) or "file"


def media_dir(video_id: int, job_id: int) -> Path:
    p = config.ARTIFACT_DIR / f"v{video_id}" / f"j{job_id}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def loads(text: str | None, default=None):
    if not text:
        return default
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default
