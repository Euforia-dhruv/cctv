# RetailVision AI: Known Limitations (MVP)

We prefer honest limits over implied capabilities.

## Counting and analytics

- Unique-visit numbers are estimates derived from tracking (occlusion, camera
  angle, people leaving/re-entering). Not exact headcounts.
- Entry/exit counts exist only when entrance/exit zones are configured; without
  zones these fields are null, not guessed.
- Dwell time is approximate (tracked time in view; includes waits).
- Queue and congestion flags are heuristics with confidence labels, not
  guaranteed measurements. They can be wrong.
- **Small people are the binding constraint.** The detector needs a person to be
  a reasonable fraction of its input. On a wide, elevated view (a 640x360 mall
  atrium, people ~40px tall) a whole-frame pass found 3 people in a visibly
  crowded scene. The pipeline now measures detected person height on a few
  frames and switches to overlapping 3x3 tiles when people are too small, which
  found 33 people on the same frame. This is automatic; the chosen grid and the
  measured person height are recorded in the analysis result.
- Tiling costs roughly 4x a whole-frame pass. On this laptop a one-hour 640x360
  recording takes tens of minutes. Long recordings are the expensive case, not
  the model.

## Camera walls (multi-camera mosaic footage)

Some uploads are not one camera but a grid of cameras in a single video (e.g. a
4x4 wall from a DVR export). RetailVision detects this automatically from the
footage and switches to per-camera analysis; nothing is assumed about the layout.

Hard limits, measured on a real 4x4 640x360 recording:

- **Resolution is the ceiling.** In a 640x360 wall each camera is ~160x90 px,
  so a standing person is ~40 px tall. Detection works but confidence is low
  (0.3-0.7) and small or distant people are missed. A 1080p wall would give
  ~3x more detail per camera; 4K more still.
- **Frame sampling is coarser.** A wall costs one inference per camera per
  frame, so long recordings are sampled more sparsely to bound processing time.
  The actual interval is reported on the analysis page. Fast crossings between
  samples are missed.
- **No cross-camera re-identification.** A person walking from CAM 03 to CAM 04
  is counted twice, and visit counts are per camera. They are never summed
  across cameras into a "unique people" figure, because that would be a
  fabricated number.
- **Queue/congestion clustering runs per camera**, so people in unrelated
  cameras are never treated as one queue.
- **Blob heuristics are disabled on walls** (spill/debris, unattended object):
  background subtraction across 16 unrelated scenes produces noise, not
  evidence.
- Cameras showing "NO SIGNAL" or black frames contribute nothing, which is
  correct, not a bug.
- **The heatmap is normalised per camera on a wall**, so colour shows each
  camera's own hotspots. Comparing intensity between two cameras is not
  meaningful, only within one. Use the per-camera visit table for comparison.

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
- A camera-wall upload costs one inference per camera per frame (~4.3x a
  single-camera pass for a 4x4 wall), so walls are slower than single views on
  identical hardware.
- No live RTSP/YouTube ingestion yet (file upload only). A YouTube URL must be
  downloaded first; the downloader is not part of the app.

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
