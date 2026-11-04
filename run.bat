@echo off
REM Launch RetailVision AI locally. Run from the repo root.
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
  echo Setting up virtual environment...
  python -m venv --system-site-packages .venv
)
set PYTHONPATH=%CD%\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
