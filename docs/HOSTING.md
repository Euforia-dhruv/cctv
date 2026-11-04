# Hosting RetailVision AI

## What can and cannot go on Vercel

Vercel is a serverless JS/edge platform. It **cannot** run this application's backend:
- Python/FastAPI service with a background worker thread (long-lived job processing)
- PyTorch/OpenCV/Ultralytics inference
- SQLite file database (ephemeral filesystem)
- Persistent uploaded video storage

The **frontend SPA can be hosted on Vercel** and pointed at a hosted backend.

## Recommended topology

```
Vercel (static SPA)  ──▶  Hosted FastAPI backend (Railway / Render / Fly.io / VPS)
                              ├─ persistent volume: /data (SQLite + uploads + artifacts)
                              └─ CPU inference is fine for demos (~14 FPS)
```

## 1. Deploy the backend

Any platform that runs Docker and offers a persistent volume works. Examples:

- Railway: add the repo, use `backend/Dockerfile`, mount a volume at `/data`.
- Render: Web Service, Docker runtime, add a Disk mounted at `/data`.
- Fly.io: `fly launch` with the Dockerfile; add `fly volume create rvdata --size 2` and mount at `/data`.
- VPS: `docker run -d -p 8000:8000 -v rvdata:/data <image>`.

### Render, step by step (recommended)

1. Push this repo to GitHub.
2. Render dashboard → **New + → Web Service** → connect the repo.
3. Settings: **Runtime = Docker**, root directory `backend` (where the Dockerfile lives).
4. Add a **Disk** (mount path `/data`, size 1 GB+) so SQLite, uploads, and artifacts persist. Note: disks require a paid instance; the free tier cannot persist data and sleeps after 15 min idle.
5. Memory: start with the Starter (512 MB) or Standard instance; CPU inference is memory-hungry and the free tier may be too small.
6. Deploy. Watch logs for `Application startup complete` and `Uvicorn running`. Verify: open `https://<your-service>.onrender.com/api/health`.
7. First analysis triggers a one-time YOLO weight download (~5 MB); first cold start is slower.

Notes:
- First boot creates the SQLite DB automatically; the YOLO weights download on first analysis (one-time).
- CPU-only container: the Dockerfile installs the CPU torch wheel.
- Expose `http://<backend>/api/health` to verify.
- In production, restrict CORS origins (currently `*` for the prototype) and put TLS at the platform edge (default on Railway/Render/Fly).

## 2. Point the frontend at the backend

Edit `frontend/env.js`:

```js
window.RV_API_BASE = "https://retailvision-backend.onrender.com";
```

Leave empty for same-origin local runs.

## 3. Deploy the frontend to Vercel

```bash
cd frontend
vercel login          # one-time
vercel --prod
```

The directory is pure static: index.html, styles.css, app.js, env.js, vendor/ (Chart.js), vercel.json. Hash routing means no rewrites are needed.

Set `window.RV_API_BASE` BEFORE first deploy (env.js is static; it is not a Vercel env var).

## 4. Verify

1. Open the Vercel URL, log in with a user you created on the backend (register through the UI).
2. Create a store, upload a demo clip from `data/videos_demo/`, run an analysis.
3. Check the analysis page (heatmap, events) loads media from the backend origin.

## 5. Security before real use

- Replace `*` CORS with the exact frontend origin.
- Add rate limiting, API-key auth for the inference endpoints, and backups of `/data`.
- Media endpoints are currently open for playback; protect them if the backend is public.
- Legal review (Indian DPDP framework etc.) is required before commercial deployment; see KNOWN_LIMITATIONS.md.
