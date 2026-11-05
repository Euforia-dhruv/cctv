"""Analysis, events, feedback, reports, models, settings, notifications, audit."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response

from . import config, db, utils
from .auth import optional_user, require_user

router = APIRouter(prefix="/api")


def _get_analysis(analysis_id: int) -> dict:
    row = db.q1("SELECT * FROM analyses WHERE id=?", (analysis_id,))
    if not row:
        raise HTTPException(404, "Analysis not found")
    return row


# ---------------------------------------------------------------- analysis
@router.get("/analyses/summary")
def analyses_summary(user: dict = Depends(require_user)):
    row = db.q1("""SELECT COUNT(*) AS analyses, COALESCE(SUM(total_detections),0) AS detections,
        COALESCE(SUM(unique_visits_est),0) AS visits,
        COALESCE(ROUND(AVG(avg_occupancy),2),0) AS avg_occupancy
        FROM analyses""")
    events = db.q1("SELECT COUNT(*) AS open_events FROM events WHERE status IN ('open','reviewing')")
    return {"analyses": row, "open_events": events["open_events"]}


@router.get("/analyses/{analysis_id}")
def analysis_summary(analysis_id: int, user: dict = Depends(require_user)):
    a = _get_analysis(analysis_id)
    video = db.q1("SELECT v.*, s.name AS store_name FROM videos v JOIN stores s ON s.id=v.store_id WHERE v.id=?", (a["video_id"],))
    job = db.q1("SELECT id, model_id, config_json, status FROM jobs WHERE id=?", (a["job_id"],))
    events = db.q("SELECT id, type, subtype, label, ts_s, confidence, status, thumb_path FROM events WHERE analysis_id=? ORDER BY ts_s", (analysis_id,))
    scene = utils.loads(a["scene_json"], {})
    return {
        "analysis": {
            **a,
            "busy_periods": utils.loads(a["busy_periods_json"], []),
            "traffic_series": utils.loads(a["traffic_series_json"], []),
            "scene": scene,
            # camera-wall breakdown (empty for a single-camera clip)
            "per_camera": scene.get("per_camera", []),
            "zone_exposure": {},
        },
        "video": video,
        "job": job,
        "events": events,
    }


@router.get("/analyses/{analysis_id}/traffic")
def traffic(analysis_id: int, user: dict = Depends(require_user)):
    a = _get_analysis(analysis_id)
    return {"series": utils.loads(a["traffic_series_json"], []),
            "busy": utils.loads(a["busy_periods_json"], [])}


@router.get("/analyses/{analysis_id}/heatmap")
def heatmap(analysis_id: int, user: dict | None = Depends(optional_user)):
    a = _get_analysis(analysis_id)
    if not a["heatmap_path"] or not __import__("os").path.exists(a["heatmap_path"]):
        raise HTTPException(404, "Heatmap not available")
    return FileResponse(a["heatmap_path"], media_type="image/jpeg")


@router.get("/analyses/{analysis_id}/reference")
def reference(analysis_id: int, user: dict | None = Depends(optional_user)):
    a = _get_analysis(analysis_id)
    if not a["reference_frame_path"] or not __import__("os").path.exists(a["reference_frame_path"]):
        raise HTTPException(404, "Reference frame not available")
    return FileResponse(a["reference_frame_path"], media_type="image/jpeg")


@router.get("/analyses/{analysis_id}/tracks")
def tracks(analysis_id: int, user: dict = Depends(require_user)):
    rows = db.q("SELECT * FROM tracks WHERE analysis_id=? ORDER BY track_id", (analysis_id,))
    for r in rows:
        r["path"] = utils.loads(r["path_json"], [])
        r.pop("path_json", None)
    return rows


@router.get("/analyses/{analysis_id}/events")
def analysis_events(analysis_id: int, user: dict = Depends(require_user)):
    return db.q("SELECT * FROM events WHERE analysis_id=? ORDER BY ts_s", (analysis_id,))


# ---------------------------------------------------------------- events
@router.get("/events")
def list_events(user: dict = Depends(require_user), status: str | None = None,
                type: str | None = None):
    sql = """SELECT e.*, v.filename, a.id AS analysis_id, v.id AS video_id
             FROM events e JOIN videos v ON v.id=e.video_id
             JOIN analyses a ON a.id=e.analysis_id WHERE 1=1"""
    params = []
    if status:
        sql += " AND e.status=?"
        params.append(status)
    if type:
        sql += " AND e.type=?"
        params.append(type)
    sql += " ORDER BY e.id DESC LIMIT 200"
    return db.q(sql, params)


@router.patch("/events/{event_id}")
def update_event(event_id: int, body: dict, user: dict = Depends(require_user)):
    row = db.q1("SELECT * FROM events WHERE id=?", (event_id,))
    if not row:
        raise HTTPException(404, "Event not found")
    if body.get("status"):
        db.exec("UPDATE events SET status=?, reviewed_by=?, reviewed_at=datetime('now') WHERE id=?",
                (body["status"], user["id"], event_id))
    if "reviewer_notes" in body:
        db.exec("UPDATE events SET reviewer_notes=?, reviewed_by=?, reviewed_at=datetime('now') WHERE id=?",
                (body["reviewer_notes"], user["id"], event_id))
    db.audit(user["id"], "review_event", "event", str(event_id))
    return db.q1("SELECT * FROM events WHERE id=?", (event_id,))


@router.get("/events/{event_id}/thumb")
def event_thumb(event_id: int, user: dict | None = Depends(optional_user)):
    row = db.q1("SELECT thumb_path FROM events WHERE id=?", (event_id,))
    if not row or not row["thumb_path"] or not __import__("os").path.exists(row["thumb_path"]):
        raise HTTPException(404, "Thumbnail not available")
    return FileResponse(row["thumb_path"], media_type="image/jpeg")


# ---------------------------------------------------------------- feedback
@router.post("/feedback")
def submit_feedback(body: dict, user: dict = Depends(require_user)):
    event_id = body.get("event_id")
    fid = db.exec("""INSERT INTO feedback(source_event_id, reviewer, label_original,
        label_corrected, video_time, model_id)
        VALUES (?,?,?,?,?,?)""",
        (event_id, user["id"], body.get("label_original"), body.get("label_corrected"),
         body.get("video_time"), body.get("model_id")))
    db.audit(user["id"], "feedback", "event", str(event_id))
    return {"id": fid, "ok": True}


@router.get("/feedback")
def list_feedback(user: dict = Depends(require_user)):
    return db.q("SELECT f.*, u.name AS reviewer_name FROM feedback f JOIN users u ON u.id=f.reviewer ORDER BY f.id DESC LIMIT 200")


# ---------------------------------------------------------------- reports
@router.get("/analyses/{analysis_id}/report.csv")
def report_csv(analysis_id: int, user: dict = Depends(require_user)):
    a = _get_analysis(analysis_id)
    buffer = io.StringIO()
    w = csv.writer(buffer)
    w.writerow(["RetailVision AI analysis report"])
    w.writerow(["analysis_id", analysis_id])
    w.writerow(["generated", utils.now_iso()])
    w.writerow([])
    w.writerow(["metric", "value"])
    for k in ("total_detections", "unique_visits_est", "entries_est", "exits_est",
              "avg_occupancy", "max_occupancy", "dwell_avg_s", "dwell_p50_s"):
        w.writerow([k, a[k]])
    w.writerow([])
    w.writerow(["events"])
    w.writerow(["time_s", "type", "subtype", "label", "confidence", "status"])
    for e in db.q("SELECT ts_s, type, subtype, label, confidence, status FROM events WHERE analysis_id=? ORDER BY ts_s", (analysis_id,)):
        w.writerow([e["ts_s"], e["type"], e["subtype"], e["label"], e["confidence"], e["status"]])
    return Response(buffer.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=analysis_{analysis_id}.csv"})


@router.get("/analyses/{analysis_id}/report.json")
def report_json(analysis_id: int, user: dict = Depends(require_user)):
    a = _get_analysis(analysis_id)
    payload = {
        "analysis_id": analysis_id,
        "generated": utils.now_iso(),
        "summary": {k: a[k] for k in ("total_detections", "unique_visits_est", "entries_est",
                                       "exits_est", "avg_occupancy", "max_occupancy",
                                       "dwell_avg_s", "dwell_p50_s")},
        "busy_periods": utils.loads(a["busy_periods_json"], []),
        "traffic_series": utils.loads(a["traffic_series_json"], []),
        "events": db.q("SELECT ts_s, type, subtype, label, confidence, status FROM events WHERE analysis_id=? ORDER BY ts_s", (analysis_id,)),
    }
    return JSONResponse(payload)


# ---------------------------------------------------------------- models
@router.get("/models")
def list_models(user: dict = Depends(require_user)):
    active = db.q1("SELECT * FROM model_meta ORDER BY updated_at DESC LIMIT 1")
    return {"registry": config.MODEL_REGISTRY, "active": active,
            "defaults": {k: config.DEFAULTS[k] for k in ("conf", "imgsz", "sample_step", "device")}}


@router.get("/models/active")
def active_model(user: dict = Depends(require_user)):
    return db.q1("SELECT * FROM model_meta ORDER BY updated_at DESC LIMIT 1") or {}


@router.patch("/models/active")
def set_active_model(body: dict, user: dict = Depends(require_user)):
    mid = body.get("model_id")
    if mid not in config.MODEL_REGISTRY:
        raise HTTPException(400, "Unknown model")
    # default next jobs to this model (stored as a selection for future runs)
    db.exec("""INSERT INTO model_meta(model_id, display_name, version, license, conf, imgsz, sample_step)
        VALUES (?,?,?,?,?,?,?) ON CONFLICT(model_id) DO UPDATE SET updated_at=datetime('now')""",
        (mid, config.MODEL_REGISTRY[mid]["display"], config.MODEL_REGISTRY[mid]["version"],
         config.MODEL_REGISTRY[mid]["license"], body.get("conf", config.DEFAULTS["conf"]),
         body.get("imgsz", config.DEFAULTS["imgsz"]), body.get("sample_step", config.DEFAULTS["sample_step"])))
    db.audit(user["id"], "set_model", "model", mid)
    return {"ok": True}


# ---------------------------------------------------------------- settings
@router.get("/settings")
def get_settings(user: dict = Depends(require_user)):
    rows = db.q("SELECT key, value FROM settings")
    return {r["key"]: r["value"] for r in rows}


@router.patch("/settings")
def update_settings(body: dict, user: dict = Depends(require_user)):
    for k, v in body.items():
        db.exec("INSERT INTO settings(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (k, str(v)))
    db.audit(user["id"], "update_settings", "settings", str(body))
    return body


# ---------------------------------------------------------------- notifications
@router.get("/notifications")
def notifications(user: dict = Depends(require_user)):
    return db.q("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50", (user["id"],))


@router.post("/notifications/read")
def mark_read(user: dict = Depends(require_user)):
    db.exec("UPDATE notifications SET read=1 WHERE user_id=?", (user["id"],))
    return {"ok": True}


# ---------------------------------------------------------------- audit
@router.get("/audit")
def audit_log(user: dict = Depends(require_user)):
    return db.q("SELECT a.*, u.name AS user_name FROM audit_log a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 100")
