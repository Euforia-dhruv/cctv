"""Analytics computed from tracking data. All outputs are estimates and are
labeled as such downstream; nothing here pretends to be an exact count."""
from __future__ import annotations

import statistics
from typing import List

from .tracker import Track
from .zones import Zone
from ..utils import dumps


def foot_points(trk: Track):
    return [(t, cx, cy) for t, cx, cy in trk.path]


def compute_analytics(tracks: List[Track], occupancy: List[tuple],
                      zones: List[Zone], fps: float, width: int, height: int) -> dict:
    total_detections = sum(trk.hits for trk in tracks)
    starts = [trk for trk in tracks if trk.hits >= 2]
    visits = [t for t in starts if t.dwell_s >= 2.0 or _displacement(t) > 40.0]

    dwells = [t.dwell_s for t in visits]
    avg_dwell = statistics.mean(dwells) if dwells else 0.0
    p50 = statistics.median(dwells) if dwells else 0.0

    occ_vals = [c for _, c in occupancy]
    max_occ = max(occ_vals) if occ_vals else 0
    avg_occ = statistics.mean(occ_vals) if occ_vals else 0.0

    # Traffic by minute + busy periods.
    traffic, busy = _traffic_and_busy(tracks, fps)

    # Entrance/exit and zone exposure.
    entries = exits = None
    zone_exposure = {}
    if zones:
        ent_zones = [z for z in zones if z.kind in ("entrance", "exit")]
        entry_zones = [z for z in zones if z.kind == "entrance"]
        exit_zones = [z for z in zones if z.kind == "exit"]
        if entry_zones or exit_zones:
            entries = sum(1 for t in visits if any(z.contains(t.foot()) for z in entry_zones))
            exits = sum(1 for t in visits if any(z.contains(t.foot()) for z in exit_zones))
        elif ent_zones:  # single line zone counts both by direction heuristic
            entries = len(visits)
        for z in zones:
            if z.kind == "display":
                in_zone = [t for t in visits if any(z.contains(p) for p in
                          [(tx, cy) for _, cx, cy in [t.foot()]])]
                # time inside zone
                total_s = 0.0
                for t in visits:
                    inside_s = 0.0
                    prev = None
                    for ts, cx, cy in t.path:
                        if z.contains((cx, cy)):
                            if prev is not None:
                                inside_s += ts - prev
                            prev = ts
                        else:
                            prev = None
                    total_s += inside_s
                zone_exposure[z.name] = {"kind": z.kind, "visits_est": len(in_zone),
                                         "person_seconds": round(total_s, 1)}

    return {
        "total_detections": total_detections,
        "unique_visits_est": len(visits),
        "entries_est": entries,
        "exits_est": exits,
        "avg_occupancy": round(avg_occ, 2),
        "max_occupancy": max_occ,
        "dwell_avg_s": round(avg_dwell, 1),
        "dwell_p50_s": round(p50, 1),
        "busy_periods_json": dumps(busy),
        "traffic_series_json": dumps(traffic),
        "zone_exposure": zone_exposure,
    }


def _displacement(t: Track) -> float:
    if len(t.path) < 2:
        return 0.0
    x0, y0 = t.path[0][1], t.path[0][2]
    x1, y1 = t.path[-1][1], t.path[-1][2]
    return ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5


def _traffic_and_busy(tracks: List[Track], fps: float):
    starts = [t for t in tracks if t.hits >= 2]
    if not starts:
        return [], []
    t0 = min(t.born_t for t in starts)
    t1 = max(t.last_t for t in starts)
    dur = max(t1 - t0, 60.0 / fps)
    nbins = max(1, int(dur // 60) + 1)
    bins = [0] * nbins
    for t in starts:
        idx = min(int((t.born_t - t0) // 60), nbins - 1)
        bins[idx] += 1
    traffic = [{"minute": i, "label": _mmss(t0 + i * 60), "visits": bins[i]}
               for i in range(nbins)]
    mean = sum(bins) / len(bins) if bins else 0
    busy = []
    run = []
    for i, b in enumerate(bins):
        if b > mean + 1.0:
            run.append(i)
        else:
            if run and len(run) >= 2:
                busy.append({"from_min": run[0], "to_min": run[-1],
                             "minutes": len(run),
                             "label": f"{_mmss(t0 + run[0]*60)} - {_mmss(t0 + (run[-1]+1)*60)}"})
            run = []
    if run and len(run) >= 2:
        busy.append({"from_min": run[0], "to_min": run[-1], "minutes": len(run),
                     "label": f"{_mmss(t0 + run[0]*60)} - {_mmss(t0 + (run[-1]+1)*60)}"})
    return traffic, busy


def _mmss(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    return f"{m:02d}:{s:02d}"
