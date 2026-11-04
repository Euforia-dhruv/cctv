"""Heatmap rendering from tracked positions (real data only)."""
from __future__ import annotations

from pathlib import Path
from typing import List

import cv2
import numpy as np
from PIL import Image

from .tracker import Track


def build_heatmap(tracks: List[Track], frame: np.ndarray, out_path: Path,
                  cells=(36, 22), scale: float = 1.0) -> Path:
    h, w = frame.shape[:2]
    ch, cw = 36, 22
    grid = np.zeros((cw, ch), dtype=np.float32)
    for trk in tracks:
        for _t, cx, cy in trk.path:
            gx = min(int(cx / w * ch), ch - 1)
            gy = min(int(cy / h * cw), cw - 1)
            grid[gy, gx] += 1.0
            # small neighborhood blur approximation
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = gy + dy, gx + dx
                    if 0 <= yy < cw and 0 <= xx < ch:
                        grid[yy, xx] += 0.25

    if grid.max() > 0:
        grid = grid / grid.max()

    # Resize grid to frame size and colorize (transparent overlay).
    heat = cv2.resize(grid, (w, h), interpolation=cv2.INTER_CUBIC)
    heat_uint8 = (heat * 255).astype(np.uint8)
    colored = cv2.applyColorMap(heat_uint8, cv2.COLORMAP_JET)

    base = frame.copy()
    mask = heat > 0.05
    base[mask] = (base[mask] * 0.45 + colored[mask] * 0.55).astype(np.uint8)

    # Legend bar (color scale).
    bar_w = max(24, int(w * 0.03))
    bar = np.zeros((int(h * 0.3), bar_w, 3), dtype=np.uint8)
    for i in range(bar.shape[0]):
        v = 255 - int(i / bar.shape[0] * 255)
        bar[i, :] = cv2.applyColorMap(np.full((1, 1), v, np.uint8), cv2.COLORMAP_JET)[0, 0]
    x0 = w - bar_w - 12
    y0 = 12
    base[y0:y0 + bar.shape[0], x0:x0 + bar_w] = bar
    cv2.putText(base, "low", (x0 - 34, y0 + 14), cv2.FONT_HERSHEY_SIMPLEX,
                0.45, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(base, "high", (x0 - 38, y0 + bar.shape[0] - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    if scale != 1.0:
        base = cv2.resize(base, (int(w * scale), int(h * scale)))
    cv2.imwrite(str(out_path), base)
    return out_path


def save_reference(frame: np.ndarray, out_path: Path) -> Path:
    cv2.imwrite(str(out_path), frame)
    return out_path
