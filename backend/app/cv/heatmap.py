"""Heatmap rendering from tracked positions (real data only)."""
from __future__ import annotations

from pathlib import Path
from typing import List

import cv2
import numpy as np
from PIL import Image

from .tracker import Track


def build_heatmap(tracks: List[Track], frame: np.ndarray, out_path: Path,
                  cells=(36, 22), scale: float = 1.0,
                  grid_spec: dict | None = None) -> Path:
    h, w = frame.shape[:2]
    cols, rows = int(cells[0]), int(cells[1])
    grid = np.zeros((rows, cols), dtype=np.float32)
    for trk in tracks:
        for _t, cx, cy in trk.path:
            gx = min(int(cx / w * cols), cols - 1)
            gy = min(int(cy / h * rows), rows - 1)
            grid[gy, gx] += 1.0
            # small neighborhood blur approximation
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = gy + dy, gx + dx
                    if 0 <= yy < rows and 0 <= xx < cols:
                        grid[yy, xx] += 0.25

    if grid.max() > 0:
        if grid_spec:
            # A wall has 16 independent scenes. Normalising by one global max
            # would let the busiest camera flatten every other camera to zero,
            # so each camera is scaled against its own peak.
            for r in range(grid_spec["rows"]):
                for c in range(grid_spec["cols"]):
                    gx0 = int(grid_spec["xs"][c] / w * cols)
                    gx1 = max(gx0 + 1, int(grid_spec["xs"][c + 1] / w * cols))
                    gy0 = int(grid_spec["ys"][r] / h * rows)
                    gy1 = max(gy0 + 1, int(grid_spec["ys"][r + 1] / h * rows))
                    block = grid[gy0:gy1, gx0:gx1]
                    peak = block.max()
                    if peak > 0:
                        block /= peak
        else:
            grid = grid / grid.max()

    # Resize grid to frame size and colorize (transparent overlay).
    heat = cv2.resize(grid, (w, h), interpolation=cv2.INTER_CUBIC)
    if grid_spec:
        # Keep each camera's activity inside its own cell: the JET colormap has a
        # high value at 0 too, so bleeding would fake heat on other cameras.
        mask_cells = np.zeros((h, w), np.uint8)
        for r in range(grid_spec["rows"]):
            for c in range(grid_spec["cols"]):
                cv2.rectangle(mask_cells,
                              (grid_spec["xs"][c], grid_spec["ys"][r]),
                              (grid_spec["xs"][c + 1] - 1, grid_spec["ys"][r + 1] - 1),
                              255, -1)
        heat = np.where(mask_cells > 0, heat, 0).astype(np.float32)
    heat_uint8 = (heat * 255).astype(np.uint8)
    colored = cv2.applyColorMap(heat_uint8, cv2.COLORMAP_JET)

    base = frame.copy()
    # 0.18 not 0.05: JET maps near-zero to saturated blue, which would read as
    # "activity here" on cameras that had almost none.
    mask = heat > 0.18
    base[mask] = (base[mask] * 0.45 + colored[mask] * 0.55).astype(np.uint8)

    # Legend bar (color scale). Backed by a dark plate so it stays readable on
    # bright footage and does not hide a camera's activity.
    bar_w = max(24, int(w * 0.03))
    bar = np.zeros((int(h * 0.3), bar_w, 3), dtype=np.uint8)
    for i in range(bar.shape[0]):
        v = 255 - int(i / bar.shape[0] * 255)
        bar[i, :] = cv2.applyColorMap(np.full((1, 1), v, np.uint8), cv2.COLORMAP_JET)[0, 0]
    x0 = w - bar_w - 12
    y0 = 12
    plate = base.copy()
    cv2.rectangle(plate, (x0 - 46, y0 - 6), (x0 + bar_w + 6, y0 + bar.shape[0] + 6),
                  (18, 18, 18), -1)
    base = cv2.addWeighted(plate, 0.72, base, 0.28, 0)
    base[y0:y0 + bar.shape[0], x0:x0 + bar_w] = bar
    cv2.putText(base, "low", (x0 - 34, y0 + 14), cv2.FONT_HERSHEY_SIMPLEX,
                0.45, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(base, "high", (x0 - 38, y0 + bar.shape[0] - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

    # Outline each camera so the heatmap is not read across scenes. No text
    # labels: DVR footage normally burns its own in, and duplicates look broken.
    if grid_spec:
        for r in range(grid_spec["rows"]):
            for c in range(grid_spec["cols"]):
                cv2.rectangle(base,
                              (grid_spec["xs"][c], grid_spec["ys"][r]),
                              (grid_spec["xs"][c + 1] - 1, grid_spec["ys"][r + 1] - 1),
                              (70, 70, 70), 1)

    if scale != 1.0:
        base = cv2.resize(base, (int(w * scale), int(h * scale)))
    cv2.imwrite(str(out_path), base)
    return out_path


def save_reference(frame: np.ndarray, out_path: Path) -> Path:
    cv2.imwrite(str(out_path), frame)
    return out_path
