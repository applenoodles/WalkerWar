import hashlib
import json
import logging
import math
import time
from pathlib import Path
from typing import Optional

import requests
import urllib3

# School / corporate networks often have self-signed certs; suppress the warning.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config import (
    ACCEPT_LANGUAGE,
    CACHE_DIR,
    CACHE_ENABLED,
    NOMINATIM_BASE,
    NOMINATIM_RATE_LIMIT_SEC,
    POI_CATEGORIES,
    POI_FLOOR,
    POI_RADIUS_M,
    POI_TARGET_COUNT,
    USER_AGENT,
)
from models.place import Place
from utils.decorators import handle_api_errors, log_execution

logger = logging.getLogger(__name__)


class NotEnoughPOIsError(Exception):
    """Raised when the search area yields fewer than POI_FLOOR places."""


class POIService:
    """Generates game POIs near an origin using Nominatim."""

    def __init__(self, cache_dir: Path = CACHE_DIR / "poi"):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        # Single session reused for all Nominatim calls.
        # verify=False works around SSL cert issues on school/corporate networks.
        self._session = requests.Session()
        self._session.verify = False
        self._session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept-Language": ACCEPT_LANGUAGE,
        })

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @handle_api_errors(default_factory=lambda: None)
    @log_execution
    def geocode(self, query: str) -> Optional[dict]:
        """Return {'lat': float, 'lon': float, 'display_name': str} or None."""
        cache_key = hashlib.sha256(query.encode()).hexdigest()[:16]
        cache_path = self._cache_dir / f"geocode_{cache_key}.json"

        if CACHE_ENABLED and cache_path.exists():
            logger.debug("cache hit: geocode %r", query)
            return json.loads(cache_path.read_text(encoding="utf-8"))

        logger.debug("cache miss: geocode %r", query)
        url = f"{NOMINATIM_BASE}/search"
        params = {
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 1,
            "namedetails": 1,
            "countrycodes": "tw",   # restrict to Taiwan for demo correctness
        }
        resp = self._session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if not data:
            logger.warning("Nominatim returned no results for %r", query)
            return None

        raw = data[0]
        result = {
            "lat": float(raw["lat"]),
            "lon": float(raw["lon"]),
            "display_name": raw.get("display_name", query),
        }
        # Only cache a successful, non-empty response.
        cache_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result

    @log_execution
    def generate_pois(
        self,
        origin_lat: float,
        origin_lon: float,
        radius_m: int = POI_RADIUS_M,
        target_count: int = POI_TARGET_COUNT,
    ) -> list[Place]:
        """
        Search Nominatim per category within a bounding box, deduplicate by
        (osm_type, osm_id), and return a list of Places.

        Strategy (IMPLEMENTATION_NOTES §5):
        - For each named category, try keywords in order until ≥ 3 POIs found.
        - Cap each category at 6 POIs.
        - If total < POI_FLOOR after all named categories, run generic fallback.
        - If still < POI_FLOOR, raise NotEnoughPOIsError.

        Caches the successful result to disk.
        """
        lat4 = round(origin_lat, 4)
        lon4 = round(origin_lon, 4)
        cache_path = self._cache_dir / f"pois_{lat4}_{lon4}_{radius_m}.json"

        if CACHE_ENABLED and cache_path.exists():
            logger.debug("cache hit: pois (%s, %s) r=%s", lat4, lon4, radius_m)
            raw_list = json.loads(cache_path.read_text(encoding="utf-8"))
            return [Place.from_dict(d) for d in raw_list]

        logger.info("Generating POIs for (%s, %s) radius=%sm", lat4, lon4, radius_m)
        viewbox = self._viewbox(origin_lat, origin_lon, radius_m)
        seen_ids: set[str] = set()  # dedup key: "{osm_type}_{osm_id}"
        by_category: dict[str, list[Place]] = {cat: [] for cat in POI_CATEGORIES}

        # Phase 1: named categories (skip "generic" — that's the fallback)
        for cat, cfg in POI_CATEGORIES.items():
            if cat == "generic":
                continue
            for kw in cfg["keywords"]:
                if len(by_category[cat]) >= 3:
                    break  # enough; skip remaining keywords for this category
                hits = self._search(kw, viewbox)
                for raw in hits:
                    key = f"{str(raw.get('osm_type',''))}_{str(raw.get('osm_id',''))}"
                    if key in seen_ids:
                        continue
                    place = Place.from_nominatim(raw, cat)
                    if place is None:
                        continue
                    seen_ids.add(key)
                    by_category[cat].append(place)
                    if len(by_category[cat]) >= 6:
                        break  # category cap reached
                time.sleep(NOMINATIM_RATE_LIMIT_SEC)

        # Flatten into a single list (cap at target_count)
        all_pois: list[Place] = []
        for cat in POI_CATEGORIES:
            if cat != "generic":
                all_pois.extend(by_category[cat])
        all_pois = all_pois[:target_count]

        # Phase 2: generic keyword fallback if still below floor
        if len(all_pois) < POI_FLOOR:
            logger.info(
                "Only %d POIs after named categories (floor=%d); running generic fallback",
                len(all_pois), POI_FLOOR,
            )
            for kw in POI_CATEGORIES["generic"]["keywords"]:
                hits = self._search(kw, viewbox)
                for raw in hits:
                    key = f"{str(raw.get('osm_type',''))}_{str(raw.get('osm_id',''))}"
                    if key in seen_ids:
                        continue
                    place = Place.from_nominatim(raw, "generic")
                    if place is None:
                        continue
                    seen_ids.add(key)
                    all_pois.append(place)
                    if len(all_pois) >= POI_FLOOR:
                        break
                time.sleep(NOMINATIM_RATE_LIMIT_SEC)
                if len(all_pois) >= POI_FLOOR:
                    break

        # Log per-category breakdown so the student can verify coverage.
        cat_counts: dict[str, int] = {}
        for p in all_pois:
            cat_counts[p.category] = cat_counts.get(p.category, 0) + 1
        logger.info("POI breakdown: %s  total=%d", cat_counts, len(all_pois))

        if len(all_pois) < POI_FLOOR:
            logger.error("Cannot reach POI floor: found %d, need %d", len(all_pois), POI_FLOOR)
            raise NotEnoughPOIsError(
                f"只找到 {len(all_pois)} 個地點，需要 {POI_FLOOR} 個；試試別的起點"
            )

        # Only cache a fully successful result.
        cache_path.write_text(
            json.dumps([p.to_dict() for p in all_pois], ensure_ascii=False),
            encoding="utf-8",
        )
        return all_pois

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _viewbox(self, lat: float, lon: float, radius_m: int) -> str:
        """
        Build a Nominatim viewbox string: left,top,right,bottom
        = lon_min, lat_max, lon_max, lat_min.
        Approximates a square bounding box using degree offsets.
        """
        delta_lat = radius_m / 111_111
        delta_lon = radius_m / (111_111 * math.cos(math.radians(lat)))
        return (
            f"{lon - delta_lon},{lat + delta_lat},"
            f"{lon + delta_lon},{lat - delta_lat}"
        )

    @handle_api_errors(default_factory=list)
    def _search(self, keyword: str, viewbox: str) -> list[dict]:
        """One Nominatim keyword search within the viewbox; returns raw JSON list."""
        url = f"{NOMINATIM_BASE}/search"
        params = {
            "q": keyword,
            "format": "jsonv2",
            "limit": 8,
            "addressdetails": 1,
            "namedetails": 1,
            "viewbox": viewbox,
            "bounded": 1,
        }
        resp = self._session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
