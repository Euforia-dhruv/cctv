# RetailVision AI backend (CPU inference). GPU hosting is a later step:
# swap the torch install line for the CUDA wheel and add a GPU instance.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    RV_DATA_DIR=/data

WORKDIR /app

# opencv-python requires libGL/libglib at runtime on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --quiet torch \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --quiet -r requirements.txt

COPY backend/app ./app

# Fail the build fast if any import is broken (e.g. cv2/libGL, torch, app).
RUN python -c "import cv2, torch; from app.main import app; print('imports ok')"

VOLUME ["/data"]
EXPOSE 8000

# Render injects $PORT (e.g., 10000); local default stays 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
