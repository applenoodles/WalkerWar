import json
import logging
import uuid
from pathlib import Path

from config import AP_PER_TURN, GAMES_DIR
from models.game_state import GameState, Player
from models.place import Place
from services.osrm_service import OSRMService
from services.poi_service import POIService

logger = logging.getLogger(__name__)


class GeocodeFailedError(Exception):
    """Origin query did not resolve to any location."""


class GameNotFoundError(Exception):
    """No game state file exists for the given game_id."""


# ----------------------------------------------------------------------
# Game creation
# ----------------------------------------------------------------------

def start_new_game(
    origin_query: str,
    poi_svc: POIService,
    osrm_svc: OSRMService,
) -> GameState:
    """
    Build a fresh GameState:
      1. Geocode origin_query (raises GeocodeFailedError if no result).
      2. Generate POIs around the origin (may raise NotEnoughPOIsError).
      3. Insert origin as pois[0] so the matrix covers it too.
      4. Build the N+1 × N+1 walking-time matrix (cached per pair).
      5. Initialise two Players sitting at "origin" with full AP.

    Caller is responsible for persisting the result via save_game_state().
    """
    loc = poi_svc.geocode(origin_query)
    if loc is None:
        raise GeocodeFailedError(f"找不到地點：{origin_query!r}")

    pois = poi_svc.generate_pois(loc["lat"], loc["lon"])

    # Make the origin look like any other Place so the matrix and reachability
    # lookups can stay uniform (no special-case branches downstream).
    origin_place = Place(
        poi_id="origin",
        name=loc.get("display_name", origin_query).split(",")[0].strip() or origin_query,
        lat=loc["lat"],
        lon=loc["lon"],
        category="generic",
        value=0,                         # origin scores no points
        osm_type="",
        osm_id="",
        raw_tags={"is_origin": True},
    )
    all_places = [origin_place] + pois

    matrix = osrm_svc.build_matrix(all_places)

    game_id = uuid.uuid4().hex[:12]
    logger.info(
        "Starting game %s — origin=%r, %d POIs (+origin), matrix %d×%d",
        game_id, origin_query, len(pois), len(matrix), len(matrix),
    )

    return GameState(
        game_id=game_id,
        turn=1,
        current_player="human",
        players={
            "human": Player(pid="human", ap=AP_PER_TURN, owned_pois=[], position="origin"),
            "ai":    Player(pid="ai",    ap=AP_PER_TURN, owned_pois=[], position="origin"),
        },
        pois=all_places,
        matrix=matrix,
        origin_lat=loc["lat"],
        origin_lon=loc["lon"],
        origin_display=loc.get("display_name", origin_query),
    )


# ----------------------------------------------------------------------
# Persistence
# ----------------------------------------------------------------------

def _game_path(game_id: str) -> Path:
    GAMES_DIR.mkdir(parents=True, exist_ok=True)
    return GAMES_DIR / f"{game_id}.json"


def save_game_state(game_id: str, gs: GameState) -> None:
    """Persist GameState to data/games/{game_id}.json (UTF-8, single-line JSON)."""
    _game_path(game_id).write_text(
        json.dumps(gs.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )


def load_game_state(game_id: str) -> GameState:
    """Load GameState from disk. Raises GameNotFoundError if missing."""
    path = _game_path(game_id)
    if not path.exists():
        raise GameNotFoundError(f"Game {game_id!r} not found at {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return GameState.from_dict(raw)
