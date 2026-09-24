"""
Synthetic cadastral parcel fabric — for UI demonstration only.

Real parcel geometry is government data requiring formal access (see
cadastral_geometry / mp_cadastral_geometry in data_registry.py). This module
never claims to be that data: every feature it emits is tagged is_demo=True
and the dataset is DEMO_ONLY / analytically forbidden (enforced in
data_registry.py and evidence_engine.py, not just here).

Rather than a uniform N×N grid, parcels are cut with a randomized recursive
guillotine split — the same family of algorithm used for treemaps — which
produces the irregular block-of-varying-sized-rectangles look of a real
cadastral fabric while staying honestly synthetic and reproducible (same
seed -> same layout).
"""
from __future__ import annotations

import math
import random

Rect = tuple[float, float, float, float]  # (lon_min, lat_min, lon_max, lat_max)

_MIN_SPLIT = 4   # a parcel this large or smaller no longer subdivides


def _split(rect: Rect, n: int, rng: random.Random) -> list[Rect]:
    if n <= 1:
        return [rect]
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    n1 = n // 2
    n2 = n - n1
    frac = min(0.72, max(0.28, (n1 / n) + rng.uniform(-0.1, 0.1)))
    if w >= h:
        cut = x0 + w * frac
        left, right = (x0, y0, cut, y1), (cut, y0, x1, y1)
    else:
        cut = y0 + h * frac
        left, right = (x0, y0, x1, cut), (x0, cut, x1, y1)
    return _split(left, n1, rng) + _split(right, n2, rng)


def _area_m2(rect: Rect) -> float:
    """Equirectangular approximation — accurate to well under 1% at this
    scale (a few hundred metres across), which is all a DEMO figure needs."""
    x0, y0, x1, y1 = rect
    lat_mid = (y0 + y1) / 2
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat_mid))
    return abs((x1 - x0) * m_per_deg_lon) * abs((y1 - y0) * m_per_deg_lat)


def generate_parcels(city_core: dict, count: int = 60, seed: int = 1) -> list[dict]:
    count = max(_MIN_SPLIT, min(int(count), 400))
    rng = random.Random(seed)
    rect: Rect = (city_core["lon_min"], city_core["lat_min"],
                  city_core["lon_max"], city_core["lat_max"])
    rects = _split(rect, count, rng)

    feats = []
    for i, r in enumerate(rects):
        x0, y0, x1, y1 = r
        area_m2 = _area_m2(r)
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[
                [x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]},
            "properties": {
                "demo_parcel_id": f"DEMO-{i:04d}",
                "is_demo": True,
                "area_sqm": round(area_m2, 1),
                "area_sqft": round(area_m2 * 10.7639, 1),
                "area_cents": round(area_m2 / 40.4686, 2),  # cent: common TN/Kerala land unit
            },
        })
    return feats
