"""Self-check for auto tile selection (small people -> tiles).

Run: python tests/test_auto_tile.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.cv.pipeline import _grid_for_person_height, MIN_PERSON_FRAC  # noqa: E402

# Heights measured on this project's footage (640x360 frame, yolo26n).
CASES = [
    # (person height px, frame height, expected grid, what it represents)
    (150, 360, 0, "close-up / normal CCTV framing: no tiling needed"),
    (120, 360, 0, "just above the working fraction"),
    (118, 360, 2, "just below it: 2x already clears the working size"),
    (40, 360, 3, "elevated mall view (the real test clip) -> 3x3"),
    (25, 360, 4, "very wide / far view -> capped at 4x4"),
    (0, 360, 0, "no detections: leave it alone"),
    (40, 0, 0, "bad frame height: guard"),
]


def main():
    ok = True
    for px, fh, want, label in CASES:
        got = _grid_for_person_height(px, fh)
        good = got == want
        ok &= good
        print(f"{'PASS' if good else 'FAIL'}  {px}px/{fh}px -> {got} (want {want})  {label}")
    print(f"\nMIN_PERSON_FRAC = {MIN_PERSON_FRAC}")
    print("\nALL AUTO-TILE CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
