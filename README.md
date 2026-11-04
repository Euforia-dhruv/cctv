# RetailVision AI

AI-powered retail CCTV intelligence platform. Upload authorized store footage, run real computer-vision inference (person detection + anonymous tracking), and review traffic, dwell, heatmaps, congestion, operational alerts, and security observations in a CRM-style dashboard.

This is a working local prototype for demo to retailers (mall operators, supermarkets, DMart profile). It processes actual video with a pretrained YOLO26n model; all dashboard numbers come from real inference stored in SQLite.

## Quick start

```
python -m venv --system-site-packages .venv
.\.venv\Scripts\pip.exe install -r backend\requirements.txt
# optional GPU: install CUDA torch (see docs/SETUP.md)
.\run.bat
```

Open http://127.0.0.1:8000 → "Use demo account".

## Repo layout

```
backend/app/        FastAPI app (routes, db, cv/)
backend/tests/      unit tests, E2E, scan, benchmark, demo seed
frontend/           SPA (HTML/CSS/JS + vendored Chart.js)
data/videos_demo/   free-license demo clips (Mixkit)
data/               runtime data (uploads, artifacts, SQLite)
docs/               research, PRD, architecture, setup, demo guide, limitations, build report
```

## Docs

- `docs/PRD.md`, `docs/RESEARCH.md`, `docs/COMPETITOR_ANALYSIS.md`
- `docs/TECH_STACK_DECISIONS.md`, `docs/AI_MODEL_EVALUATION.md`
- `docs/ARCHITECTURE.md`, `docs/SETUP.md`, `docs/DEMO_GUIDE.md`
- `docs/KNOWN_LIMITATIONS.md`, `docs/BUILD_REPORT.md`

## Notes

- No facial recognition, no biometrics, anonymous IDs, human review for observations.
- Visit counts are estimates within camera limits; queue/debris flags are experimental.
- Demo clips are free-license stock footage, not real store recordings.
