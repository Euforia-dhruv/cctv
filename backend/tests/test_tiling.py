"""Self-check for small-object tiling (sliding_tiles / merge_boxes).

Run: python tests/test_tiling.py
Synthetic check: known boxes in a known place must survive tiling and merging.
No model download, no GPU needed.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.cv import mosaic  # noqa: E402


def check(name, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got {got} want {want}")
    return ok


def main():
    ok = True
    frame = np.zeros((360, 640, 3), np.uint8)

    # 3x3 tiles must cover the whole frame, overlapping, with no empty crop.
    crops = mosaic.sliding_tiles(frame, 3, 0.15)
    ok &= check("3x3 crop count", len(crops), 9)
    ok &= check("all crops non-empty", all(c.size > 0 for c, _ in crops), True)

    covered = np.zeros((360, 640), bool)
    for _, (x0, y0, w, h) in crops:
        covered[y0:y0 + h, x0:x0 + w] = True
    ok &= check("every pixel covered", bool(covered.all()), True)

    # A box round-tripping through tile space must land back where it started.
    # map_to_frame takes tile-space (upscaled) coords, so scale the frame box up.
    cell = (80, 40, 0, 0)
    up = mosaic.TILE_UPSCALE
    want = (100.0, 50.0, 140.0, 110.0)
    tile_space = ((want[0] - cell[0]) * up, (want[1] - cell[1]) * up,
                  (want[2] - cell[0]) * up, (want[3] - cell[1]) * up, 0.9)
    back = mosaic.map_to_frame([tile_space], cell)[0]
    ok &= check("tile coord round-trip",
                tuple(round(v, 1) for v in back[:4]), want)

    # Duplicates from overlapping tiles collapse to one; distinct people stay.
    dup_a = (100.0, 50.0, 140.0, 110.0, 0.80)
    dup_b = (101.0, 51.0, 141.0, 111.0, 0.90)   # same person, higher conf
    other = (300.0, 50.0, 340.0, 110.0, 0.70)   # different person
    merged = mosaic.merge_boxes([dup_a, dup_b, other])
    ok &= check("overlap merged", len(merged), 2)
    ok &= check("highest conf kept", merged[0][4], 0.90)

    # Boxes barely touching must NOT be merged.
    a = (0.0, 0.0, 50.0, 50.0, 0.9)
    b = (45.0, 0.0, 95.0, 50.0, 0.8)
    ok &= check("near boxes kept apart", len(mosaic.merge_boxes([a, b])), 2)

    ok &= check("single box untouched", len(mosaic.merge_boxes([a])), 1)

    print("\nALL TILING CHECKS PASSED" if ok else "\nSOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
