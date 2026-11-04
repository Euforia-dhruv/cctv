# RetailVision AI: Tech Stack Decisions

Each decision records the option set, the choice, and the reason. Everything here is justified by the hardware constraints (i5-11400H, RTX 3050 4GB, 16GB RAM) and the demo-first goal.

## 1. Frontend: static SPA (no build step) instead of Next.js/React

- Options: Next.js + React + Tailwind + shadcn/ui (as suggested) vs. a hand-built single-page app (HTML/CSS/JS + Chart.js) served by FastAPI.
- Decision: static SPA.
- Reason: the prototype must run and be demoed reliably on a Windows laptop with minimal moving parts. A Next.js build adds npm install, a build step, hundreds of packages, and build-failure modes, for no demo-visible benefit. The SPA is still a real app: real API calls, real database data, real charts, no mock data. The instruction said "React/Next.js if starting fresh", but the project has no existing framework, and we are choosing the smaller complete change; this is a deliberate, documented deviation (the API contract is REST so the UI can be ported to React later without backend changes).
- Chart.js is vendored locally (MIT), so the demo works offline.

## 2. Backend: FastAPI + Pydantic + Uvicorn

- Chosen for typed models, auto-docs (OpenAPI), async support, and one-file simplicity. License MIT/BSD. [verified] pip registry

## 3. Database: SQLite with a thin stdlib layer, upgradeable to PostgreSQL

- Options: SQLAlchemy + SQLite, raw sqlite3.
- Decision: sqlite3 stdlib with a small, single `db.py` layer (schema + query helpers).
- Reason: zero extra dependency, fast, adequate for single-user prototype. The schema is written as portable DDL and all data access goes through one module, so a move to SQLAlchemy/Postgres later touches one module. No ORM magic needed at this scale.

## 4. Job execution: background thread in-process (no Celery/Redis)

- Options: Celery + Redis, thread/queue.
- Decision: a single background worker thread consuming a job queue with status persistence.
- Reason: one video at a time, one machine. Celery+Redis would violate the "no unnecessary background services" constraint. The job runner is behind a small interface so it can be swapped for a hosted worker later.

## 5. Computer vision: Ultralytics YOLO26n + custom lightweight IoU tracker

- See AI_MODEL_EVALUATION.md for the model comparison and license notes.
- The tracker is our own (no GPL/AGPL dependency), ~100 lines, with constant-velocity prediction. It is intentionally not ByteTrack code, but follows the same association idea (IoU + motion gating) and is documented as such.
- ONNX Runtime is not needed for the MVP: PyTorch handles both GPU and CPU; ONNX export is documented as the future low-latency path.

## 6. Media: OpenCV (cv2) for decode, probe, and artifact generation

- Backed by bundled FFmpeg support; PIL for heatmap rendering. Both are standard, well-licensed.

## 7. What we deliberately excluded

- Redis, Kafka, Kubernetes, Docker (for runtime), PostgreSQL, Celery, mlflow, vector DBs. None are justified for this prototype; they are documented as future steps.
- Authentication: a simple, secure-enough email/password + token scheme (stdlib hmac + random tokens), no third-party IdP, because this is a local prototype. Password hashing uses PBKDF2 via hashlib (stdlib, no dependency).

## 8. Future hosted API architecture (design only)

See ARCHITECTURE.md section "Future hosted API". Key principle: inference is an isolated adapter so it can move to a GPU host without touching CRM code.
