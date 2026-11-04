"""Core routes: auth, stores, cameras, videos, jobs."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from . import config, db, jobs, utils
from .auth import create_session, hash_password, optional_user, require_user, verify_password

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------- auth
@router.post("/auth/register")
def register(body: dict):
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()
    pw = body.get("password") or ""
    role = body.get("role") or "analyst"
    if not email or "@" not in email or len(pw) < 6:
        raise HTTPException(400, "A valid email and password (6+ chars) are required")
    if role not in ("admin", "analyst", "reviewer"):
        role = "analyst"
    if db.q1("SELECT id FROM users WHERE email=?", (email,)):
        raise HTTPException(409, "Email already registered")
    uid = db.exec("INSERT INTO users(email, name, password_hash, role) VALUES (?,?,?,?)",
                  (email, name, hash_password(pw), role))
    db.audit(uid, "register", "user", email)
    return {"token": create_session(uid), "user": db.q1("SELECT id,email,name,role FROM users WHERE id=?", (uid,))}


@router.post("/auth/login")
def login(body: dict):
    email = (body.get("email") or "").strip().lower()
    row = db.q1("SELECT * FROM users WHERE email=?", (email,))
    if not row or not verify_password(body.get("password") or "", row["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    db.audit(row["id"], "login", "user", email)
    return {"token": create_session(row["id"]),
            "user": {"id": row["id"], "email": row["email"], "name": row["name"], "role": row["role"]}}


@router.get("/auth/me")
def me(user: dict = Depends(require_user)):
    return {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}


@router.post("/auth/logout")
def logout(user: dict = Depends(require_user), token: str = ""):
    return {"ok": True}


# ---------------------------------------------------------------- stores
@router.get("/stores")
def list_stores(user: dict = Depends(require_user)):
    return db.q("SELECT s.*, (SELECT COUNT(*) FROM cameras c WHERE c.store_id=s.id) AS camera_count FROM stores s ORDER BY s.name")


@router.post("/stores")
def create_store(body: dict, user: dict = Depends(require_user)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Store name required")
    sid = db.exec("INSERT INTO stores(name, address) VALUES (?,?)", (name, body.get("address", "")))
    db.audit(user["id"], "create_store", "store", name)
    return db.q1("SELECT * FROM stores WHERE id=?", (sid,))


@router.patch("/stores/{store_id}")
def update_store(store_id: int, body: dict, user: dict = Depends(require_user)):
    db.exec("UPDATE stores SET name=?, address=? WHERE id=?", (body.get("name"), body.get("address"), store_id))
    db.audit(user["id"], "update_store", "store", str(store_id))
    return db.q1("SELECT * FROM stores WHERE id=?", (store_id,))


@router.delete("/stores/{store_id}")
def delete_store(store_id: int, user: dict = Depends(require_user)):
    db.exec("DELETE FROM stores WHERE id=?", (store_id,))
    db.audit(user["id"], "delete_store", "store", str(store_id))
    return {"ok": True}


# ---------------------------------------------------------------- cameras
@router.get("/stores/{store_id}/cameras")
def list_cameras(store_id: int, user: dict = Depends(require_user)):
    return db.q("SELECT * FROM cameras WHERE store_id=? ORDER BY name", (store_id,))


@router.post("/stores/{store_id}/cameras")
def create_camera(store_id: int, body: dict, user: dict = Depends(require_user)):
    cid = db.exec("INSERT INTO cameras(store_id, name, location, notes) VALUES (?,?,?,?)",
                  (store_id, body.get("name") or "Camera", body.get("location", ""), body.get("notes", "")))
    db.audit(user["id"], "create_camera", "camera", str(cid))
    return db.q1("SELECT * FROM cameras WHERE id=?", (cid,))


# ---------------------------------------------------------------- videos
@router.get("/videos")
def list_videos(user: dict = Depends(require_user), store_id: int | None = None):
    if store_id:
        return db.q("""SELECT v.*, s.name AS store_name,
            (SELECT COUNT(*) FROM jobs j WHERE j.video_id=v.id) AS job_count
            FROM videos v JOIN stores s ON s.id=v.store_id WHERE v.store_id=? ORDER BY v.id DESC""", (store_id,))
    return db.q("""SELECT v.*, s.name AS store_name,
        (SELECT COUNT(*) FROM jobs j WHERE j.video_id=v.id) AS job_count
        FROM videos v JOIN stores s ON s.id=v.store_id ORDER BY v.id DESC""")


@router.post("/videos")
async def upload_video(file: UploadFile = File(...), store_id: int = Form(...),
                       camera_id: int | None = Form(None), consent: int = Form(0),
                       user: dict = Depends(require_user)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in config.ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported format {ext}; use mp4/mov/avi")
    if not db.q1("SELECT id FROM stores WHERE id=?", (store_id,)):
        raise HTTPException(404, "Store not found")
    content = await file.read()
    if len(content) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File larger than {config.MAX_UPLOAD_MB} MB")
    stored_name = f"{utils.new_token()[:12]}{ext}"
    dst = config.UPLOAD_DIR / stored_name
    dst.write_bytes(content)
    try:
        probe = utils.probe_video(dst)
    except ValueError as e:
        dst.unlink(missing_ok=True)
        raise HTTPException(400, str(e))
    vid = db.exec("""INSERT INTO videos(store_id, camera_id, filename, stored_path,
        size_bytes, duration_s, width, height, fps, consent_ok, uploaded_by)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (store_id, camera_id, file.filename or stored_name, str(dst), len(content),
         probe["duration_s"], probe["width"], probe["height"], probe["fps"],
         1 if consent else 0, user["id"]))
    db.audit(user["id"], "upload_video", "video", str(vid))
    return db.q1("SELECT * FROM videos WHERE id=?", (vid,))


@router.get("/videos/{video_id}")
def get_video(video_id: int, user: dict = Depends(require_user)):
    row = db.q1("""SELECT v.*, s.name AS store_name FROM videos v
        JOIN stores s ON s.id=v.store_id WHERE v.id=?""", (video_id,))
    if not row:
        raise HTTPException(404, "Video not found")
    row["latest_job"] = db.q1("SELECT * FROM jobs WHERE video_id=? ORDER BY id DESC LIMIT 1", (video_id,))
    from pathlib import Path as _P
    row["stream_url"] = "/media/" + _P(row["stored_path"]).name
    return row


@router.get("/videos/{video_id}/stream")
def stream_video(video_id: int, user: dict | None = Depends(optional_user)):
    from fastapi.responses import FileResponse
    row = db.q1("SELECT stored_path FROM videos WHERE id=?", (video_id,))
    if not row:
        raise HTTPException(404, "Video not found")
    return FileResponse(row["stored_path"], media_type="video/mp4")


@router.delete("/videos/{video_id}")
def delete_video(video_id: int, user: dict = Depends(require_user)):
    row = db.q1("SELECT stored_path FROM videos WHERE id=?", (video_id,))
    if row:
        Path(row["stored_path"]).unlink(missing_ok=True)
    db.exec("DELETE FROM videos WHERE id=?", (video_id,))
    db.audit(user["id"], "delete_video", "video", str(video_id))
    return {"ok": True}


# ---------------------------------------------------------------- jobs
@router.post("/videos/{video_id}/analyze")
def analyze(video_id: int, body: dict | None = None, user: dict = Depends(require_user)):
    if not db.q1("SELECT id FROM videos WHERE id=?", (video_id,)):
        raise HTTPException(404, "Video not found")
    cfg = utils.dumps(body or {})
    job_id = db.exec("INSERT INTO jobs(video_id, status, config_json) VALUES (?, 'queued', ?)",
                     (video_id, cfg))
    jobs.runner.enqueue(job_id)
    db.audit(user["id"], "analyze", "video", str(video_id))
    return db.q1("SELECT * FROM jobs WHERE id=?", (job_id,))


@router.get("/jobs")
def list_jobs(user: dict = Depends(require_user), video_id: int | None = None):
    sql = """SELECT j.*, v.filename, v.store_id, a.id AS analysis
             FROM jobs j JOIN videos v ON v.id=j.video_id
             LEFT JOIN analyses a ON a.job_id=j.id"""
    if video_id:
        return db.q(sql + " WHERE j.video_id=? ORDER BY j.id DESC", (video_id,))
    return db.q(sql + " ORDER BY j.id DESC LIMIT 200")


@router.get("/jobs/{job_id}")
def get_job(job_id: int, user: dict = Depends(require_user)):
    row = db.q1("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not row:
        raise HTTPException(404, "Job not found")
    row["config"] = utils.loads(row["config_json"], {})
    row["analysis"] = db.q1("SELECT id FROM analyses WHERE job_id=?", (job_id,))
    return row
