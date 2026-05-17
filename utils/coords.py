"""
Coordinate conversion helpers.

Different APIs in this project use different (lat, lon) conventions
(see CLAUDE.md → Critical Gotchas):

- Nominatim returns (lat, lon) as strings.
- OSRM URL paths expect 'lon,lat;lon,lat'.
- OSRM 'geometry.coordinates' returns [[lon, lat], ...].
- Folium / Leaflet expect [lat, lon].

Centralising the swaps here prevents the #1 source of bugs in the project:
silently passing coordinates in the wrong order.
"""
from __future__ import annotations


def to_osrm_coords(lat: float, lon: float) -> str:
    """Format one (lat, lon) point as the 'lon,lat' string OSRM URLs expect."""
    return f"{lon},{lat}"


def from_osrm_geometry(geojson_coords: list) -> list[list[float]]:
    """Flip OSRM's [[lon, lat], ...] into Folium-style [[lat, lon], ...]."""
    return [[lat, lon] for lon, lat in geojson_coords]
