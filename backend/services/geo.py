"""Small geometry helpers shared by the evidence + site-context services."""
from __future__ import annotations

import math


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def iter_lonlat(geom: dict):
    """Yield (lon, lat) for Point / LineString / (Multi)Polygon / MultiLineString."""
    gtype, coords = geom.get("type"), geom.get("coordinates")
    if not coords:
        return
    if gtype == "Point":
        yield coords[0], coords[1]
    elif gtype in ("LineString", "MultiPoint"):
        yield from coords
    elif gtype in ("Polygon", "MultiLineString"):
        for part in coords:
            yield from part
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                yield from ring


def min_distance_m(lat: float, lon: float, geom: dict) -> float | None:
    """Nearest distance from (lat, lon) to any vertex of geom (metres)."""
    best = None
    for glon, glat in iter_lonlat(geom):
        d = haversine_m(lat, lon, glat, glon)
        best = d if best is None else min(best, d)
    return best


def point_in_ring(lon: float, lat: float, ring: list) -> bool:
    """Ray-casting test. ring is a list of [lon, lat] pairs."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


def point_in_geom(lon: float, lat: float, geom: dict) -> bool:
    gtype, coords = geom.get("type"), geom.get("coordinates")
    if gtype == "Polygon" and coords:
        return point_in_ring(lon, lat, coords[0])
    if gtype == "MultiPolygon":
        return any(rings and point_in_ring(lon, lat, rings[0]) for rings in coords)
    return False
