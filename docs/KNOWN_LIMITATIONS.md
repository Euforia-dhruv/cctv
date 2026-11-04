# RetailVision AI: Known Limitations (MVP)

We prefer honest limits over implied capabilities.

## Counting and analytics

- Unique-visit numbers are estimates derived from single-camera tracking
  (occlusion, camera angle, people leaving/re-entering). Not exact headcounts.
- Entry/exit counts exist only when entrance/exit zones are configured; without
  zones these fields are null, not guessed.
- Dwell time is approximate (tracked time in view; includes waits).
- Queue and congestion flags are heuristics with confidence labels, not
  guaranteed measurements. They can be wrong.

## Detectors

- Spill/debris and unattended-object detection is experimental (background-
  subtraction heuristic). It requires a mostly static camera and decent
  contrast; it will miss and will over-flag. Always human-reviewed.
- "Unusual movement pattern" is a motion heuristic, not intent inference.
  We never label a person as a thief; every observation is neutral and review-
  required.

## Hardware and scale

- One video at a time; frame sampling reduces accuracy on very fast motion.
- CPU mode is usable but slow; GPU strongly recommended.
- No live RTSP/YouTube ingestion yet (file upload only).

## Privacy / legal

- No facial recognition, no biometrics, no demographics, no cross-camera
  matching. Temporary anonymous tracking IDs only.
- The prototype stores footage and thumbnails locally. This is NOT a claim of
  DPDP (or any other law) compliance. A formal legal review is required before
  any commercial deployment in India or elsewhere.
- Requirements.txt demo clips are free-license stock footage; do not present
  them as real store footage.

## Security (prototype)

- Token auth without TLS by default (dev). In production: reverse proxy with
  TLS, rate limiting, secrets management, key rotation, encrypted storage,
  role-based admin for model changes, and a proper SSO option.
- No multi-tenancy isolation hardening; single-org use.
- Video storage is unencrypted on disk; production should encrypt at rest.

## Not implemented in MVP (planned)

- Live camera streams, YouTube ingest, cross-camera tracking
- Automated training loop (feedback collection + dataset preparation only)
- PostgreSQL, object storage, hosted GPU inference
- Notifications beyond in-app bell; no email
- Full BI export (CSV/JSON only; chart screenshots manual)
- Queue length in meters; sales/conversion attribution; zone-drawing UI
  (zones can be supplied via API config for now)
