"""Core logic tests (no torch/GPU needed). Run: python tests/test_core.py"""
from __future__ import annotations

import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.cv.tracker import Tracker, iou           # noqa: E402
from app.cv.zones import Zone, in_polygon          # noqa: E402
from app.cv.analytics import compute_analytics, _traffic_and_busy  # noqa: E402
from app.cv.alerts import _blob_covered            # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}")


def test_iou():
    check("iou full overlap = 1", abs(iou((0, 0, 10, 10), (0, 0, 10, 10)) - 1) < 1e-9)
    check("iou disjoint = 0", iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0)
    a = iou((0, 0, 10, 10), (5, 0, 15, 10))
    check("iou half overlap = 1/3", abs(a - 1 / 3) < 1e-6)


def test_tracker_sequence():
    tr = Tracker(max_lost=5, min_hits=2)
    # single person moving right at ~4px/frame
    dets = [(10 + i * 4, 20, 30 + i * 4, 60, 0.9) for i in range(30)]
    live = []
    for i, d in enumerate(dets):
        live = tr.update([d], float(i))
    fin = tr.finish()
    check("one finalized track", len(fin) == 1)
    check("stable id 1", fin[0].id == 1)
    check("30 hits", fin[0].hits == 30)
    check("dwell 29s", abs(fin[0].dwell_s - 29) < 1e-6)
    check("path length 30", len(fin[0].path) == 30)


def test_tracker_two_people_swap():
    tr = Tracker(max_lost=3)
    # person A and B cross paths; IDs should not swap between two detections
    A = [(10 + i * 3, 20, 30 + i * 3, 60, 0.9) for i in range(20)]
    B = [(80 - i * 3, 40, 100 - i * 3, 80, 0.9) for i in range(20)]
    ids_at_end = None
    for i in range(20):
        live = tr.update([A[i], B[i]], float(i))
        if i == 19:
            ids_at_end = sorted(t.id for t in live if t.hits >= 2)
    fin = tr.finish()
    check("two tracks", len(fin) == 2)
    check("ids 1 and 2", set(t.id for t in fin) == {1, 2})
    # Person A started on the left (x~20) and should keep id 1.
    started_left = [t for t in fin if t.path[0][1] < 50]
    check("left starter kept its id", len(started_left) == 1 and started_left[0].id == 1)


def test_tracker_occlusion():
    tr = Tracker(max_lost=5)
    dets = [(10, 20, 30, 60, 0.9)] * 6
    live = []
    for i in range(6):
        live = tr.update([dets[0]], float(i))
    # disappear for 3 frames, reappear
    for i in range(6, 9):
        live = tr.update([], float(i))
    for i in range(9, 14):
        live = tr.update([(12, 22, 32, 62, 0.9)], float(i))
    fin = tr.finish()
    check("reappeared track keeps id", len(fin) == 1 and fin[0].id == 1)


def test_zones():
    sq = Zone(1, "checkout", "display", [(0, 0), (100, 0), (100, 100), (0, 100)])
    check("inside", sq.contains((50, 50)))
    check("outside", not sq.contains((150, 50)))
    check("edge counts inside", sq.contains((0, 0)))
    tri = Zone(2, "t", "restricted", [(0, 0), (10, 0), (5, 10)])
    check("triangle inside", tri.contains((5, 3)))
    check("triangle outside", not tri.contains((9.5, 2)))
    check("point in polygon helper", in_polygon((0.5, 0.5), [(0, 0), (1, 0), (1, 1), (0, 1)]))


def test_analytics():
    from app.cv.tracker import Track
    t1 = Track(1, (0, 0, 20, 40, 0.9), 0.0)
    t1.hits = 40
    t1.last_t = 39.0
    t1.path = [(float(i), 10.0 + i, 30.0) for i in range(40)]
    t2 = Track(2, (0, 0, 20, 40, 0.9), 5.0)
    t2.hits = 6
    t2.last_t = 10.0
    t2.path = [(5 + i, 60.0, 50.0) for i in range(6)]
    t3 = Track(3, (0, 0, 20, 40, 0.9), 0.0)
    t3.hits = 20
    t3.last_t = 1.9  # short dwell (< 2s) => not a visit
    t3.path = [(float(i), 100.0, 70.0) for i in range(2)]
    occ = [(float(i), 2) for i in range(40)]
    summary = compute_analytics([t1, t2, t3], occ, [], 1.0, 1280, 720)
    check("total detections = 66", summary["total_detections"] == 66)
    check("visits est = 2 (t1,t2)", summary["unique_visits_est"] == 2)
    check("max occupancy = 2", summary["max_occupancy"] == 2)
    check("dwell avg ~ 22", abs(summary["dwell_avg_s"] - 22.0) < 1e-6)


def test_alerts_blob_cover():
    det = (0, 0, 100, 100, 0.9)
    check("centroid inside covered", _blob_covered(50, 50, 20, 20, det))
    check("blob outside not covered", not _blob_covered(200, 200, 20, 20, det))
    check("large overlap covered", _blob_covered(95, 95, 30, 30, det))


if __name__ == "__main__":
    print("RetailVision core tests")
    for fn in (test_iou, test_tracker_sequence, test_tracker_two_people_swap,
               test_tracker_occlusion, test_zones, test_analytics, test_alerts_blob_cover):
        fn()
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
