"""
Phase 6F-2 — rule-based land suitability.

This is deliberately NOT machine learning and NOT prediction. It is a
transparent weighted checklist over *verified* features. If a required
feature is missing (a real data gap), the assessment refuses to score
rather than guessing.

Threshold tables are lists of (bound, points), evaluated in ascending
order of `bound`. `direction` says whether a value qualifies for a row by
being <= bound ("asc", smaller is better) or >= bound ("desc", larger is
better). A trailing (None, points) row is the "else" bucket.
"""
from __future__ import annotations

from datetime import date

from services import feature_engineering as fe

# (feature_block, feature_key, max_points, rule)
# rule is either ("num", direction, [(bound, pts), ...]) or ("map", {label: pts})
AGRICULTURAL_CRITERIA = [
    ("terrain", "slope_deg", 25, ("num", "asc",
        [(2, 25), (5, 20), (10, 10), (15, 5), (None, 0)])),
    ("lulc", "current_class", 25, ("map",
        {"Crops": 25, "Rangeland": 15, "Trees": 10})),
    ("climate", "annual_precipitation_mm", 25, ("num", "desc",
        [(400, 5), (600, 15), (800, 20), (None, 25)])),
    ("infrastructure", "distance_to_road_m", 25, ("num", "asc",
        [(500, 25), (1000, 20), (2000, 15), (None, 5)])),
]

DEVELOPMENT_CRITERIA = [
    ("terrain", "slope_deg", 25, ("num", "asc",
        [(5, 25), (10, 20), (15, 10), (None, 0)])),
    ("lulc", "current_class", 25, ("map",
        {"Built Area": 25, "Bare Ground": 20, "Rangeland": 20, "Crops": 10})),
    ("infrastructure", "distance_to_road_m", 25, ("num", "asc",
        [(200, 25), (500, 20), (1000, 15), (2000, 10), (None, 0)])),
    ("infrastructure", "distance_to_transit_m", 25, ("num", "asc",
        [(1000, 25), (2000, 15), (5000, 10), (None, 0)])),
]


def _score_num(value, direction, table) -> int:
    """First qualifying row wins; ascending scan by bound."""
    for bound, pts in table:
        if bound is None:
            return pts
        if direction == "asc" and value <= bound:
            return pts
        if direction == "desc" and value <= bound:
            # 'desc': a value <= this bound has NOT yet reached the next tier;
            # its score is the previous (lower) tier — handled by scanning the
            # table and returning as soon as value <= bound.
            return pts
    return table[-1][1]


def _score(value, rule) -> int:
    kind = rule[0]
    if kind == "map":
        return rule[1].get(value, 0)
    _, direction, table = rule
    return _score_num(value, direction, table)


def _flatten(fv: dict) -> dict:
    flat = {}
    for name, block in fv.get("features", {}).items():
        if block.get("available"):
            for k, v in block.get("features", {}).items():
                flat[(name, k)] = v
    return flat


def _assess(fv: dict, criteria, kind: str) -> dict:
    flat = _flatten(fv)
    got = total = 0
    breakdown, missing = [], []

    for block, key, max_pts, rule in criteria:
        total += max_pts
        val = flat.get((block, key))
        if val is None:
            missing.append(f"{block}.{key}")
            breakdown.append({"criterion": f"{block}.{key}", "max": max_pts,
                              "value": None, "points": None, "status": "missing"})
            continue
        pts = _score(val, rule)
        got += pts
        breakdown.append({"criterion": f"{block}.{key}", "max": max_pts,
                          "value": val, "points": pts, "status": "scored"})

    if missing:
        return {
            "type": kind,
            "scorable": False,
            "reason": "Required verified features are missing — suitability is "
                      "not scored on incomplete evidence.",
            "missing_features": missing,
            "breakdown": breakdown,
            "confidence": "none",
            "method": "rule-based weighted checklist (no ML, no prediction)",
        }

    score = round(100 * got / total) if total else 0
    if kind == "agricultural":
        category = ("Suitable" if score >= 70 else
                    "Moderately suitable" if score >= 50 else "Unsuitable")
    else:
        category = ("High potential" if score >= 70 else
                    "Moderate potential" if score >= 50 else "Low potential")
    limiting = [b["criterion"] for b in breakdown
                if b["points"] is not None and b["points"] < b["max"] * 0.5]

    return {
        "type": kind,
        "scorable": True,
        "score": score,
        "category": category,
        "limiting_factors": limiting,
        "breakdown": breakdown,
        "confidence": "medium",
        "method": "rule-based weighted checklist (no ML, no prediction)",
    }


def assess(lat: float, lon: float, kind: str = "agricultural") -> dict:
    kind = kind.lower()
    if kind not in ("agricultural", "development"):
        return {"error": "type must be 'agricultural' or 'development'"}

    fv = fe.build_feature_vector(lat, lon)
    if "error" in fv:
        return fv

    criteria = AGRICULTURAL_CRITERIA if kind == "agricultural" else DEVELOPMENT_CRITERIA
    result = _assess(fv, criteria, kind)
    result["location"] = fv["location"]
    result["feature_provenance"] = {
        name: b.get("provenance") for name, b in fv["features"].items()
        if b.get("available")
    }
    result["generated"] = date.today().isoformat()
    result["disclaimer"] = ("Descriptive rule-based screening only. Not a "
                            "prediction, valuation, or statutory land-use "
                            "determination.")
    return result
