from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from config import POI_CATEGORIES

logger = logging.getLogger(__name__)


@dataclass
class Place:
    """A point of interest that serves as a game node on the map."""

    poi_id: str      # "{osm_type}_{osm_id}" — stable identifier across runs
    name: str
    lat: float
    lon: float
    category: str    # key from POI_CATEGORIES (e.g. "cafe", "park")
    value: int       # score value, copied from config for convenience
    osm_type: str = ""
    osm_id: str = ""
    raw_tags: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict (for disk caching and API responses)."""
        return {
            "poi_id": self.poi_id,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "category": self.category,
            "value": self.value,
            "osm_type": self.osm_type,
            "osm_id": self.osm_id,
            "raw_tags": self.raw_tags,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Place:
        """Deserialize from a dict loaded from JSON cache."""
        return cls(
            poi_id=d["poi_id"],
            name=d["name"],
            lat=float(d["lat"]),
            lon=float(d["lon"]),
            category=d["category"],
            value=int(d["value"]),
            osm_type=d.get("osm_type", ""),
            osm_id=d.get("osm_id", ""),
            raw_tags=d.get("raw_tags", {}),
        )

    @classmethod
    def from_nominatim(cls, raw: dict, category: str) -> Optional[Place]:
        """
        Build from a Nominatim search element.
        Returns None when there is no usable name or the coordinates cannot be parsed.
        Uses .get() everywhere — Nominatim fields are not guaranteed.
        """
        # Prefer the OSM 'name' tag; fall back to the first segment of display_name.
        name_details = raw.get("namedetails") or {}
        name = (
            name_details.get("name")
            or raw.get("display_name", "").split(",")[0].strip()
        )
        if not name:
            return None

        # Nominatim returns lat/lon as strings; cast to float.
        try:
            lat = float(raw["lat"])
            lon = float(raw["lon"])
        except (KeyError, ValueError, TypeError):
            logger.debug("Skipping element with bad coords (osm_id=%s)", raw.get("osm_id"))
            return None

        osm_type = str(raw.get("osm_type", ""))
        osm_id = str(raw.get("osm_id", ""))

        return cls(
            poi_id=f"{osm_type}_{osm_id}",
            name=name,
            lat=lat,
            lon=lon,
            category=category,
            value=POI_CATEGORIES.get(category, {}).get("value", 1),
            osm_type=osm_type,
            osm_id=osm_id,
            raw_tags=raw.get("extratags") or {},
        )
