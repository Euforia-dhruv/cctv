"""Hardware benchmark: YOLO26n on the target laptop (CPU vs GPU).
Run: python tests/benchmark.py"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.cv.detector import Detector    # noqa: E402
import cv2                               # noqa: E402

VIDEO = "D:/New folder (2)/retailvision/data/videos_demo/mall_23249_720.mp4"
N = 40


def bench(device: str):
    det = Detector("yolo26n.pt", conf=0.35, imgsz=640, device=device)
    cap = cv2.VideoCapture(VIDEO)
    frames = []
    for i in range(0, N * 8, 8):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, f = cap.read()
        if ok:
            frames.append(f)
    cap.release()
    # warmup
    for f in frames[:4]:
        det.detect(f)
    t0 = time.perf_counter()
    total = 0
    for f in frames:
        det.detect(f)
        total += 1
    dt = time.perf_counter() - t0
    avg_ms = dt / total * 1000
    print(f"{device}: {total} frames in {dt:.2f}s -> {avg_ms:.1f} ms/frame "
          f"({1000/avg_ms:.1f} FPS inference)")
    return avg_ms


if __name__ == "__main__":
    import torch
    print("torch", torch.__version__, "| cuda", torch.version.cuda)
    gpu = bench("cuda")
    cpu = bench("cpu")
    print(f"\nGPU is {cpu/gpu:.1f}x faster than CPU on this laptop.")
