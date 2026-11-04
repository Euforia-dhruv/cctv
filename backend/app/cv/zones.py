"""Zones: user-defined polygons (display, restricted, entrance, exit, queue)."""
from __future__ import annotations

from typing import List, Tuple

Point = Tuple[float, float]


def in_polygon(pt: Point, poly: List[Point]) -> bool:
    """Ray casting point-in-polygon."""
    x, y = pt
    inside = False
    n = len(poly)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


class Zone:
    def __init__(self, zid: int, name: str, kind: str, points: List[Point]):
        self.id = zid
        self.name = name
        self.kind = kind          # display|restricted|entrance|exit|queue
        self.points = [(float(px), float(py)) for px, py in points]

    def contains(self, pt: Point) -> bool:
        return in_polygon(pt, self.points)


def zones_from_json(data) -> List[Zone]:
    zones = []
    for i, z in enumerate(data or []):
        zones.append(Zone(int(z.get("id", i + 1)), z.get("name", f"Zone {i+1}"),
                          z.get("kind", "display"), z.get("points", [])))
    return zones
