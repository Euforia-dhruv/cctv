# RetailVision AI: Demo Guide (for mall operators / DMart-style audiences)

## Story arc (about 5 minutes)

1. **Problem setup (30s):** "You already record CCTV. Today it is only used
   reactively. RetailVision turns existing recordings into operational numbers
   and reviewable observations, with no new hardware and no facial recognition."
2. **Upload (60s):** create a store, upload a real clip from `data/videos_demo/`
   (or any authorized store footage). Show the validation and the job queuing.
3. **Processing (60s):** show the live progress. Explain: YOLO26n person
   detection (real pretrained model, ~2.4M params), an IoU tracker issuing
   temporary anonymous IDs, frame sampling (every 3rd frame), GPU when present.
4. **Results (2 min):** on the analysis page show:
   - People observed (detections) vs unique visit estimate; say clearly this is
     an estimate within camera limits, not an exact headcount.
   - Traffic-per-minute chart and busy periods.
   - Heatmap: "generated from the tracked positions you just saw."
   - Events: open one, jump to the video timestamp, review and resolve; save a
     corrected label as model feedback.
   - Export CSV/JSON report.
5. **Trust & privacy (30s):** no faces, no biometrics, anonymous IDs,
   local storage, human review before any action. Show the Settings > Privacy
   section.

## Talking points that keep you credible

- Never say "we count customers exactly". Say "visit estimates within camera
  tracking limits".
- Queue/congestion and spill/debris detectors are labeled experimental; demo
  them as "flags for staff to check", not as facts.
- Foot traffic near a display is exposure, not sales; say that explicitly.

## What could go wrong

- First YOLO run downloads weights; do it once before the live demo.
- CPU-only machines are slower (~a few minutes per short clip); pre-run the
  analysis before the demo and show a completed analysis too.
- Videos that are mostly one stationary person generate few events; that is
  honest data, and you can explain the settings (thresholds) if asked.

## Pre-demo checklist

- [ ] `.\run.bat` running, page opens
- [ ] Demo account works
- [ ] One analysis already completed and visible in Overview
- [ ] Upload one fresh clip during the demo (have it ready)
- [ ] Model page shows device (cuda vs cpu)
