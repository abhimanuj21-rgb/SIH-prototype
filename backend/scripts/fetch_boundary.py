"""
Replace the placeholder Madurai boundary with the real OSM administrative
relation.

Usage:
    python scripts/fetch_boundary.py

Pulls the OSM boundary relation for Madurai (Corporation / district) via the
Overpass API, writes GeoJSON to backend/data/madurai_boundary_clean.geojson,
and prints the new bbox so you can update AOI in evidence_engine.py if needed.

After a successful run, set madurai_boundary status to AVAILABLE and
analytical_eligible=True in services/data_registry.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parent.parent / "data" / "madurai_boundary_clean.geojson"

# Madurai Municipal Corporation relation; fall back to district search by name.
QUERY = """
[out:json][timeout:60];
(
  relation["boundary"="administrative"]["name"="Madurai"]["admin_level"~"^(5|6|8)$"];
);
out geom;
"""


def main() -> int:
    try:
        with httpx.Client(timeout=90) as c:
            r = c.post("https://overpass-api.de/api/interpreter", data={"data": QUERY})
            r.raise_for_status()
            els = r.json().get("elements", [])
    except Exception as exc:  # noqa: BLE001
        print(f"Overpass request failed: {exc}", file=sys.stderr)
        return 1

    rels = [e for e in els if e.get("type") == "relation" and e.get("members")]
    if not rels:
        print("No Madurai administrative relation returned. Inspect the query "
              "at https://overpass-turbo.eu/ and adjust admin_level.",
              file=sys.stderr)
        return 2

    rel = sorted(rels, key=lambda e: len(e.get("members", [])), reverse=True)[0]
    rings: list[list[list[float]]] = []
    for m in rel["members"]:
        if m.get("role") == "outer" and m.get("geometry"):
            rings.append([[p["lon"], p["lat"]] for p in m["geometry"]])
    if not rings:
        print("Relation had no outer geometry.", file=sys.stderr)
        return 3

    geom = ({"type": "Polygon", "coordinates": [rings[0]]}
            if len(rings) == 1 else
            {"type": "MultiPolygon", "coordinates": [[r] for r in rings]})

    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    fc = {
        "type": "FeatureCollection",
        "properties": {"is_demo": False, "source": "OpenStreetMap (Overpass)",
                       "osm_relation_id": rel.get("id")},
        "features": [{"type": "Feature",
                      "properties": {"name": "Madurai", "is_demo": False,
                                     "tags": rel.get("tags", {})},
                      "geometry": geom}],
    }
    OUT.write_text(json.dumps(fc), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"bbox: lon {min(xs):.4f}..{max(xs):.4f}  lat {min(ys):.4f}..{max(ys):.4f}")
    print("Now set madurai_boundary -> AVAILABLE / analytical_eligible=True "
          "in services/data_registry.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
