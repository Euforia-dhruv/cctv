# RetailVision AI: Architecture

## 1. High-level view

```
+--------------------------------------------------------------+
| Frontend (vanilla SPA, served by FastAPI)                     |
| index.html / styles.css / app.js / vendor/chart.umd.min.js    |
+--------------------------------------------------------------+
              | REST /api (JSON, bearer token)
+--------------------------------------------------------------+
| Backend: FastAPI (uvicorn)                                    |
|  routes_core: auth, stores, cameras, videos, jobs            |
|  routes_analysis: analyses, events, feedback, reports,       |
|                  models, settings, notifications, audit      |
|  jobs.py: background worker thread (one video at a time)     |
|  cv/: detector.py, tracker.py, analytics.py, heatmap.py,     |
|       alerts.py, zones.py, pipeline.py                       |
|  db.py: SQLite (stdlib), portable DDL                        |
+--------------------------------------------------------------+
              | reads/writes            | files
+------------------------------+   +---------------------------+
| SQLite (retailvision.db)     |   | data/uploads/* (videos)    |
| users, stores, cameras,      |   | data/artifacts/v<j>/j<k>/ |
| videos, jobs, analyses,      |   |  reference.jpg heatmap.jpg |
| tracks, events, feedback,    |   |  event_000.jpg ...         |
| model_meta, settings, audit, |   +---------------------------+
| notifications                |
+------------------------------+
```

## 2. Module responsibilities

| Module | Responsibility |
|---|---|
| `config.py` | paths, defaults, model registry |
| `db.py` | schema + per-thread SQLite connections |
| `auth.py` | PBKDF2 hashing, token sessions, role deps |
| `utils.py` | video probe, ids, artifact paths, JSON helpers |
| `cv/detector.py` | model adapter (only place that touches Ultralytics) |
| `cv/tracker.py` | IoU tracker (anonymous IDs, velocity prediction) |
| `cv/analytics.py` | visit counts, traffic bins, busy periods, dwell, zone exposure |
| `cv/alerts.py` | MOG2 static blob (debris/unattended), unusual movement, queue/congestion heuristics |
| `cv/heatmap.py` | density overlay rendering from track coordinates |
| `cv/pipeline.py` | frame loop orchestration, artifacts, event thumbnails |
| `jobs.py` | worker thread; persists results; notifications |
| routers | API surface per domain |

## 3. Key design decisions

- Single worker thread, one job at a time: matches hardware and demo constraints; no Redis/Celery.
- SQLite with WAL; data access centralized in `db.py` so PostgreSQL migration touches one module.
- Detector adapter isolates inference; swapping YOLO26n -> YOLOv8n -> ONNX -> hosted API changes one file.
- Tracking is our own IoU tracker (license-clean, no ReID). IDs are per-analysis anonymous numbers.
- Events are neutral, human-reviewable; thumbnails stored locally.
- **Scene layout is detected, never assumed.** `cv/mosaic.py` scores candidate
  grids by separator-line coverage; a wall must pass in most sampled frames.
  A wall is then analysed per camera tile (batched inference), with tracking,
  queue clustering and heatmap normalisation kept per camera. Failing this check
  means ordinary single-view processing, so a normal clip costs nothing extra.

## 4. Database schema overview

Users, Sessions, Stores, Cameras, Videos, Jobs, Analyses, Tracks, Events, Feedback, Model_meta, Settings, Audit_log, Notifications. Full DDL lives in `app/db.py` (single source of truth).

## 5. Data flow for one analysis

1. POST /api/videos/{id}/analyze -> creates job, enqueues.
2. Worker: probe video -> detect scene layout (single view or camera wall).
3. If wall: split into tiles -> batch-detect all cameras per sampled frame ->
   associate tracks per camera. Else: detect and track on the whole frame.
4. Finalize tracks -> compute analytics -> per-camera visit counts on a wall ->
   render heatmap (camera cells outlined) -> thumbnails for events.
5. Persist analyses/tracks/events/model_meta -> notify users.

## 6. Future hosted API architecture (design only)

Split into three services, API-compatible with current endpoints:

1. **RetailVision Core API** (CRM + data) = current FastAPI app, moved to a server + PostgreSQL.
2. **Vision Inference API** (GPU host): endpoints mirror the detector adapter contract:
   - `POST /v1/videos` (upload or reference)
   - `POST /v1/analyze` (start job with model config)
   - `GET /v1/jobs/{id}` (progress)
   - `GET /v1/analytics/{id}`, `GET /v1/heatmaps/{id}`, `GET /v1/events/{id}`
   - `GET /v1/models`, `POST /v1/feedback`
   - Auth: API keys; rate limits; usage tracking; file limits (e.g., 2 GB) and job status handling.
3. **RetailVision CRM** = the SPA (already REST-based).

Inference isolation is already structural: the CRM never imports models; it only reads results. Moving `cv/detector.py` behind an HTTP client swaps local for hosted inference without touching routes or UI.

## 7. Concurrency and limits

- One analysis at a time (queue). Uploads are independent of the worker.
- Memory: pipeline streams frames; no frame history retained beyond track paths (bounded).
- Events/thumbnails are capped per analysis by detector thresholds; long clips sample frames so output size stays manageable.

## 8. Security notes (prototype scope)

- Token auth with expiry; role checks on admin actions; store/video authorization checks on writes.
- Local file storage only; no cloud upload; upload consent flag recorded.
- Audit log records key actions. Full production hardening (encryption at rest, SSO, TLS termination, rate limiting) is listed in KNOWN_LIMITATIONS.md.
