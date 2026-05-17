from __future__ import annotations

from dataclasses import dataclass, field

from models.place import Place


@dataclass
class Player:
    """One side of the game (human or AI)."""

    pid: str                                    # "human" or "ai"
    ap: float                                   # walking minutes left this turn
    owned_pois: list[str] = field(default_factory=list)
    position: str = "origin"                    # current poi_id; both start at "origin"

    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "ap": self.ap,
            "owned_pois": list(self.owned_pois),
            "position": self.position,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Player":
        return cls(
            pid=d["pid"],
            ap=float(d["ap"]),
            owned_pois=list(d.get("owned_pois", [])),
            position=d.get("position", "origin"),
        )


@dataclass
class GameState:
    """
    Long-lived game data.  Lives on disk at data/games/{game_id}.json.

    Flask session only stores {game_id, turn, current_player} — see
    CLAUDE.md → 'Flask session size limit' — because the matrix alone is
    far larger than the 4 KB signed-cookie ceiling.
    """

    game_id: str
    turn: int                                                  # 1..TURNS
    current_player: str                                        # "human" or "ai"
    players: dict[str, Player]                                 # {"human": ..., "ai": ...}
    pois: list[Place]                                          # pois[0] is the origin
    matrix: dict[str, dict[str, float]]                        # walking minutes
    origin_lat: float
    origin_lon: float
    origin_display: str                                        # Nominatim's display_name
    history: list[dict] = field(default_factory=list)          # filled in later steps

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "turn": self.turn,
            "current_player": self.current_player,
            "players": {pid: p.to_dict() for pid, p in self.players.items()},
            "pois": [p.to_dict() for p in self.pois],
            "matrix": self.matrix,
            "origin_lat": self.origin_lat,
            "origin_lon": self.origin_lon,
            "origin_display": self.origin_display,
            "history": list(self.history),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameState":
        return cls(
            game_id=d["game_id"],
            turn=int(d["turn"]),
            current_player=d["current_player"],
            players={pid: Player.from_dict(p) for pid, p in d["players"].items()},
            pois=[Place.from_dict(p) for p in d["pois"]],
            matrix=d["matrix"],
            origin_lat=float(d["origin_lat"]),
            origin_lon=float(d["origin_lon"]),
            origin_display=d["origin_display"],
            history=list(d.get("history", [])),
        )
