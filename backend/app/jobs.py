"""Background job runner. One worker thread, one video at a time."""
from __future__ import annotations

import queue
import threading
import traceback
from datetime import datetime, timezone

from . import db, utils
from .config import job_config_from_request, get_model_meta
from .cv.pipeline import run_pipeline


class JobRunner:
    def __init__(self):
        self._q: queue.Queue[int] = queue.Queue()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self.current_job_id = None

    def enqueue(self, job_id: int):
        self._q.put(job_id)

    def _loop(self):
        while True:
            job_id = self._q.get()
            self.current_job_id = job_id
            try:
                self._execute(job_id)
            except Exception:
                traceback.print_exc()
            finally:
                self.current_job_id = None
                self._q.task_done()

    def _execute(self, job_id: int):
        job = db.q1("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not job:
            return
        video = db.q1("SELECT * FROM videos WHERE id=?", (job["video_id"],))
        if not video:
            db.exec("UPDATE jobs SET status='failed', error='video missing', finished_at=datetime('now') WHERE id=?", (job_id,))
            return
        cfg = job_config_from_request(utils.loads(job["config_json"], {}))
        cfg["zones"] = utils.loads(job["config_json"], {}).get("zones") or []

        def progress(stage, pct):
            db.exec("UPDATE jobs SET status='running', stage=?, progress=? WHERE id=?",
                    (stage, round(pct * 100, 1), job_id))

        db.exec("UPDATE jobs SET status='running', stage='starting', progress=1, started_at=datetime('now') WHERE id=?", (job_id,))
        try:
            artifacts = utils.media_dir(video["id"], job_id)
            res = run_pipeline(video["stored_path"], cfg, artifacts,
                               zones_json=cfg["zones"], progress=progress)
            self._persist(job_id, video["id"], res, cfg)
            db.exec("UPDATE jobs SET status='done', stage='complete', progress=100, finished_at=datetime('now') WHERE id=?", (job_id,))
            _notify(job["video_id"], job_id, video["filename"], res)
        except Exception as e:
            db.exec("UPDATE jobs SET status='failed', stage='error', error=?, finished_at=datetime('now') WHERE id=?",
                    (str(e)[:500], job_id))
            _notify(job["video_id"], job_id, video["filename"], None, error=str(e))

    def _persist(self, job_id: int, video_id: int, res, cfg: dict):
        s = res.summary
        scene = dict(res.scene)
        if s.get("per_camera"):
            # kept inside the scene blob so no new column is needed
            scene["per_camera"] = s["per_camera"]
        if s.get("track_quality"):
            scene["track_quality"] = s["track_quality"]
        analysis_id = db.exec("""INSERT INTO analyses(job_id, video_id, total_detections,
            unique_visits_est, entries_est, exits_est, avg_occupancy, max_occupancy,
            dwell_avg_s, dwell_p50_s, busy_periods_json, traffic_series_json,
            heatmap_path, reference_frame_path, detected_frames, processed_frames,
            inference_device, inference_ms_avg, model_id, model_version, scene_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (job_id, video_id, s["total_detections"], s["unique_visits_est"],
             s["entries_est"], s["exits_est"], s["avg_occupancy"], s["max_occupancy"],
             s["dwell_avg_s"], s["dwell_p50_s"], s["busy_periods_json"],
             s["traffic_series_json"], res.heatmap_path, res.reference_path,
             res.detected_frames, res.processed_frames, res.inference_device,
             res.inference_ms_avg, cfg["model"], get_model_meta(cfg["model"])["version"],
             utils.dumps(scene)))

        db.execmany("""INSERT INTO tracks(analysis_id, track_id, first_seen_s, last_seen_s,
            dwell_s, avg_x, avg_y, min_x, min_y, max_x, max_y, path_json, stationary_ratio,
            cell, flagged)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
            [(analysis_id, t["track_id"], t["first_seen_s"], t["last_seen_s"],
              t["dwell_s"], t["avg_x"], t["avg_y"], t["min_x"], t["min_y"],
              t["max_x"], t["max_y"], utils.dumps(t["path_json"]), t["stationary_ratio"],
              t.get("cell"))
             for t in res.tracks])

        db.execmany("""INSERT INTO events(analysis_id, video_id, type, subtype, label,
            ts_s, confidence, evidence_json, thumb_path, status)
            VALUES (?,?,?,?,?,?,?,?,?, 'open')""",
            [(analysis_id, video_id, e["type"], e["subtype"], e["label"],
              e["ts_s"], e["confidence"], utils.dumps(e["evidence_json"]), e.get("thumb_path"))
             for e in res.events])

        db.exec("""INSERT INTO model_meta(model_id, display_name, version, license,
            device, conf, imgsz, sample_step)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(model_id) DO UPDATE SET device=excluded.device,
              conf=excluded.conf, imgsz=excluded.imgsz, sample_step=excluded.sample_step,
              updated_at=datetime('now')""",
            (cfg["model"], res.model_meta["display"], res.model_meta["version"],
             res.model_meta["license"], res.inference_device, cfg["conf"],
             cfg["imgsz"], cfg["sample_step"]))
        return analysis_id


def _notify(video_id: int, job_id: int, filename: str, res, error: str = ""):
    text = f"Analysis completed for {filename}" if not error else f"Analysis failed: {filename}"
    if error:
        text += f" ({error})"
    link = f"/analysis?video={video_id}&job={job_id}"
    rows = db.q("SELECT id FROM users WHERE role IN ('admin','analyst','reviewer')")
    db.execmany("INSERT INTO notifications(user_id, text, link) VALUES (?,?,?)",
                [(r["id"], text, link) for r in rows])


runner = JobRunner()
