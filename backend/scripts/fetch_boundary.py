"""
Fetch a real OSM administrative boundary relation for one of the platform's
prototype cities (see services/cities.py) and write it to backend/data/.

Usage (from the backend/ directory):
    python scripts/fetch_boundary.py madurai
    python scripts/fetch_boundary.py bhopal

Writes GeoJSON to backend/data/<city>_boundary_clean.geojson and prints the
new bbox. After a successful run the script also flips <city>_boundary to
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
from services.cities import get_city  # noqa: E402


def _queries(name_pattern: str) -> list[str]:
    # Try progressively looser queries; first hit wins.
    return [
        # City corporation / city (admin_level 8 in most Indian states)
        '[out:json][timeout:90];'
        f'relation["boundary"="administrative"]["admin_level"="8"]["name"~"{name_pattern}",i];'
        'out geom;',
        # District (admin_level 5/6)
        '[out:json][timeout:90];'
        f'relation["boundary"="administrative"]["admin_level"~"5|6"]["name"~"{name_pattern}",i];'
        'out geom;',
        # Anything named with a boundary
        '[out:json][timeout:90];'
        f'relation["boundary"="administrative"]["name"~"{name_pattern}",i];'
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
    if len(sys.argv) < 2:
        print("Usage: python scripts/fetch_boundary.py <city-id>", file=sys.stderr)
        return 1
    city_id = sys.argv[1].lower()
    city = get_city(city_id)
    if city is None:
        print(f"Unknown city '{city_id}'. See services/cities.py.", file=sys.stderr)
        return 1

    out = BACKEND / "data" / city["boundary_file"]
    rel = None
    for q in _queries(city["osm_name_pattern"]):
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
        print(f"No {city['label']} administrative relation found via any query.",
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
                       "name": rel.get("tags", {}).get("name", city["label"]),
                       "admin_level": rel.get("tags", {}).get("admin_level")},
        "features": [{"type": "Feature",
                      "properties": {"name": rel.get("tags", {}).get("name", city["label"]),
                                     "is_demo": False,
                                     "admin_level": rel.get("tags", {}).get("admin_level"),
                                     "wikidata": rel.get("tags", {}).get("wikidata")},
                      "geometry": geom}],
    }
    out.write_text(json.dumps(fc), encoding="utf-8")
    print(f"Wrote {out} (relation {rel.get('id')}, "
          f"admin_level {rel.get('tags', {}).get('admin_level')}, "
          f"{sum(len(r) for r in rings)} vertices)")
    print(f"bbox: lon {min(xs):.4f}..{max(xs):.4f}  lat {min(ys):.4f}..{max(ys):.4f}")
    print(f"Next: set {city['boundary_dataset_id']} -> AVAILABLE / "
          f"analytical_eligible=True in services/data_registry.py, and check the "
          f"AOI for '{city_id}' in services/cities.py covers this bbox.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
