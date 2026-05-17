import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

import requests
import urllib3

# School / corporate networks often have self-signed certs; suppress the warning.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config import (
    CACHE_DIR,
    CACHE_ENABLED,
    OSRM_BASE,
    USER_AGENT,
    WALKING_SPEED_KMH,
)
from models.place import Place
from utils.coords import from_osrm_geometry, to_osrm_coords
from utils.decorators import handle_api_errors, log_execution

logger = logging.getLogger(__name__)


class OSRMService:
    """
    Queries OSRM (foot profile) for walking routes between two points,
    and builds the N×N walking-time matrix used for all gameplay decisions.

    Each route response is cached on disk by a symmetric key — walking A→B
    and B→A take the same time on foot, so they share one cache file.

    Note: the public OSRM demo server actually returns car-speed durations
    even on the /foot/ profile. We therefore ignore OSRM's duration and
    derive walking minutes from its routed distance (which is still
    accurate because both modes follow streets) using WALKING_SPEED_KMH.
    """

    def __init__(self, cache_dir: Path = CACHE_DIR / "osrm"):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        # Single session reused for all OSRM calls.
        # verify=False works around SSL cert issues on school/corporate networks.
        self._session = requests.Session()
        self._session.verify = False
        self._session.headers.update({"User-Agent": USER_AGENT})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @handle_api_errors(default_factory=lambda: None)
    @log_execution
    def get_walking_route(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> Optional[dict]:
        """
        Return {'duration_min', 'distance_m', 'geometry'} for walking start→end.

        Inputs are (lat, lon) tuples. Output geometry is Folium-style
        [[lat, lon], ...]. Returns None on failure.

        duration_min is always recomputed from distance_m at read time, so the
        cache "self-heals" if WALKING_SPEED_KMH is ever tuned.
        """
        cache_path = self._cache_path(start, end)
        if CACHE_ENABLED and cache_path.exists():
            logger.debug("cache hit: osrm route %s→%s", start, end)
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            cached["duration_min"] = self._walking_minutes(cached["distance_m"])
            return cached

        logger.debug("cache miss: osrm route %s→%s", start, end)
        coords = f"{to_osrm_coords(*start)};{to_osrm_coords(*end)}"
        url = f"{OSRM_BASE}/route/v1/foot/{coords}"
        params = {"overview": "full", "geometries": "geojson"}
        resp = self._session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            logger.warning(
                "OSRM returned no route for %s→%s (code=%s)",
                start, end, data.get("code"),
            )
            return None

        route = data["routes"][0]
        result = {
            "duration_min": self._walking_minutes(route["distance"]),
            "distance_m": route["distance"],
            "geometry": from_osrm_geometry(route["geometry"]["coordinates"]),
        }
        # Only cache a successful, non-empty response.
        cache_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result

    def get_walking_time(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> Optional[float]:
        """Convenience wrapper — just the walking time in minutes."""
        route = self.get_walking_route(start, end)
        return route["duration_min"] if route else None

    @log_execution
    def build_matrix(self, places: list[Place]) -> dict[str, dict[str, float]]:
        """
        Build a symmetric N×N walking-time matrix indexed by Place.poi_id.

        Returns a nested dict so that `matrix[a_id][b_id]` gives the walking
        time (in minutes) from place a to place b. The matrix satisfies:
          • matrix[x][x] == 0
          • matrix[a][b] == matrix[b][a]

        Only the C(N, 2) unique pairs (the upper triangle) are queried;
        the lower triangle is mirrored for free. Progress is logged every
        20 pairs so the student knows the build isn't hung.

        Raises RuntimeError if any single pair fails — the matrix must be
        complete because every gameplay decision indexes into it.
        """
        n = len(places)
        # Diagonal: zero-cost self-loop for every place.
        matrix: dict[str, dict[str, float]] = {
            p.poi_id: {p.poi_id: 0.0} for p in places
        }

        # Upper triangle only — symmetry halves the API cost.
        pairs = [
            (places[i], places[j])
            for i in range(n)
            for j in range(i + 1, n)
        ]
        total = len(pairs)
        logger.info("Building %d×%d walking matrix (%d unique pairs)...", n, n, total)

        for idx, (a, b) in enumerate(pairs, start=1):
            t = self.get_walking_time((a.lat, a.lon), (b.lat, b.lon))
            if t is None:
                raise RuntimeError(
                    f"OSRM failed for pair {a.name!r} ↔ {b.name!r}; "
                    "cannot build complete matrix."
                )
            matrix[a.poi_id][b.poi_id] = t
            matrix[b.poi_id][a.poi_id] = t  # mirror to lower triangle

            if idx % 20 == 0 or idx == total:
                logger.info("  matrix progress: %d / %d pairs done", idx, total)

        logger.info("Matrix built: %d × %d", n, n)
        return matrix

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _walking_minutes(self, distance_m: float) -> float:
        """Convert routed distance (m) to walking time (min) at WALKING_SPEED_KMH."""
        return (distance_m / 1000.0) / WALKING_SPEED_KMH * 60.0

    def _cache_path(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> Path:
        """
        Symmetric cache key: round to 5 decimals (~1 m precision), then
        sort the pair so (A, B) and (B, A) hash to the same file.
        """
        a = (round(start[0], 5), round(start[1], 5))
        b = (round(end[0], 5), round(end[1], 5))
        pair = tuple(sorted([a, b]))
        key = hashlib.sha256(json.dumps(pair).encode()).hexdigest()[:16]
        return self._cache_dir / f"route_{key}.json"
