# RetailVision AI backend (CPU inference). GPU hosting is a later step:
# swap the torch install line for the CUDA wheel and add a GPU instance.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    RV_DATA_DIR=/data

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --quiet torch \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --quiet -r requirements.txt

COPY backend/app ./app

VOLUME ["/data"]
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
