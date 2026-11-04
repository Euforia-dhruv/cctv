# RetailVision AI Product Requirements Document (MVP)

## 1. Product vision

RetailVision AI turns existing store CCTV footage into measurable operational insights, security observations, and retail analytics, without new hardware. A retailer uploads (or later connects) a camera feed, and the platform detects people, tracks them anonymously, and reports traffic, dwell, heatmaps, congestion, operational alerts, and review-required observations in a CRM-style dashboard.

## 2. Target customers

- Mall operators, supermarket chains (DMart profile), standalone stores with existing CCTV.
- Store operations managers, loss-prevention/security heads, marketing/merchandising teams.

## 3. User roles

| Role | Capabilities |
|---|---|
| Admin | manage stores, cameras, users, settings, model config, retention |
| Analyst/Manager | view dashboards, upload videos, run analyses, export reports, add zones |
| Reviewer | review incidents, add notes, resolve observations, provide model feedback |

Role-based access is implemented (role field on users); the UI targets the Manager/Reviewer as primary.

## 4. Core use cases

1. Upload an authorized CCTV recording and get an analysis job run with real inference.
2. See traffic/unique-visit estimates, busy periods, dwell, occupancy.
3. See a per-analysis heatmap from real track coordinates.
4. Review operational alerts (possible spill/debris, unattended object) and security observations (restricted zone, unusual movement) with timestamps and video links.
5. Export a report (CSV/JSON) and check model metadata.

## 5. MVP scope (in)

- File upload (MP4/MOV/AVI), validation, one video at a time.
- Detection + tracking + analytics + heatmap + event review + reports + settings.
- Auth, stores, cameras, videos, jobs, audit log.

## 6. Out of scope for MVP (future)

- Live RTSP/YouTube ingestion, cross-camera identity, device/edge deployment, training-loop execution (only feedback collection), multi-tenant cloud, PostgreSQL, mobile apps, paid plan.

## 7. User journeys

- New store: sign in, create store, add camera (optional), upload video, job runs, open analysis page, view heatmap, open an event, jump to timestamp, resolve it, export report.
- Frame: onboarding with a sample video already analyzed so the dashboard is never empty in demo mode; sample data is clearly labeled demo.

## 8. Functional requirements (selection)

- FR1 Upload: validate extension, size limit (1 GB), real video (OpenCV probe), store file, create video record.
- FR2 Job: status lifecycle queued/running/done/failed, progress %, current stage, error message, retry.
- FR3 Inference: person detection, tracking IDs, per-frame occupancy, confidence threshold config.
- FR4 Analytics: totals (detections, unique-visit estimate, entries/exits where configured), per-minute traffic series, busy/quiet periods, dwell stats, zone exposure, congestion events.
- FR5 Heatmap: generated from real coords, with overlay on a reference frame, zone rendering.
- FR6 Events: type, timestamp, video time, confidence/evidence, status (open/reviewing/resolved/confirmed/dismissed), reviewer notes, linked frame thumbnail, jump-to-time.
- FR7 Reports: CSV export of events and analytics summary; JSON export for API consumption.
- FR8 Model page: show model id, version, source, device, thresholds, config, and feedback dataset size; allow saving reviewed examples.
- FR9 Settings: store list, camera list, uploads list, account, logout, retention note.

## 9. Non-functional requirements

- Performance: analytics of a 10-minute 720p clip should finish in a few minutes on the laptop (measured; no unmeasured FPS claims).
- Lightweight: memory under 8 GB, no background services beyond the app.
- Privacy: no faces stored beyond frame thumbnails for review (documented), no biometrics, anonymous IDs only; review thumbnails are stored locally by default.
- Usability: responsive, keyboard accessible, states (empty/loading/error) present.
- Reliability: graceful errors, progress reporting, job resumability on restart (job table persists).

## 10. Data model (logical)

users, sessions, stores, cameras, videos, jobs, analyses, tracks, events, reviews, model_config, audit_log, notifications.

## 11. API requirements

REST under /api; JSON; bearer-token auth; authorization checks on store-scoped resources; OpenAPI docs at /docs. Endpoints listed in ARCHITECTURE.md.

## 12. Privacy requirements

- No facial recognition, no biometric identification, no demographic profiling, no cross-camera identity matching.
- Temporary anonymous tracking IDs only.
- Configurable retention and deletion (documented; UI delete for videos/analyses).
- Human review for security-related observations; neutral labels only.
- Only process footage the user is authorized to hold; consent field on upload.
- India DPDP: the MVP is a local prototype and is not claimed to be DPDP-compliant; a legal review is required before commercial deployment in India. Documented in KNOWN_LIMITATIONS.md.

## 13. Acceptance criteria (MVP complete when)

1. Launch locally (one command) and log in.
2. Upload an authorized video; validation works; job runs.
3. Real pretrained model detects persons (visible on analysis page).
4. Tracking IDs appear; metrics computed from actual track data.
5. Heatmap generated from actual coordinates.
6. Events reviewable with timestamp links into the video.
7. Analytics in dashboard (no hardcoded metrics).
8. Reports export.
9. Reviewer feedback saved; model metadata visible.
10. CPU fallback works; GPU tested when available.
11. Errors handled gracefully; empty/loading/error states exist.
12. Setup + demo documentation exists; sample video documented.

## 14. Known limitations (summary)

Full list in KNOWN_LIMITATIONS.md. Headline: single camera, estimates not exact counts, experimental detectors labeled, no legal compliance claims.
