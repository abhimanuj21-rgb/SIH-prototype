"""
Replace the placeholder Madurai boundary with the real OSM administrative
relation.

Usage (from the backend/ directory):
    python scripts/fetch_boundary.py

Writes GeoJSON to backend/data/madurai_boundary_clean.geojson and prints the
new bbox. After a successful run the script also flips madurai_boundary to
AVAILABLE / analytical_eligible in services/data_registry.py is NOT automatic —
do that edit by hand once you've eyeballed the geometry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services import overpass  # noqa: E402

OUT = BACKEND / "data" / "madurai_boundary_clean.geojson"

# Try progressively looser queries; first hit wins.
QUERIES = [
    # Madurai Corporation / city (admin_level 8 in TN)
    '[out:json][timeout:90];'
    'relation["boundary"="administrative"]["admin_level"="8"]["name"~"Madurai",i];'
    'out geom;',
    # Madurai district (admin_level 5/6)
    '[out:json][timeout:90];'
    'relation["boundary"="administrative"]["admin_level"~"5|6"]["name"~"Madurai",i];'
    'out geom;',
    # Anything named Madurai with a boundary
    '[out:json][timeout:90];'
    'relation["boundary"="administrative"]["name"~"Madurai",i];'
    'out geom;',
]


def _rings_from_relation(rel: dict) -> list[list[list[float]]]:
    rings: list[list[list[float]]] = []
    for m in rel.get("members", []):
        if m.get("role") in ("outer", "") and m.get("geometry"):
            pts = [[p["lon"], p["lat"]] for p in m["geometry"]
                   if p.get("lon") is not None]
            if len(pts) >= 2:
                rings.append(pts)
    return rings


def main() -> int:
    rel = None
    for q in QUERIES:
        try:
            els = overpass.query(q, timeout=95.0)
        except overpass.OverpassError as exc:
            print(f"query failed ({exc}); trying next", file=sys.stderr)
            continue
        rels = [e for e in els if e.get("type") == "relation" and e.get("members")]
        if rels:
            rel = max(rels, key=lambda e: len(e.get("members", [])))
            break

    if rel is None:
        print("No Madurai administrative relation found via any query.",
              file=sys.stderr)
        return 2

    rings = _rings_from_relation(rel)
    if not rings:
        print("Relation had no usable outer geometry.", file=sys.stderr)
        return 3

    geom = ({"type": "Polygon", "coordinates": [rings[0]]}
            if len(rings) == 1 else
            {"type": "MultiPolygon", "coordinates": [[r] for r in rings]})

    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    fc = {
        "type": "FeatureCollection",
        "properties": {"is_demo": False, "source": "OpenStreetMap (Overpass)",
                       "osm_relation_id": rel.get("id"),
                       "name": rel.get("tags", {}).get("name", "Madurai"),
                       "admin_level": rel.get("tags", {}).get("admin_level")},
        "features": [{"type": "Feature",
                      "properties": {"name": rel.get("tags", {}).get("name", "Madurai"),
                                     "is_demo": False,
                                     "admin_level": rel.get("tags", {}).get("admin_level"),
                                     "wikidata": rel.get("tags", {}).get("wikidata")},
                      "geometry": geom}],
    }
    OUT.write_text(json.dumps(fc), encoding="utf-8")
    print(f"Wrote {OUT} (relation {rel.get('id')}, "
          f"admin_level {rel.get('tags', {}).get('admin_level')}, "
          f"{sum(len(r) for r in rings)} vertices)")
    print(f"bbox: lon {min(xs):.4f}..{max(xs):.4f}  lat {min(ys):.4f}..{max(ys):.4f}")
    print("Next: set madurai_boundary -> AVAILABLE / analytical_eligible=True "
          "in services/data_registry.py, and widen AOI in evidence_engine.py "
          "if the bbox exceeds it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
