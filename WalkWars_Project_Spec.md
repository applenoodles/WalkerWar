# WalkWars — Final Project Specification

> **For AI Agent Implementation.** This document is the complete spec for building the project end-to-end. The student will review every file you produce — write readable, well-named code with concise inline comments where logic isn't obvious. Avoid clever one-liners.

---

## 0. How to Use This Spec

- Implement strictly in the order of **Section 13 (Build Order)**.
- After each step, run the verification in **Section 14** before moving on.
- Do **not** add features outside this spec. If something is missing, ask.
- All code in Python 3.11+. Use type hints throughout.
- **Teaching Mode (Section 18) is required** after every step.

---

## 1. Project Overview

**Project Name:** `WalkWars: 15-Minute Turf` / 步行 15 分鐘：城市搶地戰

**One-liner (EN):** A turn-based strategy game where real-world walking time — not straight-line distance — drives every move, every contest, and every territory boundary.

**One-liner (中):** 一款以真實城市步行時間為核心機制的回合制策略遊戲。

**Target Player:** A demo audience (professor + TA + classmates). The student plays vs a Greedy AI in a 6-turn match.

**Core Innovation:**
The three required APIs (Nominatim / OSRM / Folium) are not used as utilities — they are the game's physics engine.
- Nominatim generates the playing field (POIs as nodes).
- OSRM is the cost function (walking time as Action Point spend, contest tiebreaker, territory influence).
- Folium is the game board.

**Demo Scenario:** Start at 清華大學 (NTHU), 1.5 km radius, 20–25 POIs, 6 turns, 15 min AP per turn, vs Greedy AI.

---

## 2. Tech Stack (Locked)

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Web framework | Flask |
| Geocoding | Nominatim (public OSM, custom User-Agent) |
| POI discovery | Nominatim (`amenity`, `tourism`, `leisure` keywords) |
| Routing | OSRM public demo server (`router.project-osrm.org`) |
| Map rendering | Folium (Leaflet under the hood) |
| Templating | Jinja2 (Flask default) |
| Frontend | HTML + CSS (vanilla) + minimal JS for form submission |
| State | Flask session (signed cookies) + disk JSON per game |
| HTTP client | `requests` |

**No additional packages without student approval.**

---

## 3. Critical Gotchas — Read First

1. **Coordinate order is inconsistent:**
   - Nominatim returns `lat`, `lon` (as strings — cast to float)
   - OSRM URL path expects `lon,lat;lon,lat`
   - OSRM `routes[0].geometry.coordinates` returns `[lon, lat]` pairs
   - Folium expects `[lat, lon]`
   - Always use `utils/coords.py`. Never inline coordinate string building.

2. **Nominatim ToS:**
   - `User-Agent: WalkWars/1.0 (NTHU final project)` required
   - Max 1 request/second — `time.sleep(1.05)` between calls
   - `accept-language: zh-TW,en` for bilingual names

3. **OSRM matrix build is the slow path.** N=20 POIs → C(20,2)=190 calls → ~10s. Cache on disk. Log progress every 20 calls so the student knows it isn't hung.

4. **Flask session size limit ~4KB.** Store only `game_id`, `turn`, `current_player` in session. Load the full GameState (matrix, POIs, ownership) from `data/games/{game_id}.json` per request.

5. **Folium maps embed ~1MB of JS.** Render once per page request; never in a loop.

6. **Demo-day network insurance.** Pre-warm caches for the demo scenario. If APIs hang on stage, cached data must produce the same game.

7. **Contest resolution.** When AI targets a POI the player just claimed this same turn, compare OSRM walking times from each player's pre-move position. Shorter wins. Tie → player wins.

8. **Skip-turn is allowed.** If no POI is reachable within AP (rare), or player chooses to stay, no movement happens. AP does not carry over.

---

## 4. Folder Structure

```text
walkwars/
├── app.py                    # Flask app + routes (thin)
├── config.py                 # Constants, POI categories, game params
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
│
├── models/
│   ├── __init__.py
│   ├── place.py              # Place dataclass
│   └── game_state.py         # GameState, Player dataclasses
│
├── services/
│   ├── __init__.py
│   ├── poi_service.py        # Nominatim POI generation
│   ├── osrm_service.py       # Walking time queries + matrix builder
│   ├── game_engine.py        # Turn loop, claim/contest resolution, scoring
│   ├── ai_service.py         # Greedy AI opponent
│   └── map_service.py        # Folium rendering
│
├── utils/
│   ├── __init__.py
│   ├── coords.py             # to_osrm_coords, from_osrm_geometry
│   └── decorators.py         # @log_execution, @handle_api_errors
│
├── templates/
│   ├── base.html
│   ├── index.html            # Setup: origin input + start button
│   └── game.html             # Map + turn controls + score panel
│
├── static/
│   └── style.css
│
└── data/
    ├── cache/
    │   ├── poi/              # Nominatim results per (origin, radius)
    │   └── osrm/             # OSRM results per (lat1,lon1,lat2,lon2)
    └── games/                # {game_id}.json with full GameState
```

---

## 5. Config (`config.py`)

```python
from pathlib import Path

# API endpoints
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
OSRM_BASE = "https://router.project-osrm.org"

# Request headers
USER_AGENT = "WalkWars/1.0 (NTHU final project)"
ACCEPT_LANGUAGE = "zh-TW,en"
NOMINATIM_RATE_LIMIT_SEC = 1.05

# Game parameters (locked for demo)
TURNS = 6
AP_PER_TURN = 15.0              # walking minutes
POI_RADIUS_M = 1500             # search bounding box
POI_TARGET_COUNT = 22           # try to land in [20, 25]
DEMO_ORIGIN = "清華大學"

# POI categories — Nominatim keyword + value + emoji + color
POI_CATEGORIES = {
    "cafe":        {"keyword": "cafe",       "value": 2, "emoji": "☕", "color": "#a0522d"},
    "restaurant":  {"keyword": "restaurant", "value": 2, "emoji": "🍜", "color": "#d2691e"},
    "park":        {"keyword": "park",       "value": 3, "emoji": "🌳", "color": "#228b22"},
    "station":     {"keyword": "station",    "value": 3, "emoji": "🚉", "color": "#4682b4"},
    "attraction":  {"keyword": "attraction", "value": 5, "emoji": "⭐", "color": "#daa520"},
    "shop":        {"keyword": "shop",       "value": 1, "emoji": "🛒", "color": "#808080"},
    "generic":     {"keyword": None,         "value": 1, "emoji": "📍", "color": "#a9a9a9"},
}

# Combo bonuses
COMBO_LIFESTYLE_BONUS = 8       # ≥1 cafe + ≥1 park + ≥1 restaurant, pairwise ≤ 15min
COMBO_LIFESTYLE_TIME = 15.0
COMBO_TOURIST_BONUS = 10        # ≥3 attractions owned
COMBO_TOURIST_COUNT = 3

# Territory bonus
TERRITORY_BONUS_PER_POI = 1

# Player colors (Folium hex)
PLAYER_COLORS = {
    "human": "#2c7fb8",         # blue
    "ai":    "#c0392b",         # red
    "neutral": "#7f8c8d",       # gray
}
PLAYER_INFLUENCE_TINT = {       # lighter shades for influenced neutrals
    "human": "#a6cee3",
    "ai":    "#fb9a99",
    "neutral": "#bdc3c7",
}

# Cache & data directories
CACHE_DIR = Path("data/cache")
GAMES_DIR = Path("data/games")
CACHE_ENABLED = True

# Flask
SECRET_KEY_ENV = "WALKWARS_SECRET"   # read from env; fallback "dev-secret"
```

---

## 6. Class & Method Specifications

### 6.1 `Place` — `models/place.py`

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Place:
    poi_id: str                  # f"{osm_type}_{osm_id}" — stable across runs
    name: str                    # Best available name
    lat: float
    lon: float
    category: str                # Key from POI_CATEGORIES
    value: int                   # Score value (copy from config for convenience)
    osm_type: str = ""
    osm_id: str = ""
    raw_tags: dict = field(default_factory=dict)

    def to_dict(self) -> dict: ...

    @classmethod
    def from_dict(cls, d: dict) -> "Place": ...

    @classmethod
    def from_nominatim(cls, raw: dict, category: str) -> Optional["Place"]:
        """
        Build from a Nominatim element.
        Returns None if raw has no usable coordinates or no name.
        Sets value from POI_CATEGORIES[category]['value'].
        """
```

### 6.2 `GameState` & `Player` — `models/game_state.py`

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Player:
    id: str                      # "human" or "ai"
    current_poi_id: str          # Where the player stands now ("ORIGIN" or a poi_id)
    owned_poi_ids: list[str] = field(default_factory=list)
    score: int = 0

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "Player": ...

@dataclass
class GameState:
    game_id: str                 # UUID hex
    origin_label: str            # User-entered string
    origin_lat: float
    origin_lon: float
    pois: list[Place]            # All 20–25 POIs for this game
    matrix: dict[str, dict[str, float]]
        # matrix[from_id][to_id] = walking_time_min
        # Special key "ORIGIN" exists with distances from origin to each POI
    players: dict[str, Player]   # {"human": Player(...), "ai": Player(...)}
    turn: int = 1                # 1..TURNS
    current_player_id: str = "human"   # "human" or "ai"
    move_history: list[dict] = field(default_factory=list)
        # Each entry: {"turn": int, "player": str, "from": str, "to": str, "time": float, "contested": bool}
    finished: bool = False

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, d: dict) -> "GameState": ...

# Disk persistence helpers
def save_game_state(gs: GameState) -> None: ...
def load_game_state(game_id: str) -> GameState: ...
```

### 6.3 `POIService` — `services/poi_service.py`

```python
class POIService:
    """Generate game POIs near an origin via Nominatim."""

    def __init__(self, cache_dir: Path = CACHE_DIR / "poi"): ...

    @handle_api_errors(default_factory=lambda: None)
    @log_execution
    def geocode(self, query: str) -> Optional[dict]:
        """Returns {'lat': float, 'lon': float, 'display_name': str} or None."""

    @log_execution
    def generate_pois(
        self,
        origin_lat: float,
        origin_lon: float,
        radius_m: int = POI_RADIUS_M,
        target_count: int = POI_TARGET_COUNT,
    ) -> list[Place]:
        """
        For each category in POI_CATEGORIES (except 'generic'), run Nominatim
        keyword search within a viewbox. Merge, dedupe by (osm_type, osm_id),
        cap at target_count.
        Strategy: aim for variety — at most ~6 of any one category, prefer
        broad coverage.
        Rate-limit 1.05s between calls.
        """
```

**Nominatim params:**
```
GET /search
  q={keyword}
  format=jsonv2
  limit=8
  addressdetails=1
  namedetails=1
  viewbox={left},{top},{right},{bottom}
  bounded=1
  accept-language=zh-TW,en
```

### 6.4 `OSRMService` — `services/osrm_service.py`

```python
class OSRMService:
    """OSRM walking-time queries with caching."""

    def __init__(self, cache_dir: Path = CACHE_DIR / "osrm"): ...

    @handle_api_errors(default_factory=lambda: None)
    def get_walking_time(
        self, start: tuple[float, float], end: tuple[float, float]
    ) -> Optional[float]:
        """Returns walking time in minutes, or None on failure. Cached."""

    def get_walking_route(
        self, start: tuple[float, float], end: tuple[float, float]
    ) -> Optional[dict]:
        """
        Returns {'duration_min': float, 'distance_m': float, 'geometry': list[[lat,lon]]}.
        Used by map_service for drawing polylines after a move.
        """

    @log_execution
    def build_matrix(
        self,
        origin_lat: float,
        origin_lon: float,
        pois: list[Place],
        progress_callback=None,
    ) -> dict[str, dict[str, float]]:
        """
        Returns matrix[from_id][to_id] = walking_time_min.
        Keys include "ORIGIN" plus each poi.poi_id.
        Symmetric: matrix[a][b] == matrix[b][a] (OSRM is approximately symmetric
        for foot routing; we assert this and average).
        Calls get_walking_time C(N+1, 2) times — log every 20 calls.
        Missing values default to a large sentinel (999.0) so they're never picked.
        """
```

**OSRM URL:**
```
GET /route/v1/foot/{lon1},{lat1};{lon2},{lat2}
  ?overview=full
  &geometries=geojson
```

`data["routes"][0]["duration"]` is seconds → `/60`.

### 6.5 `GameEngine` — `services/game_engine.py`

```python
class GameEngine:
    """Manages turn flow, claim resolution, and scoring."""

    def __init__(self, ai: "AIService"): ...

    def new_game(
        self, origin_label: str, origin_lat: float, origin_lon: float,
        pois: list[Place], matrix: dict[str, dict[str, float]]
    ) -> GameState:
        """Initialize a fresh GameState with both players at ORIGIN."""

    def reachable_poi_ids(self, gs: GameState, player_id: str) -> list[str]:
        """Returns POI IDs where matrix[player.current][poi.id] <= AP_PER_TURN
        AND poi is not already owned by this player (can revisit others' though,
        which counts as a contest)."""

    def apply_move(self, gs: GameState, player_id: str, target_poi_id: str) -> dict:
        """
        Validate the move; update player position; resolve claim/contest;
        update score; append to move_history.
        Returns a dict describing what happened:
          {"ok": bool, "claimed": bool, "contested": bool,
           "stolen_from": str|None, "walking_time": float, "reason": str|None}
        After both players have moved this turn, advance to next turn.
        """

    def is_player_turn(self, gs: GameState) -> bool: ...
    def is_finished(self, gs: GameState) -> bool: ...

    def compute_running_score(self, gs: GameState) -> dict[str, int]:
        """Player + AI base scores (POI values only). For mid-game display."""

    def compute_final_score(self, gs: GameState) -> dict:
        """
        Returns {
          "human": {"base": int, "territory": int, "combos": list[str], "combo_bonus": int, "total": int},
          "ai": {...},
          "winner": "human" | "ai" | "tie",
          "territory_map": {poi_id: "human"|"ai"|"neutral"},
        }
        Includes weighted Voronoi territory and combo bonuses.
        """
```

### 6.6 `AIService` — `services/ai_service.py`

```python
class AIService:
    """Greedy AI opponent."""

    def choose_move(
        self,
        gs: GameState,
        ai_player: Player,
        reachable_ids: list[str],
    ) -> Optional[str]:
        """
        For each reachable POI, score:
            score = (poi.value * combo_multiplier) / walking_time
        combo_multiplier: 1.5 if claiming this POI would form a partial lifestyle
        combo or tourist trail with already-owned POIs; else 1.0.
        Return the highest-scoring POI id. None if no reachable POI.

        Tie-break: prefer POIs not owned by anyone (lowest contest risk).
        """
```

### 6.7 `MapService` — `services/map_service.py`

```python
class MapService:
    def render_game_map(
        self,
        gs: GameState,
        reachable_ids: list[str],
        territory_map: Optional[dict[str, str]] = None,
        last_route_geometry: Optional[list[list[float]]] = None,
    ) -> str:
        """
        Returns Folium HTML.
        Markers:
          - Origin: green home icon
          - Owned by human: blue DivIcon with category emoji
          - Owned by AI: red DivIcon with category emoji
          - Neutral: gray DivIcon with category emoji
          - Reachable this turn (not owned by current player): black ring outline
        If territory_map provided, tint neutral markers with influence color.
        If last_route_geometry provided, draw a colored polyline for that move.
        Popups: name, category, value, walking time from current player.
        Each marker's HTML element gets `data-poi-id="{poi_id}"` so the front-end
        can wire clicks to /move?poi_id=...
        """
```

---

## 7. Decorators (`utils/decorators.py`)

```python
def log_execution(func):
    """Log function name, args summary, elapsed time at INFO level."""

def handle_api_errors(default_factory):
    """
    Catch requests.Timeout, requests.RequestException, ValueError, KeyError;
    log with logging.exception; return default_factory().
    """
```

No `@validate_*` decorator at the route level for MVP — validation is inline (the form is tiny).

---

## 8. Flask Routes (`app.py`)

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Render `index.html` — origin input form |
| `/health` | GET | `{"status": "ok"}` for sanity checks |
| `/new` | POST | Geocode, generate POIs, build matrix, create game, redirect to `/game` |
| `/game` | GET | Render current game state (map + side panel) |
| `/move` | POST | Apply human's move, then auto-apply AI move, redirect to `/game` |
| `/game/end` | GET | Final score breakdown screen |
| `/reset` | POST | Clear session, redirect to `/` |

**Service wiring at app start:**
```python
poi_svc = POIService()
osrm_svc = OSRMService()
ai_svc = AIService()
engine = GameEngine(ai=ai_svc)
mapper = MapService()
```

**`/new` flow:**
```python
origin_input = request.form["origin"]
loc = poi_svc.geocode(origin_input)
if not loc: flash("找不到地點"); return redirect("/")
pois = poi_svc.generate_pois(loc["lat"], loc["lon"])
matrix = osrm_svc.build_matrix(loc["lat"], loc["lon"], pois)
gs = engine.new_game(loc["display_name"], loc["lat"], loc["lon"], pois, matrix)
save_game_state(gs)
session["game_id"] = gs.game_id
session["turn"] = gs.turn
session["current_player"] = gs.current_player_id
return redirect("/game")
```

**`/move` flow:**
```python
gs = load_game_state(session["game_id"])
if gs.finished: return redirect("/game/end")
target = request.form["poi_id"]
result = engine.apply_move(gs, "human", target)
if not result["ok"]:
    flash(result["reason"]); save_game_state(gs); return redirect("/game")

# After human, if game not finished, AI moves
if not engine.is_finished(gs) and gs.current_player_id == "ai":
    ai_reachable = engine.reachable_poi_ids(gs, "ai")
    ai_target = ai_svc.choose_move(gs, gs.players["ai"], ai_reachable)
    if ai_target:
        engine.apply_move(gs, "ai", ai_target)
    else:
        # AI skips
        engine.apply_move(gs, "ai", gs.players["ai"].current_poi_id)

save_game_state(gs)
session["turn"] = gs.turn
session["current_player"] = gs.current_player_id
return redirect("/game/end" if gs.finished else "/game")
```

---

## 9. Templates

### `templates/base.html`
Shared layout. Loads `style.css`. Flash messages at top. `{% block content %}{% endblock %}`.

### `templates/index.html`
- Title: "WalkWars: 15-Minute Turf"
- Subtitle: "Real walking time becomes the rules of the game."
- Form `POST /new`:
  - Text input `origin`, placeholder `清華大學`, default value `清華大學`
  - Submit button "Start Game"
- Small "How to play" expander with 3 bullets.

### `templates/game.html`
Two-column layout (CSS grid):
- **Left side panel (300px):**
  - Turn counter: `Turn 3 / 6`
  - Whose turn: badge `Your Turn` / `AI Thinking...`
  - AP display: `15 min remaining this turn`
  - Score: `You: 12   AI: 9`
  - Move history (latest 5): "T2 You → Cafe X (8 min)"
  - "End Turn (skip)" small button — submits `/move` with `poi_id=__skip__`
- **Right side (rest):**
  - Folium map `{{ map_html|safe }}`
- Marker clicks call a small inline `<script>` that submits a hidden form to `/move` with the clicked POI's `data-poi-id`.

### `templates/game_end.html`
- "Game Over" heading
- Winner banner (You Win / AI Wins / Tie)
- Score breakdown table:
  - Base POI Score
  - Territory Bonus
  - Combo Bonuses (list combos triggered)
  - Total
- Final map (full territory voronoi tinting + all routes)
- "Play Again" button (POST `/reset`)

---

## 10. CSS / UI — `static/style.css`

**Aesthetic: clean strategy game.** Not "explorer notebook" — this is a sharper, more game-y look.

- Background: very light gray `#f4f6f8`
- Text: dark slate `#2c3e50`
- Accents: player blue `#2c7fb8`, AI red `#c0392b`, neutral gray
- Headings: bold sans (system stack: `-apple-system, "Segoe UI", "Noto Sans TC", sans-serif`)
- Side panel: white card, `border-radius: 8px`, soft shadow, padding 16px
- Score numbers: large monospace
- Turn badge: pill-shaped, animated subtle pulse when it's player's turn
- Map container: full height of column, `height: calc(100vh - 32px)`, rounded
- Move history: small font, monospace timestamps
- Responsive: stack vertically below 768px

---

## 11. Game Rules — Full Detail

### 11.1 Setup
1. Player enters origin string in `/`
2. System geocodes via Nominatim → `(lat, lon, display_name)`
3. `POIService.generate_pois` runs keyword search per category in a `POI_RADIUS_M` viewbox
4. Dedupe by `(osm_type, osm_id)`, cap at `POI_TARGET_COUNT`
5. `OSRMService.build_matrix` computes pairwise walking times for `{ORIGIN, P1..PN}`
6. `GameState` created with both players at `ORIGIN`, turn 1, current player "human"

### 11.2 A Turn
1. **Player phase**:
   - Compute `reachable_ids = {p | matrix[player.current][p.id] <= AP_PER_TURN AND p not owned by player}`
   - Player clicks a reachable POI (or "End Turn")
   - `apply_move(gs, "human", target)`:
     - If `target == player.current` (skip): no movement, no claim, log skip
     - Else: walking time = `matrix[player.current][target]`
     - Update `player.current = target`
     - **Claim resolution**:
       - If POI was unowned: add to `player.owned_poi_ids`, mark as claimed
       - If POI was owned by player: no-op (just moved through own)
       - If POI was owned by opponent: this is a contest — see 11.3
   - Append to move history
   - Set `current_player_id = "ai"`

2. **AI phase**: same logic, AI picks via `AIService.choose_move`. If `choose_move` returns None (no reachable POI), AI skips.

3. **End of turn**: when both players have moved this turn, increment `turn`. If `turn > TURNS`, set `finished = True`.

### 11.3 Contest Rules (MVP)
When AI moves to a POI the player claimed **this same turn**:
- Compute `human_time = matrix[human.pre_move_position][target]`
- Compute `ai_time = matrix[ai.pre_move_position][target]`
- If `ai_time < human_time`: AI takes the POI; remove from human's `owned_poi_ids`, add to AI's; mark `contested=True, stolen_from="human"` in move history
- If `ai_time >= human_time`: human keeps it; AI still moves there (paid AP) but doesn't claim; log `contested=True, stolen_from=None`

For simplicity in MVP, contests only flow this direction (AI vs human's same-turn claim). Human cannot contest AI claims because the player moves first.

### 11.4 Scoring
**Per-player base score** = sum of `value` over owned POIs.

**Territory bonus** (computed at game end only):
- For each neutral POI `x` (not owned by anyone), compute for each player `p`:
  - `dist(p, x) = min over n in owned(p) of matrix[n][x]`
  - If `owned(p)` is empty, `dist(p, x) = matrix["ORIGIN"][x]`
- The player with the smallest `dist` "influences" `x`. Tie → no influence.
- Add `TERRITORY_BONUS_PER_POI = 1` per influenced neutral.

**Combo bonuses** (computed at game end):
- **15-minute lifestyle circle**: if a player owns at least one cafe, one park, and one restaurant such that all pairwise walking times among those three POIs are ≤ `COMBO_LIFESTYLE_TIME`, add `COMBO_LIFESTYLE_BONUS = 8`. Check up to one combo bonus per player.
- **Tourist trail**: if a player owns ≥ `COMBO_TOURIST_COUNT = 3` attractions, add `COMBO_TOURIST_BONUS = 10`.

**Total** = base + territory + combos.

---

## 12. Algorithms — Detail

### 12.1 Reachable Set
```
reachable(player) = { poi.id : matrix[player.current][poi.id] <= AP_PER_TURN
                              AND poi.id not in player.owned_poi_ids }
```
One pass over POIs. O(N).

### 12.2 Greedy AI
```
For each id in reachable_ids:
    multiplier = 1.0
    if would_complete_combo(player, id):     # check if claiming this POI brings
                                              # the AI closer to a combo bonus
        multiplier = 1.5
    score[id] = (POI[id].value * multiplier) / matrix[ai.current][id]

return argmax(score)
```
Tie-break: prefer unowned (avoid risky contests).

### 12.3 Weighted Voronoi Territory
```
For each neutral POI x:
    For each player p in {human, ai}:
        if p.owned is empty:
            dist[p] = matrix["ORIGIN"][x]
        else:
            dist[p] = min(matrix[n][x] for n in p.owned)
    if dist[human] < dist[ai]: territory[x] = "human"
    elif dist[ai] < dist[human]: territory[x] = "ai"
    else: territory[x] = "neutral"
```
O(N × P × O) where P=2 players, O=avg owned count. Tiny.

### 12.4 Combo Check (Lifestyle)
For each player:
```
cafes = [p for p in owned if p.category == "cafe"]
parks = [p for p in owned if p.category == "park"]
rests = [p for p in owned if p.category == "restaurant"]
for c in cafes:
    for k in parks:
        for r in rests:
            if max(matrix[c][k], matrix[c][r], matrix[k][r]) <= COMBO_LIFESTYLE_TIME:
                return True
return False
```
Brute-force; cubic in category sizes, but each category typically ≤ 5 POIs owned. Fine.

---

## 13. Build Order (Strict)

### Phase 1 — Core MVP

| Step | Goal | Files |
|---|---|---|
| 1 | Scaffold + `/health` | folder tree, config, requirements.txt, app.py |
| 2 | `Place` + POI generation | place.py, poi_service.py |
| 3 | OSRM single query + coords | osrm_service.py (get_walking_time), coords.py |
| 4 | Walking time matrix | osrm_service.py (build_matrix) |
| 5 | GameState + `/new` route | game_state.py, app.py (/new, /game stub), index.html |
| 6 | Game screen w/ Folium map (read-only) | map_service.py, game.html |
| 7 | Player move + reachable highlighting | game_engine.py (partial), app.py (/move) |
| 8 | AI turn (Greedy) | ai_service.py, game_engine integration |
| 9 | Contest resolution + running score panel | game_engine (full), game.html updates |
| 10 | Game end + territory + combo bonuses | game_engine (scoring), game_end.html |

### Phase 2 — Polish

| Step | Goal |
|---|---|
| 11 | UI styling (colors, panel, turn badge) — full style.css pass |
| 12 | `scripts/warm_cache.py` to pre-populate demo scenario |
| 13 | README + demo dry-run |

---

## 14. Verification Criteria

| Step | Verification |
|---|---|
| 1 | `flask run` starts; `curl /health` → `{"status":"ok"}` |
| 2 | Submitting `清華大學` to a debug route prints ≥ 15 POIs across ≥ 3 categories |
| 3 | Single `get_walking_time((lat1,lon1),(lat2,lon2))` returns a positive float; cache file appears |
| 4 | `build_matrix` for 20 POIs completes in < 30s on warm cache, logs progress; matrix is symmetric within 0.1 min |
| 5 | Form on `/` accepts "清華大學", redirects to `/game` showing a game_id; reload preserves game state via session |
| 6 | `/game` shows the map with ~22 POIs, origin marked, no clicks wired yet |
| 7 | Clicking a reachable POI moves the human there; AP "used" reflects matrix lookup; unreachable POIs do nothing |
| 8 | After human moves, AI immediately moves to a sensible POI; both moves visible in history |
| 9 | If both target same POI same turn: shorter walking time wins; score panel updates |
| 10 | After 6 turns: game_end screen shows base + territory + combos; neutral POIs tinted by influence |
| 11 | Final UI has player-color markers, clean panel, turn badge pulses on player turn |
| 12 | `python scripts/warm_cache.py` runs the demo end-to-end, populates caches; subsequent gameplay is fast |
| 13 | README has setup + demo scenario; student has rehearsed 3× under 7 min |

---

## 15. `README.md` Structure

```markdown
# WalkWars: 15-Minute Turf

> Real walking time becomes the rules of the game.

## What is this?
A turn-based strategy game played on real city maps. You and an AI compete
to claim POIs (cafes, parks, attractions) within a 15-minute walking budget
per turn. The map is the real city. The walking times are real. The strategy
is yours.

## Setup
```bash
git clone <repo>
cd walkwars
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app app run
```
Open http://localhost:5000

## Demo Scenario
1. Origin: 清華大學
2. 6 turns × 15 minutes AP
3. Opponent: Greedy AI
→ ~22 POIs auto-generated; click reachable ones to claim.

## How it works
- **Nominatim** generates POIs as game nodes
- **OSRM** computes the walking-time matrix that drives every game decision
- **Folium** renders the live game map

## API Credits
- POI search & geocoding: Nominatim / OpenStreetMap
- Walking routes: OSRM public demo server
- Map: Folium / Leaflet

## Course Info
NTHU IE&IM Final Project, Spring 2026
```

---

## 16. `requirements.txt`

```
Flask>=3.0
folium>=0.15
requests>=2.31
python-dotenv>=1.0
```

---

## 17. Notes for the AI Agent

1. **No tests beyond smoke tests.** One end-to-end check per service is enough.
2. **Logging**: Python `logging`, format `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"`, level INFO.
3. **Don't catch broad `Exception`**.
4. **Docstrings on every class and public method.** The student needs to explain these in Q&A.
5. **Inline comments only where logic isn't obvious.**
6. **`app.py` stays thin.** All logic in services.
7. **Coordinate flips are the #1 bug.** Use `utils/coords.py`.
8. **Pre-create directories**: `data/cache/{poi,osrm}/` and `data/games/` with `.gitkeep` files.
9. **Cache hit logging**: every cached service should log `"cache hit"` vs `"cache miss"` at DEBUG level so the student can verify caching works.
10. **When in doubt, ask the student** before adding features beyond this spec.

---

## 18. Teaching Mode — REQUIRED FORMAT FOR EACH STEP

> The student is a first-year IE/IM undergraduate with minimal programming background. They will be questioned on this code during a 7-minute demo. The agent MUST teach as it builds.

### After completing **each Build Order step**, produce these four artifacts in order:

#### A. 🔧 The Code
Write the actual files for this step. Follow Section 17.

#### B. 📖 Plain-English Walkthrough (per file)
```
=== FILE: services/osrm_service.py ===

WHAT THIS FILE DOES (in 1 paragraph, no jargon):
This file talks to OSRM (a free walking-route service) and finds out
how many minutes it takes to walk between two real-world places. It
remembers every answer it gets so we never have to ask twice — that's
important because OSRM is slow and our game needs to ask hundreds of
walking-time questions during setup.

KEY CONCEPTS INTRODUCED HERE:
- HTTP request: how our Python program talks to OSRM over the internet.
- Cache: a saved copy of a previous answer, used when the same question
  is asked again.
- Tuple of floats: (latitude, longitude) — a pair of numbers identifying
  a point on Earth.

WHY WE DESIGNED IT THIS WAY:
- One class per external API: keeps the OSRM-specific quirks contained.
- Cache on disk as JSON: works even if the app restarts.
- @handle_api_errors: if OSRM hiccups, our game doesn't crash.

WHEN THIS RUNS:
At game start, the GameEngine calls build_matrix once for all POIs.
The map and AI later read from the matrix without calling OSRM again.
```

#### C. 🎓 Concept Cards
First time each new concept appears:
```
=== CONCEPT CARD: Distance Matrix ===

WHAT IT IS (1 sentence):
A 2D table where T[i][j] holds the cost (walking time) to get from
location i to location j.

ANALOGY:
A train timetable, but for every pair of stations at once. Look up
"Station A row, Station B column" → that's the travel time.

WHERE IT APPEARS IN OUR CODE:
GameState.matrix — built once at game start by OSRMService.build_matrix.
Used by GameEngine.reachable_poi_ids, AIService.choose_move,
GameEngine.compute_final_score, and MapService.

WHY WE USE IT:
The game asks "can I reach POI X?" and "is POI Y closer for me or for the
AI?" hundreds of times. Computing answers on demand would mean calling
OSRM repeatedly. A precomputed matrix turns each question into a single
dictionary lookup.

LIKELY PROFESSOR QUESTION:
"Why do you precompute the matrix instead of calling OSRM during the game?"
GOOD ANSWER:
"Two reasons. First, OSRM has rate limits — calling it mid-turn risks
demo-day failure. Second, every reachability check, AI decision, and
contest resolution would otherwise cost a network round-trip. By
computing once at setup, every gameplay question becomes a hash lookup
in O(1)."
```

Required cards: `Class`, `Dataclass`, `Decorator`, `Type hint`, `HTTP request / REST API`, `JSON`, `Flask route`, `Flask session`, `Jinja2 template`, `Cache`, `Heuristic algorithm`, `Bounding box`, `Geocoding`, `Pure function`, `GeoJSON`, `Greedy algorithm`, `Distance matrix`, `Weighted Voronoi diagram`.

#### D. 📝 Mock Q&A (3–5 questions per step)
```
=== MOCK Q&A FOR STEP N ===

Q1: [a question the professor might ask about this step's code]
A1: [model answer, 2–4 sentences]
    KEY POINTS TO HIT: [bullets of must-mention items]
```

Cover at least one of: Concept, Walkthrough, Decision, Modification.

### Student's 10-Minute Ritual After Each Step

> Before moving to the next step, do this:
> 1. Read all Plain-English Walkthroughs for files created this step.
> 2. Close the laptop. Out loud, explain to a wall what this step does.
> 3. Stuck? Ask the agent: "Explain X in simpler words."
> 4. Open `MY_NOTES.md` (create if missing). Write **in your own words**, 2–4 sentences per file, what each new file does. Do NOT copy from the walkthrough.
> 5. Try to answer the Mock Q&A out loud. If you can, move on. If not, ask again.

---

## 19. Q&A Preparation Bank

### 19.1 Concept Questions

**Q: What is an API?**
A: A way for our program to ask another program for something. Nominatim has an API that takes a place name and returns coordinates. OSRM has one that takes two points and returns a walking route.

**Q: What is a class?**
A: A blueprint that bundles related data and functions together. Our `GameEngine` class holds the rules of the game — turn flow, claim resolution, scoring — so the rest of the code can say "engine.apply_move(...)" without knowing the details.

**Q: What is a dataclass?**
A: A short way to declare a class that's mostly data. Instead of writing `__init__`, `__repr__`, etc. by hand, the `@dataclass` decorator generates them. Our `Place` and `GameState` are dataclasses because they hold game state, not behavior.

**Q: What is Flask session?**
A: Flask stores small amounts of data in a signed cookie tied to the user's browser. We use it to remember which game the player is in. The game itself is too big for the cookie, so we keep only the `game_id` in the session and load the full state from disk.

**Q: What is a heuristic?**
A: A "good enough" rule that runs fast but isn't provably optimal. Our greedy AI picks the move with the best `value / walking_time` ratio. It's not guaranteed to win, but it's fast and explainable.

**Q: What is a distance matrix?**
A: A table where row i and column j hold the cost to go from location i to location j. We precompute one for all POIs at game start so every reachability and AI decision is a single dictionary lookup, not a network call.

**Q: What is a weighted Voronoi diagram?**
A: It's a partition of space where each region belongs to the "site" you can reach fastest — weighted by travel time, not straight-line distance. In our game, every neutral POI belongs to the player whose owned POI is closest by walking time.

### 19.2 Project-Specific Design Questions

**Q: Why did you turn this into a game instead of a navigation app?**
A: A navigation app uses OSRM as a utility. Our game uses OSRM as the physics engine. Every move costs walking minutes, every contest is settled by walking times, every territory boundary is a walking-time Voronoi cell. The same three APIs the assignment requires, used in a way that puts them at the center of the design.

**Q: Why precompute the walking-time matrix?**
A: Three reasons. First, OSRM has rate limits — calling it during gameplay risks demo failure. Second, every reachability check, AI decision, and contest resolution would otherwise cost a network round-trip. Third, the matrix makes the math obvious: every gameplay question becomes a hash lookup in O(1).

**Q: Why a greedy AI? Won't it be too weak?**
A: Greedy with a combo multiplier is the right complexity for a demo. It's deterministic and explainable — when asked "why did the AI pick X?", I can show the formula: `value × combo_multiplier / walking_time`. Anything fancier (minimax, MCTS) would be a black box and beyond the scope of a solo undergraduate project.

**Q: What if Nominatim doesn't find enough POIs?**
A: We run keyword search across six categories, cap each at ~6, and target 22 total. If a particular origin has fewer POIs, the game still runs with whatever it finds — the scoring scales naturally. For demo we pre-warm the cache so the count is known.

**Q: What if OSRM is slow or fails on demo day?**
A: Two layers of defense. (1) Every OSRM response is cached as JSON on disk. (2) For the demo scenario, we run `scripts/warm_cache.py` before the demo to populate the cache. On demo day, even if OSRM is down, the cache replays the game perfectly.

**Q: How does a contest get resolved?**
A: When the AI moves to a POI the player just claimed this same turn, the engine compares each player's walking time *from their pre-move position* to the contested POI, using the matrix. Shorter time wins. Tie goes to the player. This is the "step-walking version of who got there first."

**Q: Walk me through what happens when I click a POI marker.**
A: The marker's HTML has a `data-poi-id` attribute. A small inline script submits a hidden form POST to `/move` with that id. In `app.py`, `/move` loads the GameState from disk, calls `engine.apply_move("human", poi_id)`, then immediately calls AI's `choose_move` and `apply_move("ai", ai_target)`, saves the new state, and redirects back to `/game` which re-renders the map.

### 19.3 Code-Walking Patterns

When the professor points at code, narrate **what + why** in two sentences.

> "This block does **[plain English]**. We wrote it this way because **[design reason]**."

**Likely targets:**

- **The OSRM coordinate flip in `osrm_service.py`** → "OSRM expects coordinates as `lon,lat` in the URL — opposite of Folium and Nominatim. We centralize that flip in `utils/coords.py` so the rest of the code can pass `(lat, lon)` tuples without thinking about it."

- **The matrix symmetry assertion** → "OSRM walking time is approximately symmetric for pedestrians (no one-way streets matter at foot speed). We average the two directions to remove tiny noise, so `matrix[A][B] == matrix[B][A]`. This makes the territory and contest math cleaner."

- **The greedy score formula in `ai_service.py`** → "We score each candidate POI as `value × combo_multiplier / walking_time`. Combo multiplier rewards moves that bring the AI closer to a bonus. Dividing by walking_time means the AI prefers efficient claims, not just high-value ones."

- **The territory loop in `compute_final_score`** → "For each unclaimed POI, we find each player's shortest walking time to it using only their owned POIs as starting points. Whichever player's nearest owned POI is closest 'influences' that neutral. It's a weighted Voronoi diagram — same idea as the post-office problem in operations research."

### 19.4 Modification Questions (for the Bonus 2%)

| Hypothetical task | First file | Approach |
|---|---|---|
| "Change AP from 15 to 20 minutes" | `config.py` | `AP_PER_TURN = 20.0`, restart |
| "Add a 'museum' category worth 4 points" | `config.py` | Add to `POI_CATEGORIES` dict |
| "Increase turns from 6 to 8" | `config.py` | `TURNS = 8` |
| "Make AI prefer attractions over cafes" | `ai_service.py` | Add `category_preference` to score formula |
| "Show walking time on each marker's popup" | `map_service.py` | Already present in popup HTML; verify rendering |
| "Add a third player (second AI)" | `game_state.py`, `game_engine.py` | Extend `players` dict; modify turn order |

**Strategy when given an unexpected task:**
1. Read aloud, restate.
2. Open the most relevant file (`config.py` for settings; `templates/` for visual; `services/` for behavior).
3. Use Ctrl+F to find the relevant variable.
4. Smallest change that works.
5. Verify in browser.

### 19.5 The "I don't know" Safety Net

If you don't know an answer:
1. "Good question — let me check." Open the file, read it aloud, answer from what you see.
2. "I'm not 100% sure, but my understanding is X. The relevant code is in `file.py`."
3. "I don't remember exactly, but it relates to [concept], which we use because [reason]."

Honesty + repo navigation beats confident wrong answers.

---

## 20. Pre-Demo Final Checklist

| Done? | Item |
|---|---|
| ☐ | Every file in repo read and understood at walkthrough level |
| ☐ | `MY_NOTES.md` exists with own-words summary per file |
| ☐ | Can answer ≥80% of Q&A Bank (Section 19) out loud |
| ☐ | Demo scenario (清華大學, 6 turns) runs successfully twice from fresh terminal |
| ☐ | `scripts/warm_cache.py` has been run; caches populated |
| ☐ | Screenshots of working app saved (API-outage insurance) |
| ☐ | `flask --app app run` works in a fresh venv with only `requirements.txt` |
| ☐ | README setup tested by a friend |
| ☐ | 3–4 min live demo practiced 3× with a timer |
| ☐ | Know where each Build Order step's verification was completed |
