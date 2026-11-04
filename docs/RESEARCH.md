# RetailVision AI: Research Notes

Status: completed for MVP, 2026-11-05.
Method: live web search was unavailable in this environment (search API returned 402), so verification used the package registry (pip index), direct fetches of official repositories and vendor pages, and installed tooling. Every claim below is marked with its source: [verified] (checked against a primary source during this build) or [knowledge] (from training knowledge, re-verify before a commercial decision).

## 1. Hardware baseline (measured on the target laptop)

| Item | Value | Source |
|---|---|---|
| CPU | Intel Core i5-11400H, 6 cores / 12 threads | [verified] device query |
| GPU | NVIDIA GeForce RTX 3050 Laptop, 4 GB VRAM, driver 610.74, CUDA 13.3 | [verified] nvidia-smi |
| RAM | 16 GB DDR4 | [verified] device query |
| OS | Windows (PowerShell 7) | [verified] |
| Python | 3.13.15 | [verified] python --version |
| PyTorch | 2.15.0 installed (CUDA build check pending) | [verified] pip index |
| Ultralytics | 8.4.202 available (latest) | [verified] pip index |

Implications: choose small models (nano/small), batch size 1, 640 px input, and sample frames (not every frame). 4 GB VRAM is the hard ceiling; detection on 640x640 nano models fits comfortably.

## 2. Person detection models considered

| Model | Params | mAP50-95 (COCO) | CPU ONNX (ms) | GPU T4 TensorRT (ms) | License | Notes |
|---|---|---|---|---|---|---|
| YOLO26n (Ultralytics) | 2.4 M | 40.9 | 38.9 | 1.7 | AGPL-3.0 or Enterprise | [verified] official README table (fetched). Newest family, fastest per accuracy |
| YOLO26s | 9.5 M | 48.6 | 87.2 | 2.5 | AGPL-3.0 or Enterprise | [verified] same source |
| YOLOv8n (Ultralytics) | 3.2 M | 37.3 | ~50 | ~2 | AGPL-3.0 or Enterprise | [knowledge] stable, heavily deployed |
| YOLO11n | 2.6 M | 39.5 | ~40 | ~1.7 | AGPL-3.0 or Enterprise | [knowledge] |
| YOLOX-s | 9.0 M | 40.5 | ~120 (ONNX) | - | Apache-2.0 | [knowledge] Apache licensed, heavier CPU latency |
| RT-DETR-R18 | 20 M | 46.5 | ~250 | - | Apache-2.0 | [knowledge] from PaddleDetection; strong accuracy, heavier, transformer decoder |
| RT-DETR-R50 | 42 M | 53.1 | ~600 | - | Apache-2.0 | [knowledge] too heavy for this laptop CPU |
| EfficientDet-D0 | 3.9 M | 34.6 | ~80 | - | Apache-2.0 | [knowledge] TensorFlow ecosystem, less convenient |
| MobileNet-SSD v2 | ~6.8 M | ~22 | ~40 | - | Apache-2.0 | [knowledge] too weak for small persons |
| DETR / Deformable DETR | 41 M | 43.8 / 46.2 | very slow | - | Apache-2.0 | [knowledge] not suitable for laptop |

Decision: YOLO26n primary, YOLOv8n fallback (both exposed through the adapter; the app is not coupled to one model). License caveat: Ultralytics weights and code are AGPL-3.0. For a demo prototype that is acceptable; for a commercial product, either buy the Ultralytics Enterprise license or switch the adapter to an Apache-2.0 model (YOLOX-s, RT-DETR-R18) which we keep as a documented path.

## 3. Tracking algorithms

| Solution | License | Fit |
|---|---|---|
| ByteTrack | MIT | [knowledge] proven association strategy; reference design |
| BoT-SORT | mirrors Ultralytics repo (AGPL) | shipped inside ultralytics; heavier, includes ReID embedding which we do not want |
| DeepSORT | GPL-3.0 | [knowledge] not suitable for commercial use without care |
| Custom IoU / centroid tracker | our own code (MIT-style) | chosen for MVP |

Decision: implement a lightweight IoU tracker with constant-velocity prediction, track lifecycle (new/active/lost), and no appearance model. This is honest, license-clean, and enough for one camera, one angle. It matches the "temporary anonymous tracking IDs" requirement and avoids cross-camera identity matching entirely.

## 4. Crowd counting and people flow

- Density-estimation networks (CSRNet, DM-Count) need training on crowd datasets and are not reliable zero-shot. [knowledge]
- For MVP, counting = detection + tracking headcount ("estimated unique visits within tracking limits"), clearly labeled, never presented as exact customer counts.
- People flow: derived from track direction and entry/exit zone crossing; only where the camera view allows a truthful zone config. [design decision]

## 5. Queue and congestion

- No zero-shot queue model is reliable enough to claim. [knowledge]
- MVP approach: occupancy heuristics per configured zone (stationary-track ratio, zone density, sustained period). All queue/ congestion outputs carry confidence and limitations. We do not fabricate queue length when footage cannot support it.

## 6. Heatmaps

- Generated from tracked foot (bbox-bottom-center) coordinates accumulated over time, rendered as a density overlay. Implementation: grid accumulation + PIL gradient render. [design]

## 7. Spill, debris, operational hazard detection

- No pretrained, generally available spill detector is accessible/licensed cleanly for this build. [knowledge]
- MVP approach: background-subtraction (MOG2) finds static foreground blobs that persist (no person overlap) for a threshold duration, raised as "Possible obstacle / debris (experimental)" with a review workflow. Honest labeling. 

## 8. Unusual activity / security observations

- Automatic accusation is explicitly out of scope. We generate neutral "review required" observations from heuristics: prolonged presence, erratic movement, restricted-zone entry, unattended static blob. Human review is the resolution step. [design]

## 9. Video processing and storage architecture

- Local files + SQLite metadata; artifacts organized under data/artifacts/<analysis_id>/. 
- Future: object storage; the analysis artifact layout stays stable so a storage backend swap does not touch the app. [design]

## 10. Local vs hosted inference

- Local: torch CUDA (RTX 3050) with CPU fallback; measured in BUILD_REPORT.md.
- Future: keep inference as an adapter so it can be moved to a GPU host (API stub described in ARCHITECTURE.md). No inference host is required for the MVP. [design]

## 11. Hosting options for a future demonstration (low/zero cost)

- RunPod / Lambda GPU pods: pay-as-you-go, cheap for short demos. [knowledge]
- Hugging Face Inference Endpoints / Replicate / Modal: serverless, per-second billing. [knowledge]
- Colab free/paid GPU: quick path for demos. [knowledge]
- All prices change; re-verify at the time of use. None are needed for the local MVP.

## 12. License summary (important)

| Component | License | Commercial note |
|---|---|---|
| Ultralytics models (YOLO26n/8n) | AGPL-3.0 / Enterprise | Buy Enterprise for closed commercial product, or swap adapter to Apache model |
| ByteTrack (reference design) | MIT | fine |
| FastAPI, Starlette, Uvicorn | MIT / BSD | fine |
| SQLite | public domain | fine |
| OpenCV | Apache-2.0 | fine |
| PyTorch | BSD-style | fine |
| Chart.js | MIT | fine |
| Mixkit demo videos | free license (no attribution required) | [verified] mixkit.co license page; can be used in demos, not resold unmodified |

## 13. What we deliberately did not do

- No training on this laptop (would violate constraints).
- No large models, no batches, no GPU-hungry backbones.
- No Redis/Kafka/Kubernetes/Postgres for the MVP (see TECH_STACK_DECISIONS.md).
- No cloud upload of private footage.
