"""Self-check: blob heuristics stay quiet in a crowd.

Background subtraction reported 274 false 'unattended object'/'debris' events
out of 280 on a crowded mall clip. This pins the guard that fixed it.

Run: python tests/test_alert_crowd.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.cv.alerts import AlertsEngine, CROWD_PEOPLE  # noqa: E402

W, H = 640, 360


def fake_frame(seed=0):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, (H, W, 3), dtype=np.uint8)


def people(n):
    """n synthetic detections: (x1, y1, x2, y2, conf)."""
    return [(10 + i * 20, 100, 30 + i * 20, 180, 0.9) for i in range(n)]


def run(dets_per_frame, frames=40):
    eng = AlertsEngine(W, H, 30.0)
    for i in range(frames):
        eng.on_frame(fake_frame(i), dets_per_frame, i / 30.0)
    return eng


def main():
    ok = True

    busy = run(people(CROWD_PEOPLE + 10))
    quiet = run(people(1))

    def check(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"{'PASS' if good else 'FAIL'}  {name}: got {got} want {want}")

    check("crowded scene -> blob events suppressed", len(busy.events), 0)
    check("crowded scene -> counted as crowded", busy.crowd_frames, 40)
    check("quiet scene -> blobs still processed", quiet.crowd_frames, 0)
    print(f"\nCROWD_PEOPLE = {CROWD_PEOPLE}")

    print("\nALL CROWD-GUARD CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
