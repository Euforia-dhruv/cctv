# RetailVision AI: AI Model Evaluation

Scope: choose a person detector for CCTV footage on the target laptop, and a tracking approach. Benchmarks on this laptop are in BUILD_REPORT.md; values below are vendor-published figures or measured-later placeholders. Nothing is invented.

## 1. Detector candidates (with evidence)

| Metric | YOLO26n | YOLO26s | YOLOv8n | YOLO11n | RT-DETR-R18 | YOLOX-s |
|---|---|---|---|---|---|---|
| Params | 2.4M | 9.5M | 3.2M | 2.6M | ~20M | 9.0M |
| mAP50-95 (COCO val) | 40.9 | 48.6 | 37.3 | 39.5 | 46.5 | 40.5 |
| Speed CPU ONNX (ms/img) | 38.9 | 87.2 | ~50 | ~40 | ~250 | ~120 |
| Speed GPU TensorRT T4 (ms/img) | 1.7 | 2.5 | ~2 | ~1.7 | n/a | n/a |
| VRAM @ batch 1, 640px (est.) | <1GB | ~1.2GB | <1GB | <1GB | ~2GB | ~1.5GB |
| License | AGPL / Enterprise | AGPL / Enterprise | AGPL / Enterprise | AGPL / Enterprise | Apache-2.0 | Apache-2.0 |
| Source of numbers | [verified] Ultralytics README (fetched 2026-11-05) | same | [knowledge] | [knowledge] | [knowledge] | [knowledge] |

Notes:
- YOLO26n numbers are from the official Ultralytics README tables fetched during this build (mAP 40.9, CPU ONNX 38.9ms, TensorRT 1.7ms). Updated as of release.
- RT-DETR-R18 and YOLOX-s are the Apache-2.0 alternatives if AGPL is unacceptable; they are heavier on CPU-only operation. This is the documented commercial-license fallback path.

## 2. Decision

- Default model: YOLO26n (best accuracy per resource on this laptop). Fallback config: YOLOv8n (most battle-tested) if YOLO26 download or run has any issue on this machine. Both are swappable through the model adapter without touching app code.

## 3. Tracking evaluation

| Approach | License | Verdict |
|---|---|---|
| ByteTrack (MIT) | MIT | reference algorithm; we do not copy code, we implement the same association concept (IoU + motion). |
| BoT-SORT (in ultralytics) | AGPL context | avoided: heavier, includes ReID features we explicitly do not want |
| DeepSORT | GPL-3.0 | avoided for license and ReID |
| Custom IoU tracker | our own | chosen. ~100 lines; confidence gating, velocity prediction, track lifecycle. Matches "temporary anonymous IDs" requirement. |

## 4. Feature-to-model mapping (what is real vs experimental)

| Feature | Method | Status |
|---|---|---|
| Person detection | YOLO26n (coco person class) | production (prototype) |
| Multi-object tracking | custom IoU tracker | production (prototype) |
| Unique-visit estimate | track lifecycle + dwell filter | production; labeled estimate |
| Traffic bins / busy periods | per-minute track counts | production |
| Dwell time | per-track duration | production; approximate |
| Heatmap | density grid from track positions | production |
| Occupancy over time | per-frame person count | production |
| Zone exposure | configured polygons + track time inside | production |
| Queue/congestion | stationary-track + zone-density heuristics | experimental, confidence-labeled |
| Spill/debris | MOG2 static-blob heuristic | experimental, review-required |
| Unusual movement | motion heuristics | experimental, review-required |
| Unattended object | static-blob heuristic | experimental, review-required |
| Restricted-zone entry | polygon intersection | production |
| Sales/conversion attribution | not attempted | out of scope; exposure only |
| Face/biometric/demographic | not attempted | out of scope (privacy) |

## 5. Tuning defaults (conservative)

- Input: 640x640 (matches training distribution), person class only.
- Confidence: 0.35 default (configurable 0.2-0.6).
- Frame sampling: every 3rd frame at 30fps (~10Hz), configurable.
- Tracker: max lost frames 8, IoU threshold 0.3, min track length 2 detections.
- These are starting points; BUILD_REPORT.md records measured results and any tuning.
