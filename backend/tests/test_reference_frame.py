"""Self-check: a fade-in must not leave a dark reference frame.

The long-form mall clip ramps 0 -> 23 -> 128 brightness in its first ~2 s. An
early "usable" frame at mean 23 is technically not black but still a bad
reference, so the pipeline keeps the brightest of the opening frames.

Run: python tests/test_reference_frame.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.cv.pipeline import _brightness, _usable_frame  # noqa: E402


def pick_reference(frames, settle=20):
    """Mirror of the pipeline's reference selection."""
    ref = None
    for i, f in enumerate(frames):
        if _usable_frame(f) and (ref is None or
                                (i < settle and _brightness(f) > _brightness(ref) * 1.5)):
            ref = f.copy()
    return ref


def main():
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"{'PASS' if good else 'FAIL'}  {name}: got {got} want {want}")

    black = np.zeros((360, 640, 3), np.uint8)
    fade = np.full((360, 640, 3), 23, np.uint8)
    lit = np.full((360, 640, 3), 130, np.uint8)

    check("black frame usable", _usable_frame(black), False)
    check("mid-fade frame usable", _usable_frame(fade), True)
    check("None usable", _usable_frame(None), False)
    check("grey 20 usable", _usable_frame(np.full((4, 4, 3), 20, np.uint8)), True)

    ref = pick_reference([black, fade, lit])
    check("fade-in keeps the lit frame", _brightness(ref), _brightness(lit))

    ref2 = pick_reference([black, lit, fade])
    check("lit-then-dark keeps the lit frame", _brightness(ref2), _brightness(lit))

    ref3 = pick_reference([black, black])
    check("all-black yields no reference", ref3, None)

    print("\nALL REFERENCE-FRAME CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
