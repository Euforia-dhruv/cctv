# RetailVision AI: Build Report (MVP)

Date: 2026-11-05. Machine: Intel Core i5-11400H (6C/12T), NVIDIA RTX 3050 Laptop 4GB, 16GB RAM, Windows.

## 1. Implemented features

- Auth: register/login (PBKDF2, bearer token), roles (admin/analyst/reviewer).
- Stores & cameras management; video upload (MP4/MOV/AVI, validation, size limit, consent flag).
- Job system: queue, progress %, stage, errors, one video at a time.
- Real CV pipeline: YOLO26n person detection + custom IoU tracker (anonymous IDs).
- Analytics from tracked data: detections, unique-visit estimate, occupancy avg/peak, dwell avg/median, per-minute traffic series, busy periods, zone exposure hooks.
- Heatmap rendered from actual track coordinates (with legend).
- Events: operational (debris/spill experimental, unattended object experimental), security (restricted zone entry, unusual movement, prolonged presence), queue/congestion heuristics; all human-reviewed with thumbnails, video jump-to-time, status workflow, reviewer notes.
- Model feedback: corrected labels collected into a dataset (training pipeline not included).
- Reports: CSV + JSON export per analysis.
- Dashboard: Overview, Stores, Videos, Analysis (player + timeline + charts + review), Traffic, Heatmaps, Incidents, Alerts, Reports, Model, Settings, Audit, Notifications. All numbers come from the database; no hardcoded metrics.
- Demo footage: 9 free-license Mixkit clips in `data/videos_demo/`; `seed_demo_analysis.py` creates the demo store/upload/analysis.

## 2. Features not implemented (documented)

- Live RTSP/YouTube ingestion, cross-camera tracking, facial/biometric analytics.
- Model training loop (feedback collection only). ONNX export not automated.
- PostgreSQL, object storage, hosted GPU API (architecture designed, see ARCHITECTURE.md).
- Zone-drawing UI (zones configurable via API JSON only).
- Email notifications, multi-tenancy hardening, TLS in dev.

## 3. Tests executed

| Test | Result |
|---|---|
| Core unit tests (iou, tracker sequence, crossing, occlusion, zones, analytics, alert heuristics) | 25/25 passed |
| API E2E (register → store → upload → analyze → poll → analysis → tracks/events → review → feedback → CSV) | passed |
| Browser checks (login, overview, analysis page, incidents, model, videos; console clean) | passed |
| CPU fallback scan across all demo clips | passed |
| GPU inference benchmark | ran, numbers below |

## 4. Hardware benchmark (measured on this laptop)

- Inference latency, YOLO26n @640, conf 0.35, batch 1:
  - GPU (CUDA 12.8): 36.2 ms/frame → ~27.7 FPS
  - CPU: 68.8 ms/frame → ~14.5 FPS
  - GPU ≈ 1.9x CPU.
- Full pipeline (decode + pre/post + tracking, hero clip 39.8s, sample_step 3): ~62 ms/frame GPU average; job completed in ~75 s including model warmup.
- Hero analysis (mall_23249): 1082 detections, 13 unique-visit estimate, avg occupancy 3.26, peak 7, dwell avg 9.8s, 3 review-required events.

## 5. Model and dependency versions

| Component | Version |
|---|---|
| Ultralytics | 8.4.202 |
| Detector | YOLO26n (AGPL-3.0 / Enterprise; fallback YOLOv8n available) |
| PyTorch | 2.11.0+cu128 (CUDA 12.8) |
| torchvision | 0.26.0+cu128 |
| OpenCV | 4.x (bundled with pip install) |
| FastAPI / Uvicorn | latest from PyPI |
| Python | 3.13.15 |
| Chart.js | 4.4.9 (vendored, MIT) |
| Database | SQLite (WAL) |

## 6. Known limitations

See `KNOWN_LIMITATIONS.md`. Headlines: visit estimates not exact counts; queue/debris detectors are experimental; single camera; not DPDP-compliant; prototype security (no TLS by default).

## 7. Security considerations

- Token auth; role checks; audit log; upload consent recorded; files stored locally; media endpoints open to anonymous for playback (single-org prototype, documented).
- Production deployment requires TLS, rate limiting, encrypted storage, secret management, and legal/DPDP review.

## 8. Run the demo

```
cd D:\New folder (2)\retailvision
.\run.bat
# open http://127.0.0.1:8000, click "Use demo account"
# or: python backend/tests/seed_demo_analysis.py (with server up)
```
See `SETUP.md` and `DEMO_GUIDE.md`.
