"""SQLite persistence layer. Single module, portable DDL, per-thread connections."""
from __future__ import annotations

import sqlite3
import threading
from typing import Any, Iterable

from . import config

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'analyst',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  address TEXT DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS cameras (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  location TEXT DEFAULT '',
  notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS videos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
  camera_id INTEGER REFERENCES cameras(id) ON DELETE SET NULL,
  filename TEXT NOT NULL,
  stored_path TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  duration_s REAL,
  width INTEGER, height INTEGER, fps REAL,
  consent_ok INTEGER NOT NULL DEFAULT 0,
  uploaded_by INTEGER REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'queued',   -- queued|running|done|failed
  stage TEXT DEFAULT '',
  progress REAL NOT NULL DEFAULT 0,
  error TEXT,
  model_id TEXT, config_json TEXT,
  started_at TEXT, finished_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS analyses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  total_detections INTEGER DEFAULT 0,
  unique_visits_est INTEGER,
  entries_est INTEGER, exits_est INTEGER,
  avg_occupancy REAL, max_occupancy INTEGER,
  dwell_avg_s REAL, dwell_p50_s REAL,
  busy_periods_json TEXT,
  traffic_series_json TEXT,
  heatmap_path TEXT,
  reference_frame_path TEXT,
  detected_frames INTEGER, processed_frames INTEGER,
  inference_device TEXT, inference_ms_avg REAL,
  model_id TEXT, model_version TEXT,
  scene_json TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS tracks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
  track_id INTEGER NOT NULL,
  first_seen_s REAL, last_seen_s REAL, dwell_s REAL,
  avg_x REAL, avg_y REAL,
  min_x REAL, min_y REAL, max_x REAL, max_y REAL,
  path_json TEXT, zone_ids_json TEXT,
  stationary_ratio REAL,
  flagged INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
  video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  type TEXT NOT NULL,            -- operational|security|queue|congestion
  subtype TEXT NOT NULL,
  label TEXT NOT NULL,
  ts_s REAL NOT NULL,
  confidence REAL,
  evidence_json TEXT,
  thumb_path TEXT,
  status TEXT NOT NULL DEFAULT 'open',  -- open|reviewing|resolved|confirmed|dismissed
  reviewer_notes TEXT,
  reviewed_by INTEGER REFERENCES users(id),
  reviewed_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
  reviewer INTEGER NOT NULL REFERENCES users(id),
  label_original TEXT, label_corrected TEXT,
  video_time REAL, thumb_path TEXT,
  model_id TEXT,
  included_in_dataset INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS model_meta (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  model_id TEXT NOT NULL UNIQUE,
  display_name TEXT, version TEXT, license TEXT,
  device TEXT, conf REAL, imgsz INTEGER, sample_step INTEGER,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id),
  action TEXT NOT NULL,
  resource TEXT,
  detail TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  link TEXT, read INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_analysis ON events(analysis_id);
CREATE INDEX IF NOT EXISTS idx_tracks_analysis ON tracks(analysis_id);
CREATE INDEX IF NOT EXISTS idx_jobs_video ON jobs(video_id);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_db() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        _local.conn = _connect()
    return _local.conn


def init_db() -> None:
    config.ensure_dirs()
    conn = _connect()
    conn.executescript(SCHEMA)
    # lightweight migration for existing databases (additive only)
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(analyses)").fetchall()]
    if "scene_json" not in cols:
        conn.execute("ALTER TABLE analyses ADD COLUMN scene_json TEXT")
    conn.commit()
    conn.close()


def q(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    cur = get_db().execute(sql, tuple(params))
    return [dict(r) for r in cur.fetchall()]


def q1(sql: str, params: Iterable[Any] = ()) -> dict | None:
    rows = q(sql, params)
    return rows[0] if rows else None


def exec(sql: str, params: Iterable[Any] = ()) -> int:
    conn = get_db()
    cur = conn.execute(sql, tuple(params))
    conn.commit()
    return cur.lastrowid


def execmany(sql: str, seq: Iterable[Iterable[Any]]) -> None:
    conn = get_db()
    conn.executemany(sql, seq)
    conn.commit()


def audit(user_id: int | None, action: str, resource: str = "", detail: str = "") -> None:
    exec("INSERT INTO audit_log(user_id, action, resource, detail) VALUES (?,?,?,?)",
         (user_id, action, resource, detail))
