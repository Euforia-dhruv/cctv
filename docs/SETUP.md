# RetailVision AI: Setup

## Requirements (target laptop)

- Windows 10/11, Python 3.13
- NVIDIA GPU (CUDA-capable) optional; CPU fallback supported
- ~4 GB free disk for pip packages (CUDA torch wheel is ~3 GB)

## 1. One-time install

```powershell
cd D:\New folder (2)\retailvision
# create venv that sees the system torch (if any)
python -m venv --system-site-packages .venv
# CPU/GPU-agnostic runtime deps
.\.venv\Scripts\pip.exe install -r backend\requirements.txt
# CUDA-enabled torch (REPLACES any CPU torch in this venv)
.\.venv\Scripts\pip.exe install torch==2.11.0+cu128 torchvision==0.26.0+cu128 --index-url https://download.pytorch.org/whl/cu128
# verify GPU
.\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"
```

If you do not want CUDA, skip the torch line; the app will use CPU automatically.

## 2. Run

```powershell
.\run.bat
```

Open http://127.0.0.1:8000

Demo login: click "Use demo account" on the sign-in page (creates `demo@retailvision.ai` / `demo1234`).

## 3. First run checklist

1. Create a store (Overview -> Stores -> + New store).
2. Open the store -> upload a CCTV clip (MP4/MOV/AVI). Confirm authorization.
3. Open the video -> "Analyze video". The first run downloads the YOLO weights
   (one-time) and then processes.
4. When the job completes you land on the analysis page: heatmap, traffic,
   events, video timeline.

## 4. Configuration

Defaults live in `backend/app/config.py`. Model/threshold settings are exposed
in the Model page; per-job overrides can be posted to
`POST /api/videos/{id}/analyze` with JSON like
`{"model":"yolov8n.pt","conf":0.4,"sample_step":2}`.

## 5. Demo videos

`data/videos_demo/` ships with four free-license clips from Mixkit (free
commercial license, no attribution required; see their license page).  It is
documented as demo footage in the UI/docs.

## 6. Tests

```powershell
cd backend
.\.venv\Scripts\python.exe tests\test_core.py
```
