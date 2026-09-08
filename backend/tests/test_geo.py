"""Geometry helpers used by the site-context service."""
from services import geo


def test_haversine_known_distance():
    # ~111 km per degree of latitude near the equator.
    d = geo.haversine_m(9.90, 78.10, 10.00, 78.10)
    assert 10_900 < d < 11_300  # ~11.1 km for 0.1 deg


def test_point_in_ring_square():
    ring = [[0, 0], [0, 2], [2, 2], [2, 0], [0, 0]]
    assert geo.point_in_ring(1, 1, ring) is True
    assert geo.point_in_ring(3, 1, ring) is False
    assert geo.point_in_ring(-1, 1, ring) is False


def test_point_in_geom_polygon():
    poly = {"type": "Polygon", "coordinates": [[[0, 0], [0, 2], [2, 2], [2, 0], [0, 0]]]}
    assert geo.point_in_geom(1, 1, poly) is True
    assert geo.point_in_geom(5, 5, poly) is False


def test_min_distance_to_linestring():
    # min_distance_m measures to the nearest vertex, so query near an endpoint.
    line = {"type": "LineString", "coordinates": [[78.10, 9.90], [78.20, 9.90]]}
    d = geo.min_distance_m(9.905, 78.101, line)
    assert d is not None and 400 < d < 700  # ~0.005 deg lat off vertex (78.10, 9.90)
