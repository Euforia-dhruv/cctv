"""Detector adapter. The app talks to this interface only, so the model can be
swapped (YOLO26n -> YOLOv8n -> ONNX -> hosted API) without touching pipeline code."""
from __future__ import annotations

import threading
from typing import List

import numpy as np

from .. import config

Det = tuple[float, float, float, float, float]  # x1,y1,x2,y2,conf


class Detector:
    def __init__(self, model_id: str, conf: float, imgsz: int, device: str):
        self.model_id = model_id
        self.conf = conf
        self.imgsz = imgsz
        self.device = self._resolve_device(device)
        self._model = None
        self._lock = threading.Lock()

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device in ("cuda", "cpu"):
            return device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def _load(self):
        if self._model is not None:
            return
        from ultralytics import YOLO
        # Model files auto-download from Ultralytics releases on first use.
        self._model = YOLO(self.model_id)

    def detect(self, frame: np.ndarray) -> List[Det]:
        return self.detect_many([frame])[0]

    def detect_many(self, frames: list) -> List[List[Det]]:
        """Batch inference. Returns one detection list per input frame, in order."""
        with self._lock:
            self._load()
            results = self._model.predict(
                source=list(frames), conf=self.conf, imgsz=self.imgsz,
                device=self.device, classes=[0], verbose=False,
            )
        out: List[List[Det]] = []
        for r in results:
            dets: List[Det] = []
            box = r.boxes
            if box is not None and len(box) > 0:
                for (x1, y1, x2, y2), c in zip(box.xyxy.cpu().numpy(),
                                               box.conf.cpu().numpy()):
                    dets.append((float(x1), float(y1), float(x2), float(y2), float(c)))
            out.append(dets)
        return out

    def meta(self) -> dict:
        m = config.get_model_meta(self.model_id)
        return {"model_id": self.model_id, "display": m["display"],
                "version": m["version"], "license": m["license"],
                "device": self.device, "conf": self.conf,
                "imgsz": self.imgsz}
