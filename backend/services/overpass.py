"""
Shared Overpass client: tries multiple public mirrors with one retry each,
so a transient 429/504 on one endpoint doesn't turn OSM data into a gap.
"""
from __future__ import annotations

import time

import httpx

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


class OverpassError(RuntimeError):
    pass


def query(ql: str, timeout: float = 60.0) -> list[dict]:
    """Return Overpass 'elements' or raise OverpassError with a readable reason."""
    last = "no endpoints tried"
    for url in ENDPOINTS:
        for attempt in (1, 2):
            try:
                with httpx.Client(timeout=timeout) as c:
                    r = c.post(url, data={"data": ql})
                if r.status_code == 200:
                    return r.json().get("elements", [])
                last = f"{url} -> HTTP {r.status_code}"
                if r.status_code in (429, 504, 502, 503):
                    time.sleep(1.5 * attempt)
                    continue
                break  # non-retryable status, move to next endpoint
            except Exception as exc:  # noqa: BLE001
                last = f"{url} -> {exc.__class__.__name__}"
                time.sleep(1.0 * attempt)
    raise OverpassError(last)
