# WalkWars — Agent Prompts (Per-Step)

> **How to use this file.**
> Open a fresh Claude Code session per step. Paste the **Session Setup** + the **Step Prompt**. Wait for the agent to finish, run the **Verification**, and only then move on. If something breaks, scroll to **Predicted Errors** for that step.
>
> The main spec (`WalkWars_Project_Spec.md`) is the source of truth. These prompts reference it by section number.
>
> **Token strategy:** one step per session. Don't be ambitious. If the agent's output is getting cut off, ask it to "continue" — don't start a new step on the same session.

---

## Session Setup (Run at the Start of EVERY New Session)

Paste this first, with `IMPLEMENTATION_NOTES.md`, `WalkWars_Project_Spec.md`, and `CLAUDE.md` attached (Claude Code auto-loads CLAUDE.md from the repo, but verify):

```
You are helping me build a Python Flask project called WalkWars — a turn-based
walking-time strategy game. I am a first-year IE/IM undergraduate at NTHU with
minimal programming background. You must:

1. READ IMPLEMENTATION_NOTES.md FIRST. It is a patch document that overrides
   the main spec on specific items (reachable rules, turn advancement, skip
   handling, HTTP timeouts, POI fallback, Folium click handling, session
   policy, /new structure, AI combo wording, demo insurance). Where notes
   and spec disagree, the notes WIN.
2. Then follow WalkWars_Project_Spec.md for everything else. Do not add
   features outside the spec. Do not skip ahead.
3. Operate in TEACHING MODE per Section 18 of the spec:
   - Write the code for the requested step only.
   - Then output a Plain-English Walkthrough for every file created or modified.
   - Output a Concept Card the first time any new programming concept appears.
   - Finish with 3–5 Mock Q&A items for that step with model answers.
4. After your output, STOP and wait. Do not start the next step on your own.

Confirm you have read BOTH IMPLEMENTATION_NOTES.md and the spec by:
(a) listing the 13 items in IMPLEMENTATION_NOTES.md by section heading, and
(b) listing Section 13's Build Order steps from the spec.
Then wait for me to give you the step to start.
```

Wait for the agent to confirm. **Then** paste the step prompt.

---

## Step 1 — Project Scaffolding

### Prerequisites
- Empty repo folder.
- Python 3.11+ installed.
- Spec + CLAUDE.md available to the agent.
- Session Setup prompt run.

### Prompt

```
Implement Build Order Step 1 (Project Scaffolding) only.

Deliverables:
1. Create the full folder tree per Section 4 of the spec.
   - Every Python package folder (models/, services/, utils/, scripts/) gets
     an empty __init__.py (no scripts/__init__.py — scripts is for CLIs).
   - data/cache/{poi,osrm}/ and data/games/ each get a .gitkeep file.
2. Write config.py with the EXACT contents of Section 5.
3. Write requirements.txt with the four lines from Section 16.
4. Write .gitignore covering: __pycache__/, *.pyc, .venv/, .env,
   data/cache/*/*.json, data/games/*.json, .DS_Store, .vscode/, .idea/.
   Keep .gitkeep files.
5. Write .env.example with FLASK_DEBUG=1 and WALKWARS_SECRET=dev-secret.
6. Write a minimal app.py with:
   - `from flask import Flask, jsonify`
   - `app = Flask(__name__)`
   - `app.secret_key = os.environ.get("WALKWARS_SECRET", "dev-secret")`
   - One route: GET /health returning jsonify({"status": "ok"})
   - if __name__ == "__main__": app.run(debug=True)
7. Teaching Mode artifacts: walkthrough for every file. Concept Cards for:
   Virtual Environment, requirements.txt, Flask app, Route, JSON.
   3 Mock Q&A items for Step 1.

Do not create any service classes yet. Do not write templates yet.
```

### Verification

```bash
cd <repo>
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
# Another terminal:
curl http://127.0.0.1:5000/health
# Expect: {"status":"ok"}
```

### Predicted Errors & Fixes

| Symptom | Likely Cause | Fix Prompt |
|---|---|---|
| `ModuleNotFoundError: No module named 'flask'` | Venv not activated, or pip install skipped | `source .venv/bin/activate && pip install -r requirements.txt` |
| `Address already in use` on port 5000 | Mac AirPlay or previous run on same port | "Add `app.run(debug=True, port=5001)` and verify on 5001" |
| Agent created files outside Section 4 (tests/, Dockerfile, .github/) | Overreach | "Delete every file outside the Section 4 folder tree. Step 1 is scaffolding only." |
| `__init__.py` missing in some package folders | Forgot package files | "Add empty `__init__.py` to models/, services/, utils/." |
| Agent put real secret in .env.example | Bad practice | "Replace WALKWARS_SECRET value in .env.example with `dev-secret` placeholder only." |

### Student Ritual After Step 1
1. Open `MY_NOTES.md` (create it). Write 2–3 sentences each on: what `config.py` is for, what `app.py` does today, why we use a virtual environment.
2. Out loud: "When I type `python app.py`, what happens?"

---

## Step 2 — Place Dataclass + POI Generation

### Prerequisites
- Step 1 verified. Health endpoint works.

### Prompt

```
Implement Build Order Step 2 (Place + POI generation) only.

Reference: Spec Section 6.1 (Place), Section 6.3 (POIService),
Section 7 (decorators).

Deliverables:
1. utils/decorators.py with @log_execution and @handle_api_errors per Section 7.
   - @log_execution: log function name + elapsed ms at INFO level.
   - @handle_api_errors(default_factory): catch requests.Timeout,
     requests.RequestException, ValueError, KeyError; log with
     logging.exception; return default_factory().
   - Use functools.wraps.
2. models/place.py with the Place dataclass per Section 6.1:
   - to_dict(), from_dict(), from_nominatim(raw, category) classmethods.
   - from_nominatim returns Optional[Place] — None when no name or
     unparseable coords. Use .get() everywhere; never assume Nominatim
     returns a particular field.
3. services/poi_service.py with POIService class per Section 6.3:
   - geocode(query) → {"lat": float, "lon": float, "display_name": str} | None.
     Cached at data/cache/poi/geocode_{sha256(query)}.json.
   - generate_pois(origin_lat, origin_lon, radius_m, target_count) → list[Place].
     For each category in POI_CATEGORIES (skip 'generic'), call Nominatim
     keyword search within a viewbox. time.sleep(1.05) between calls.
     Dedupe by (osm_type, osm_id). Cap each category at ~6. Cap total at
     target_count. Cache the full result under
     data/cache/poi/pois_{lat}_{lon}_{radius}.json with lat/lon rounded
     to 4 decimal places.
4. Add a small debug route GET /debug/pois in app.py that calls
   poi_service.geocode("清華大學") then generate_pois and returns the
   list as JSON. We'll remove this route in Step 5.
5. Teaching Mode artifacts. Concept Cards: Class, Dataclass, Decorator,
   Type hint, HTTP request / REST API, JSON, Cache, Bounding box, Geocoding.
   3–5 Mock Q&A.

Constraints:
- Do not implement OSRM yet.
- Do not implement game state yet.
- Use logging module, not print().
```

### Verification

```bash
python app.py
# In another terminal:
curl http://127.0.0.1:5000/debug/pois | python -m json.tool | head -50
# Expect a JSON list of 15+ places with name, lat, lon, category, value.
# Categories should include at least 3 of: cafe, restaurant, park, station,
# attraction, shop.
ls data/cache/poi/   # Should have geocode_*.json and pois_*.json
# Run the same curl again — should be fast (cache hit logged).
```

### Predicted Errors & Fixes

| Symptom | Likely Cause | Fix Prompt |
|---|---|---|
| Nominatim 403 / blocked | Missing User-Agent header | "Verify POIService sends `User-Agent: WalkWars/1.0 (NTHU final project)` on every request. Show me the headers dict." |
| Empty POI list | Viewbox math wrong | "Print the viewbox you computed before each Nominatim call. Format is `left,top,right,bottom` = `lon_min,lat_max,lon_max,lat_min`. Verify lat/lon aren't swapped." |
| `KeyError: 'namedetails'` | Missing query param | "Pass `params={'namedetails': 1, 'addressdetails': 1, ...}` not query string. Print final URL to verify." |
| Only one category in results | Loop broken after first iteration | "Print the category being queried inside the loop. Verify it iterates all 6 (cafe, restaurant, park, station, attraction, shop)." |
| `429 Too Many Requests` | Sleep not happening | "Add `time.sleep(NOMINATIM_RATE_LIMIT_SEC)` BETWEEN iterations, including after a cache miss request. Print elapsed time between calls." |
| Place names show as None | `from_nominatim` doesn't fall back | "In from_nominatim, fall back through: raw.get('namedetails',{}).get('name') → raw.get('display_name','').split(',')[0]. Return None only if both empty." |
| Chinese characters garbled | Missing accept-language | "Verify Accept-Language header is `zh-TW,en` (set via headers dict, not URL param)." |
| Decorator order swallows exceptions | `@log_execution` outside `@handle_api_errors` | "Decorator order: `@handle_api_errors(...)` on TOP, then `@log_execution` directly above the function. handle_api_errors must wrap the logged function." |
| Duplicate POIs in result | Dedupe key inconsistent types | "Cast osm_type and osm_id to str when building the dedupe set. Print the set size before and after dedup." |

### Student Ritual After Step 2
1. Open one `data/cache/poi/pois_*.json` in a text editor. Look at one entry. Find which JSON field became `place.name`.
2. Write in MY_NOTES.md: "What is a Place? Why a dataclass and not a plain dict?"
3. Out loud: "When the form is submitted, what does POIService do, step by step?"

---

## Step 3 — OSRM Single Query + Coords Helpers

### Prerequisites
- Step 2 verified. POIs generated and cached.

### Prompt

```
Implement Build Order Step 3 (OSRM single query + coordinate helpers).

Reference: Spec Section 6.4 (OSRMService — only get_walking_time and
get_walking_route in this step; build_matrix is Step 4),
Section 3 (coordinate gotchas).

Deliverables:
1. utils/coords.py with two pure functions:
   - to_osrm_coords(lat: float, lon: float) -> str
     Returns "lon,lat" string for OSRM URL.
   - from_osrm_geometry(geojson_coords: list[list[float]]) -> list[list[float]]
     Converts OSRM's [[lon,lat], ...] to Folium's [[lat,lon], ...].
   One-line docstring on each explaining the coordinate-order flip.
2. services/osrm_service.py with OSRMService class:
   - get_walking_time(start, end) → Optional[float]
     start, end are (lat, lon) tuples. Returns minutes. Cached.
     Cache key: f"{round(lat1,5)}_{round(lon1,5)}_{round(lat2,5)}_{round(lon2,5)}.json"
     Cache directory: data/cache/osrm/
     Symmetric key: when looking up, also check the reverse-order key;
     if present, use it.
   - get_walking_route(start, end) → Optional[dict]
     Returns {"duration_min": float, "distance_m": float,
              "geometry": list[[lat, lon]]} or None.
     Used for drawing routes later.
   - Both decorated with @handle_api_errors(default_factory=lambda: None)
     and @log_execution.
3. Extend the /debug/pois route OR add /debug/osrm that picks the first
   two POIs from the cached result and prints their walking time. This
   is temporary — will be removed in Step 5.
4. Teaching Mode artifacts. Concept Cards: Pure function, GeoJSON, Tuple.
   3–5 Mock Q&A. At least one Q&A on the coordinate-order flip.

Constraints:
- DO NOT implement build_matrix yet.
- Always go through utils/coords.py for the coordinate string. Never inline.
```

### Verification

```bash
python app.py
curl http://127.0.0.1:5000/debug/osrm
# Expect: {"time_min": 4.7, "from": "POI A", "to": "POI B"}
ls data/cache/osrm/   # Should have one JSON file.
# Run again: should be cache hit (logged).
```

### Predicted Errors & Fixes

| Symptom | Likely Cause | Fix Prompt |
|---|---|---|
| OSRM returns `{"code":"NoRoute"}` | Coordinates off-network or in a building | "Check `data.get('code') == 'Ok'` before reading routes. Return None on any other code. Pick two POIs in our cached list that are clearly on streets." |
| Walking time is 0 or absurdly large | Lat/lon swapped in URL | "Print the exact URL before each requests.get. Verify path is `/foot/{lon1},{lat1};{lon2},{lat2}` — LON FIRST. Use utils.coords.to_osrm_coords." |
| `KeyError: 'routes'` | Error response not handled | "Wrap `data['routes'][0]['duration']` in `if data.get('code') == 'Ok' and data.get('routes'):` check." |
| Time in hours (~0.08) | Forgot /60 conversion | "OSRM duration is in seconds. Divide by 60 for minutes." |
| Cache writes happen on failed requests | No success guard | "Only write cache on success: after `if data.get('code') == 'Ok'`. Don't poison cache with None." |
| Same point pair queried twice with different cache keys | Float precision mismatch | "Always round to 5 decimals before building cache key. Print both keys side-by-side on cache miss to debug." |

### Student Ritual After Step 3
1. Memorize: Nominatim/Folium use `(lat, lon)`; OSRM URL uses `(lon, lat)`; OSRM GeoJSON returns `[lon, lat]`. This is Q&A bait.
2. Write: "Why do we have utils/coords.py? What problem does it solve?"
3. Look at one OSRM cache JSON file. Find the duration field.

---

## Step 4 — Walking Time Matrix

### Prerequisites
- Step 3 verified. Single OSRM query works and is cached.

### Prompt

```
Implement Build Order Step 4 (Walking Time Matrix).

Reference: Spec Section 6.4 (OSRMService.build_matrix), Section 3 gotcha 3.

Deliverables:
1. Extend services/osrm_service.py with build_matrix method:
   - Inputs: origin_lat, origin_lon, pois (list[Place]),
             progress_callback (optional).
   - Output: dict[str, dict[str, float]] where keys include "ORIGIN" plus
     each poi.poi_id.
   - Algorithm:
     a. Build list of points: [("ORIGIN", lat, lon)] + [(p.poi_id, p.lat, p.lon) for p in pois]
     b. For each unordered pair (i, j) where i < j:
        - Call get_walking_time
        - If result is None, use 999.0 as sentinel
        - matrix[i_id][j_id] = result
        - matrix[j_id][i_id] = result  (symmetric)
     c. matrix[id][id] = 0.0 for every id
     d. Log progress every 20 pair calls: f"Matrix progress: {done}/{total}"
   - Decorated with @log_execution.
2. Update /debug route to ALSO show:
   - Number of POIs
   - Number of matrix entries
   - Average walking time
   - Maximum walking time
   - Symmetry check: pick 3 random pairs and verify matrix[a][b]==matrix[b][a]
3. Teaching Mode artifacts. Concept Card: Distance matrix.
   3–5 Mock Q&A. At least one: "Why precompute the matrix instead of
   calling OSRM during the game?"

Constraints:
- No new dependencies.
- Do not save the matrix to disk yet — that's Step 5 (with GameState).
- Matrix must include "ORIGIN" as a key so reachability from start works.
```

### Verification

```bash
python app.py
# /debug now also shows matrix stats
curl http://127.0.0.1:5000/debug/pois
# Expect output like:
#   "poi_count": 22,
#   "matrix_size": 23 (22 POIs + ORIGIN),
#   "avg_walking_time_min": 8.3,
#   "max_walking_time_min": 22.1,
#   "symmetry_check": "OK"

# First run: takes 10-30 seconds, logs progress every 20 pairs.
# Second run: should be <1 second (all cache hits).
```

### Predicted Errors & Fixes

| Symptom | Likely Cause | Fix Prompt |
|---|---|---|
| Matrix build takes >2 minutes | Calling OSRM for both orders | "build_matrix should call get_walking_time ONCE per unordered pair (i<j), then set both matrix[a][b] and matrix[b][a]. Verify the i<j check." |
| Symmetry check fails | Two separate OSRM calls returning slightly different values | "OSRM is approximately symmetric but not exactly. After both directions are computed via the SAME single call (via the symmetric cache key in Step 3), they should match. Verify the symmetric cache key check is hit. If not, average the two: matrix[a][b] = matrix[b][a] = (t_ab + t_ba) / 2." |
| KeyError when looking up matrix["ORIGIN"][some_id] | ORIGIN missing | "Verify 'ORIGIN' is the first element in the points list. Print matrix.keys() to confirm 'ORIGIN' is present." |
| Some matrix entries are 999.0 | OSRM failed on those pairs | "This is expected for unreachable points. Log a WARNING with the pair when 999.0 is used. The game treats these as unreachable, which is correct behavior." |
| Out of memory / huge matrix | N is too large | "Verify POI_TARGET_COUNT in config.py is 22, not larger. For demo we want ~20-25 POIs, not 100." |
| Cache hit logging not visible | Logging level not set | "Set logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s') in app.py before app starts." |

### Student Ritual After Step 4
1. Compute by hand: with 22 POIs + ORIGIN, how many unordered pairs are there? `C(23,2) = 253`. This is the number of OSRM calls on cold cache.
2. Out loud: "Why are we OK that the matrix takes 30 seconds to build?"
3. Open one matrix entry. Trace where `matrix["ORIGIN"][P12]` comes from.

---

## Step 5 — GameState + /new Route

### Prerequisites
- Step 4 verified. Matrix builds and is logged.

### Prompt

```
Implement Build Order Step 5 (GameState + /new flow).

Reference: Spec Section 6.2 (GameState, Player), Section 8 (routes),
Section 9 (templates).

Deliverables:
1. models/game_state.py with Player and GameState dataclasses per Section 6.2:
   - Both have to_dict() and from_dict() classmethods.
   - GameState.to_dict serializes pois (using Place.to_dict) and players.
   - GameState.from_dict reconstructs Place instances.
   - Two module-level functions:
     - save_game_state(gs: GameState) → None
       Writes to data/games/{game_id}.json.
     - load_game_state(game_id: str) → GameState
       Reads and reconstructs. Raises FileNotFoundError on missing.
2. templates/base.html: simple shared layout, flash messages, content block,
   loads static/style.css (file can be empty for now).
3. templates/index.html: form POSTing to /new with one text input named
   `origin` (default value "清華大學") and a Submit button. Below the form,
   a small "How to play" section with 3 bullets.
4. templates/game.html: STUB ONLY for this step.
   Show: "Game {{ gs.game_id }} | Turn {{ gs.turn }} / 6 | Player: {{ gs.current_player_id }}"
   List all POIs as a simple <ul>.
   Show the matrix size: "{{ gs.pois|length }} POIs, {{ matrix_count }} matrix entries"
5. Update app.py:
   - Add SECRET_KEY from environment.
   - Import services: POIService, OSRMService.
   - GET / renders index.html.
   - POST /new:
     a. Read `origin` from form
     b. geocode(origin); if None, flash error and redirect to /
     c. generate_pois(lat, lon)
     d. build_matrix(lat, lon, pois)
     e. Create GameState via uuid.uuid4().hex for game_id; both players
        start at "ORIGIN"; turn=1; current_player="human"
     f. save_game_state(gs)
     g. session["game_id"] = gs.game_id; session.modified = True
     h. redirect to /game
   - GET /game:
     a. If "game_id" not in session, redirect to /
     b. gs = load_game_state(session["game_id"])
     c. render_template("game.html", gs=gs, matrix_count=...)
   - REMOVE /debug routes from previous steps.
6. Teaching Mode artifacts. Concept Cards: Flask session, Jinja2 template,
   UUID. 3-5 Mock Q&A.

Constraints:
- Do not render Folium map yet (Step 6).
- Do not implement /move yet (Step 7).
- No new dependencies.
```

### Verification

```bash
python app.py
# Browser: http://127.0.0.1:5000/
# Submit form with default "清華大學".
# Expect 10-30 second wait (matrix build) — DON'T REFRESH.
# After redirect, /game shows:
#   Game <some-uuid> | Turn 1 / 6 | Player: human
#   22 POIs, 253 matrix entries
#   <ul> of POI names
# Reload /game: same state shown (loaded from disk via session).
ls data/games/   # Should have one .json file.
```

### Predicted Errors & Fixes

| Symptom | Likely Cause | Fix Prompt |
|---|---|---|
| `RuntimeError: session is unavailable because no secret key was set` | SECRET_KEY missing | "In app.py, set `app.secret_key = os.environ.get('WALKWARS_SECRET', 'dev-secret')` after `app = Flask(__name__)`." |
| Form submit hangs forever | Matrix build is slow on cold cache | "Expected on first run. Check logs — should see 'Matrix progress: 20/253' etc. If actually frozen (no log progress), check that the network can reach router.project-osrm.org." |
| `TypeError: Object of type Place is not JSON serializable` | save_game_state doesn't convert | "GameState.to_dict() must convert each Place via Place.to_dict(), and each Player via Player.to_dict(). The save function should call gs.to_dict() and json.dump that." |
| `KeyError: 'pois'` on reload | from_dict not reconstructing | "GameState.from_dict must reconstruct each Place via Place.from_dict for the 'pois' key." |
| Session lost on every request | Cookie not being sent | "Verify browser accepts cookies. Try a different browser. Also check: `session.modified = True` after mutation." |
| /game shows stale data after /new | Session has old game_id | "After save_game_state, set `session['game_id'] = gs.game_id` and `session.modified = True` BEFORE the redirect." |
| Multiple game files accumulate | No cleanup | "This is expected for now. Step 13 will handle cleanup. For development, occasionally `rm data/games/*.json`." |

### Student Ritual After Step 5
1. Open the saved game JSON file. Find: matrix["ORIGIN"], players, turn.
2. Write in MY_NOTES.md: "What is Flask session? Why don't we store the matrix in it?"
3. Out loud: "When I submit the form, what happens step by step until I see /game?"

---

## Step 6 — Folium Map (Read-Only)

### Prerequisites
- Step 5 verified. GameState round-trips through disk.

### Prompt

```
Implement Build Order Step 6 (Folium map rendering, read-only for this step).

Reference: Spec Section 6.7 (MapService).

Deliverables:
1. services/map_service.py with MapService class:
   - render_game_map(gs, reachable_ids=None, territory_map=None,
                     last_route_geometry=None) -> str
   - Origin: folium.Marker at (gs.origin_lat, gs.origin_lon) with green
     home icon. Tooltip = gs.origin_label.
   - For each POI:
     - Determine owner: which player_id owns it, or "neutral"
     - Get color: PLAYER_COLORS[owner]
     - Marker: folium.Marker with folium.DivIcon containing
       `<div class="poi-marker" data-poi-id="{poi.poi_id}"
              style="background:{color}; color:white;
                     border-radius:50%; width:32px; height:32px;
                     display:flex; align-items:center; justify-content:center;
                     font-size:16px; cursor:pointer;
                     box-shadow:0 2px 4px rgba(0,0,0,0.3);">
            {emoji}
        </div>`
     - Popup with HTML: name, category, value, walking time from current
       player's position (lookup matrix[current][poi.poi_id]). Bilingual
       not required.
   - Auto-fit bounds to include origin + all POIs (use folium.FitOverlays
     or compute manually).
   - Return m.get_root().render() — the full HTML string.
2. Update GET /game route:
   - render the map via mapper.render_game_map(gs)
   - pass map_html into render_template
3. Update templates/game.html:
   - Two-column CSS grid layout (will be styled in Step 11; basic for now)
   - Left side: existing turn/player info; remove the <ul> of POIs (they're
     on the map now)
   - Right side: {{ map_html|safe }} in a div with class "map-container"
   - Add MINIMAL inline CSS (just enough so the map shows):
     .map-container { height: 600px; }
4. Teaching Mode artifacts. Concept Cards: Folium / Leaflet relationship,
   HTML escaping (|safe). 3-5 Mock Q&A.

Constraints:
- Markers are NOT clickable yet (Step 7).
- No reachable highlighting yet (also Step 7).
- No territory tinting yet (Step 10).
```

### Verification

```bash
python app.py
# Browser: submit form, get to /game.
# Expect: map fills right side, all 22 POIs visible as emoji markers,
# origin marked with green home icon, map auto-zoomed to fit.
# Clicking a marker shows popup with name + category + walking time.
# Markers are NOT clickable (no action yet).
```

### Predicted Errors & Fixes

| Symptom | Likely Cause | Fix Prompt |
|---|---|---|
| Map shows but is blank gray | Tile layer blocked or no internet | "Default folium uses OSM tiles. Check browser console for blocked tile requests. If on a restricted network, that's the issue." |
| Map shows at tiny size | Container has no height | "Add `.map-container { height: 600px; }` to inline CSS in game.html for now. Step 11 will move this to style.css." |
| Markers in wrong locations | Lat/lon swapped in folium.Marker | "folium.Marker takes `location=[lat, lon]` — LAT FIRST. Show the code." |
| Emoji shows as a box | Font fallback | "DivIcon HTML must include emoji directly in the div text. Modern browsers handle this. Try a different emoji like ⭐ to verify it's not a font issue." |
| Map doesn't fit all POIs | fit_bounds not called | "After adding all markers, compute bounds = [[min_lat, min_lon], [max_lat, max_lon]] and call m.fit_bounds(bounds, padding=(20, 20))." |
| /game extremely slow | Folium render runs even when GameState unchanged | "Folium render is ~200ms; this is acceptable for our scale. If unbearably slow, check that build_matrix isn't being called on /game (only /new should call it)." |
| Markers show but popups don't open | DivIcon swallows clicks | "Use folium.Popup with the marker's `popup=` arg. The DivIcon click is for Step 7." |

### Student Ritual After Step 6
1. Open browser dev tools, inspect a marker. Find the `data-poi-id` attribute. We'll use this in Step 7.
2. Write: "What does Folium do under the hood? What's the relationship between Folium and Leaflet?"

---

## Step 7 — Player Move + Reachable Highlighting

### Prerequisites
- Step 6 verified. Map renders with POIs.

### Prompt

```
Implement Build Order Step 7 (Player turn: select reachable POI + claim).

Reference: Spec Section 6.5 (GameEngine partial — apply_move,
reachable_poi_ids, is_player_turn), Section 11 (game rules).

Deliverables:
1. services/game_engine.py with GameEngine class:
   - __init__(self, ai=None): ai param is None for now.
   - new_game(origin_label, origin_lat, origin_lon, pois, matrix) -> GameState
   - reachable_poi_ids(gs, player_id) -> list[str] per Section 12.1.
   - apply_move(gs, player_id, target_poi_id) -> dict per Section 6.5.
     For Step 7, contest resolution can be simplified: if POI already owned
     by anyone, log warning and treat as unreachable (this is OK because
     in MVP only human moves first each turn; AI vs human contest is Step 9).
     Special case: if target_poi_id == player.current_poi_id, treat as skip
     (no movement, no claim).
     After human moves, advance current_player_id to "ai" (AI logic is Step 8).
   - is_player_turn(gs) -> bool
   - is_finished(gs) -> bool (turn > TURNS)
2. Update services/map_service.py:
   - render_game_map now accepts reachable_ids: list[str]
   - For reachable, NOT-owned-by-current-player POIs, wrap the DivIcon
     with an extra outline: add to style:
     `outline: 3px solid #2c3e50; outline-offset: 2px;`
   - Owned POIs use PLAYER_COLORS[owner] background.
3. Update templates/game.html:
   - Add a hidden form: <form id="move-form" method="POST" action="/move">
       <input type="hidden" name="poi_id" id="poi_id_input">
     </form>
   - Add inline <script> at bottom:
     ```
     document.querySelectorAll('.poi-marker').forEach(el => {
       el.addEventListener('click', e => {
         e.stopPropagation();
         const id = el.dataset.poiId;
         document.getElementById('poi_id_input').value = id;
         document.getElementById('move-form').submit();
       });
     });
     ```
   - But this fires INSIDE the Folium iframe — won't work. So:
     Use folium.Marker's popup with an HTML button that calls a top-frame
     function. Easiest: each marker's popup includes
     `<button onclick="window.parent.submitMove('{poi_id}')">Move here</button>`
     and game.html defines window.submitMove on the parent frame.
4. Add POST /move route in app.py:
   - Load game state. If finished, redirect to /game/end (stub for now —
     just redirect to / with flash "Game over").
   - target = request.form["poi_id"]
   - reachable = engine.reachable_poi_ids(gs, "human")
   - If target not in reachable AND target != current: flash error,
     redirect to /game.
   - result = engine.apply_move(gs, "human", target)
   - For Step 7 only: after human moves, AI does NOT move yet. Just advance
     current_player to "ai" briefly, then back to "human" and increment turn
     (this simulates AI's turn passing silently — placeholder until Step 8).
   - save_game_state(gs); update session; redirect to /game.
5. Update GET /game to compute reachable_ids and pass to map_service.
6. Teaching Mode artifacts. Concept Cards: Greedy algorithm (preview — full
   greedy is Step 8), Form submission, Reachable set. 3–5 Mock Q&A.

Constraints:
- DO NOT implement AI in this step. Use the placeholder "skip" for AI's
  turn — comment clearly that Step 8 will fix this.
- Contest resolution is also Step 9. For this step, if a POI is owned, it
  acts as unreachable.
```

### Verification

```bash
python app.py
# Submit form → /game.
# Reachable POIs have a visible outline.
# Click a reachable POI's popup "Move here" button → page reloads.
# That POI is now blue (player color), marked owned.
# Player position has moved (next turn's reachable set is different).
# Turn counter increments (because Step 7 silently skips AI).
# After ~6 moves, get "Game over" flash and redirect.
```

### Predicted Errors & Fixes

| Symptom | Likely Cause | Fix Prompt |
|---|---|---|
| Marker click does nothing | Click handler inside iframe | "Use popup button with onclick='window.parent.submitMove(\"{poi_id}\")' instead of trying to bind clicks to DivIcon. Define window.submitMove in game.html outer template." |
| `submitMove is not defined` | Parent function not defined | "In game.html, add `<script>window.submitMove = function(id) { document.getElementById('poi_id_input').value = id; document.getElementById('move-form').submit(); };</script>` BEFORE the map_html div." |
| Player can move to unreachable POI | Reachable check missing | "Verify /move route checks `if target not in reachable_ids` before calling apply_move." |
| Reachable outline shows on owned POIs too | Outline applied unconditionally | "reachable_ids should EXCLUDE POIs already owned by current player. Check Section 12.1 condition: `poi.id not in player.owned_poi_ids`." |
| Turn doesn't advance | Logic in apply_move broken | "After human moves, set current_player='ai'. After the placeholder AI step (also in /move route for now), set current_player='human' and increment turn." |
| Game state has stale current_poi_id | apply_move not updating | "After successful move, set `gs.players[player_id].current_poi_id = target_poi_id`. Verify by printing player position before and after." |
| /move fails with 405 | Form method wrong | "Verify form has `method='POST'` and route is `@app.post('/move')` or `@app.route('/move', methods=['POST'])`." |

### Student Ritual After Step 7
1. Play through 6 turns. Watch the map evolve.
2. Open game JSON after each move; note how `current_poi_id` changes.
3. Write: "What does 'reachable' mean in this game? Why are some markers outlined and some not?"

---

## Step 8 — AI Turn (Greedy)

### Prerequisites
- Step 7 verified. Player can move; turns advance.

### Prompt

```
Implement Build Order Step 8 (Greedy AI opponent).

Reference: Spec Section 6.6 (AIService), Section 12.2.

Deliverables:
1. services/ai_service.py with AIService class:
   - choose_move(gs, ai_player, reachable_ids) -> Optional[str]
   - For each id in reachable_ids:
     - base = poi.value / matrix[ai_player.current_poi_id][id]
     - combo_multiplier:
       - If claiming this POI would give the AI ≥1 cafe AND ≥1 park AND
         ≥1 restaurant (need not satisfy time check yet), → 1.5
       - If claiming this POI would give the AI ≥3 attractions, → 1.5
       - Else 1.0
     - score = base * combo_multiplier
   - Return argmax(score). Tie-break: prefer POIs not owned by anyone.
   - Return None if reachable_ids is empty.
2. Update GameEngine constructor to accept ai: AIService.
3. Update /move route in app.py:
   - Replace the Step-7 placeholder "skip AI turn" with real AI logic:
     ```python
     # After human move
     if not engine.is_finished(gs):
         ai_reachable = engine.reachable_poi_ids(gs, "ai")
         ai_target = ai_service.choose_move(gs, gs.players["ai"], ai_reachable)
         if ai_target:
             engine.apply_move(gs, "ai", ai_target)
         else:
             # AI skips (no reachable POI)
             engine.apply_move(gs, "ai", gs.players["ai"].current_poi_id)
     ```
   - apply_move must handle "ai" player_id the same way as "human"
     (claim if unowned; do nothing if owned by self).
4. Update templates/game.html side panel:
   - Show last move from each player in move history (most recent 5 entries):
     `T2 You → 餐廳A (8.3 min)`
     `T2 AI → 咖啡店B (5.1 min)`
5. Teaching Mode artifacts. Concept Cards: Greedy algorithm (full),
   argmax. 3–5 Mock Q&A.

Constraints:
- Do NOT implement contest resolution yet (Step 9).
- AI should never pick a POI owned by anyone (including itself).
- Log the AI's chosen score and runner-up score at DEBUG level so the
  student can see "why did AI pick X?" — helpful for Q&A.
```

### Verification

```bash
python app.py
# Submit form, play one turn.
# After clicking a POI: page reloads.
# Map shows: your POI is BLUE, AI's POI is RED.
# Move history shows both moves with walking times.
# AI's choice should be sensible — high-value POI within reasonable walking time.
# Play 6 turns. Both colors should grow.
```

### Predicted Errors & Fixes

| Symptom | Likely Cause | Fix Prompt |
|---|---|---|
| AI always picks the same POI | Tie-break broken | "Print score for each candidate. If multiple POIs have the same top score, prefer ones not owned by anyone. Print which one was selected." |
| AI picks an owned POI | Filter missing | "reachable_poi_ids excludes own-owned but should ALSO exclude opponent-owned in the AI's case. Or filter inside choose_move: skip if poi.poi_id is in either player's owned list." |
| AI score formula gives 0 division | matrix[a][b] == 0 (same POI) | "Already excluded by reachable filter (player_current is not in reachable). But guard: `if walking_time > 0` before dividing." |
| Combo multiplier always 1.5 | Logic backwards | "Multiplier should be 1.5 only if THIS POI being claimed COMPLETES one of the two combos. Use a helper: would_complete_combo(player_after_claiming_id)." |
| AI move not appearing in history | apply_move not appending | "Both human and AI apply_move calls should append to gs.move_history. Verify the append is at the end of apply_move, not in a player-specific branch." |
| Move history shows wrong walking time | Time read after position update | "Capture `time = matrix[player.current_poi_id][target]` BEFORE setting player.current_poi_id = target." |

### Student Ritual After Step 8
1. Play a full game. Note which POIs the AI picks vs you.
2. Open the game JSON, find `move_history`. Trace the AI's logic.
3. Out loud: "Why does the AI prefer high-value POIs that are close? What's its formula?"

---

## Step 9 — Contest Resolution + Running Score

### Prerequisites
- Step 8 verified. AI plays.

### Prompt

```
Implement Build Order Step 9 (Same-turn contest resolution + running score).

Reference: Spec Section 11.3 (contest rules), Section 6.5 (compute_running_score).

Deliverables:
1. Update game_engine.apply_move:
   - When player_id is "ai" AND target_poi_id is owned by "human" AND
     that ownership was set THIS TURN (check move_history for human's move
     this turn targeting this same POI):
     - human_time = matrix[human.pre_move_position_this_turn][target]
     - ai_time = matrix[ai.current_poi_id][target]  # ai's pre-move position
     - if ai_time < human_time:
         - Remove from human's owned_poi_ids
         - Add to ai's owned_poi_ids
         - Set move_history entry contested=True, stolen_from="human"
       else:
         - Human keeps it (no change to ownership)
         - AI still moves there (pays AP cost) but doesn't claim
         - Set move_history entry contested=True, stolen_from=None
   - For AI moving to opponent-owned POIs from PREVIOUS turns: no contest
     in MVP — those POIs act as unreachable (filtered out in
     reachable_poi_ids for AI; or in choose_move).
   - Hint: track "pre_move_position" — easiest is to look at the previous
     entry in move_history for that player, or store it when apply_move
     starts.
2. Add compute_running_score(gs) -> dict[str, int]:
   - For each player, sum POI values over owned_poi_ids.
   - Return {"human": int, "ai": int}.
3. Update /game route:
   - Compute running_score = engine.compute_running_score(gs)
   - Pass to template.
4. Update templates/game.html side panel:
   - Show: `Score — You: {{ running_score.human }}   AI: {{ running_score.ai }}`
   - In move history, show contested moves differently:
     `T2 AI → Cafe X (5.1 min) [stole from you]` in red.
5. Teaching Mode artifacts. Mock Q&A on contest rules. At least one
   modification scenario: "What if both players tied?"

Constraints:
- Contests only flow AI → human in MVP (human moves first).
- Tie → human wins (proposal says so; design for fairness).
- Do NOT implement weighted Voronoi yet (Step 10).
```

### Verification

```bash
python app.py
# Play a game. To trigger a contest, do this:
# - Turn 1: claim a POI close to you (say 5 min away).
# - Watch AI's turn. If AI also targets that POI:
#   - Walking times printed in logs
#   - Move history shows "[stole from you]" if AI's time < yours
# - Otherwise, replay until you see a contest.
# Running score updates each turn.
```

### Predicted Errors & Fixes

| Symptom | Likely Cause | Fix Prompt |
|---|---|---|
| Contest never triggers even when AI targets player's POI | Filter excluding it too early | "reachable_poi_ids for AI should INCLUDE POIs owned by human (so AI can contest). Only exclude AI's own POIs. Then contest logic in apply_move handles the rest." |
| Pre-move position lost | Captured after update | "At the start of apply_move, save `pre_move_position = gs.players[player_id].current_poi_id` to a local variable. Use that for the contest comparison." |
| Wrong player keeps the POI | Comparison direction | "Re-read Section 11.3: shorter walking time wins. `if ai_time < human_time: AI takes it`. NOT <=." |
| Running score wrong | Score includes contested-but-not-claimed POIs | "Only count POIs in player.owned_poi_ids at score time. If a contest fails for AI, the POI stays in human's owned list — that's correct." |
| Score panel doesn't update | Not passed to template | "GET /game must compute running_score = engine.compute_running_score(gs) and pass it." |

### Student Ritual After Step 9
1. Trigger a contest. Read the logs to see the walking times compared.
2. Write: "How does a contest work? Why does the player win ties?"

---

## Step 10 — Game End + Territory + Combos

### Prerequisites
- Step 9 verified. Contests resolve; score shows.

### Prompt

```
Implement Build Order Step 10 (Game end + weighted Voronoi territory +
combo bonuses).

Reference: Spec Section 6.5 (compute_final_score), Section 11.4,
Section 12.3, Section 12.4.

Deliverables:
1. game_engine.py:
   - compute_final_score(gs) -> dict per Section 6.5. Includes:
     - base (POI values)
     - territory (Voronoi count × TERRITORY_BONUS_PER_POI)
     - combos (list of triggered combo names)
     - combo_bonus (sum)
     - total
     - territory_map (dict[poi_id, "human" | "ai" | "neutral"])
     - winner: "human" | "ai" | "tie"
   - Helper _compute_voronoi_territory(gs) per Section 12.3.
   - Helper _check_lifestyle_combo(player, gs) per Section 12.4 (brute force).
   - Helper _check_tourist_combo(player) — own ≥3 attractions.
2. Update GET /game:
   - If gs.finished, redirect to /game/end.
3. Add GET /game/end route:
   - Load game state.
   - If not finished, redirect to /game.
   - Compute final_score = engine.compute_final_score(gs).
   - Render the map ONE MORE TIME with territory_map applied (neutral
     POIs tinted with PLAYER_INFLUENCE_TINT[territory_owner]).
   - render_template("game_end.html", gs=gs, score=final_score, map_html=...)
4. templates/game_end.html per Section 9 (game_end.html sub-section):
   - Winner banner (color the banner based on winner)
   - Score breakdown table for each player:
     - Base POI Score
     - Territory Bonus (with count)
     - Combo Bonuses (list each combo triggered)
     - Total
   - Full map with territory tinting
   - "Play Again" button POSTing to /reset
5. Add POST /reset route:
   - session.clear()
   - redirect to /
6. Update map_service.py:
   - render_game_map now accepts territory_map. When provided, neutral
     POIs use PLAYER_INFLUENCE_TINT[territory_map[poi_id]] as their
     background instead of PLAYER_COLORS["neutral"].
7. Teaching Mode artifacts. Concept Card: Weighted Voronoi diagram.
   3-5 Mock Q&A, including: "Explain the Voronoi territory calculation."

Constraints:
- No new dependencies.
- Combo check brute-force is OK (each player owns ≤6 in MVP).
- Tie-breakers: prefer human in any tie.
```

### Verification

```bash
python app.py
# Play through 6 turns.
# After turn 6 (both players moved), get redirected to /game/end.
# Expect:
#   - Winner banner (You Win / AI Wins / Tie)
#   - Both players' score breakdowns
#   - "Combo Bonuses" lists triggered combos by name
#   - Map shows neutral POIs in lighter shades of player colors based on
#     who influences them (closer by walking time)
# Click "Play Again" → redirected to /, session cleared.
```

### Predicted Errors & Fixes

| Symptom | Likely Cause | Fix Prompt |
|---|---|---|
| /game/end shows score=0 for everyone | finished flag not set | "Verify game_engine.apply_move increments turn AND sets gs.finished=True when turn > TURNS." |
| Territory bonus is 0 | All POIs are owned (no neutrals) | "This is possible with 22 POIs and 12 max claims (6 turns × 2 players). Verify by printing the count of neutral POIs. If all are owned, territory bonus should legitimately be 0." |
| Voronoi treats owned POIs as neutral | Filter wrong | "Only iterate POIs that are not in human.owned + ai.owned for territory computation." |
| Voronoi assigns wrong player | argmin direction | "We want the player with the SMALLEST distance to influence the neutral. Use `min(dist) → player`. If tied, neutral stays neutral." |
| Combo bonus always triggered | Condition check loose | "Lifestyle combo requires ALL THREE categories (cafe + park + restaurant) AND pairwise walking time among the three ≤ 15. Print the matrix lookups during check." |
| Tourist combo over-triggered | ≥3 condition wrong | "Tourist combo: count POIs with category=='attraction'. Bonus only if count >= 3, exactly +10." |
| Map doesn't tint neutrals | territory_map not passed | "GET /game/end must compute territory_map and pass it to render_game_map. Verify with browser dev tools that neutral marker backgrounds differ." |

### Student Ritual After Step 10
1. Play 3 full games. Note when combos trigger vs not.
2. Write: "What is weighted Voronoi territory in our game? Why does walking time matter, not direct distance?"
3. Out loud: trace the full score calculation for a finished game.

---

## Step 11 — UI Styling

### Prerequisites
- Step 10 verified. Game ends and shows scores.

### Prompt

```
Implement Build Order Step 11 (UI styling pass).

Reference: Spec Section 10.

Deliverables:
1. Write static/style.css per Section 10:
   - Background #f4f6f8, text #2c3e50
   - System font stack: -apple-system, "Segoe UI", "Noto Sans TC", sans-serif
   - Side panel: white card, border-radius 8px, soft shadow, padding 16px
   - Score numbers: monospace font, size 24px
   - Turn badge: pill-shaped div, color-coded by current player
   - Move history: small font, monospace timestamps
   - Map container: full height of right column
   - Game end winner banner: gradient background, large text, color-coded
2. Update templates/game.html:
   - Apply CSS classes: .side-panel, .map-container, .turn-badge,
     .score, .score-human, .score-ai, .move-history, .move-entry,
     .move-stolen
3. Update templates/game_end.html:
   - .winner-banner.human / .winner-banner.ai / .winner-banner.tie
   - .score-breakdown-table
4. Update templates/index.html:
   - Center the form, large title, "How to play" expander styled
5. Add a meta viewport tag in base.html for mobile.
6. @media (max-width: 768px) — stack the two-column layout vertically.
   Side panel above, map below.
7. Teaching Mode artifacts. Concept Cards: CSS grid, Media query.
   2-3 Mock Q&A on UI choices.

Constraints:
- No CSS framework. Hand-written only.
- Keep style.css under 250 lines.
- No JavaScript beyond the existing window.submitMove.
```

### Verification
- Visually inspect each page on desktop and mobile width (Chrome dev tools).
- All three screens (index, game, game_end) look intentional and game-y.
- Turn badge clearly indicates whose turn it is.
- Score is readable at a glance.

### Predicted Errors & Fixes

| Symptom | Likely Cause | Fix Prompt |
|---|---|---|
| Map ignored new styling | Map is inside Folium iframe | "You can't style inside the iframe. Only style the outer `.map-container`. Folium's internal CSS is fixed." |
| Mobile layout doesn't stack | Missing viewport meta | "Add `<meta name='viewport' content='width=device-width, initial-scale=1'>` in base.html `<head>`." |
| Markers look different (style changed) | CSS bleed into DivIcon | "DivIcon CSS is inline in map_service.py. Don't override .poi-marker class in style.css — keep DivIcon styling inline." |
| Text too small / too large | Bad font-size choices | "Use rem units, not px. Body 1rem (16px), score 1.5rem, headings 2rem. Adjust to taste." |

---

## Step 12 — Cache Warming Script

### Prompt

```
Create scripts/warm_cache.py to pre-populate caches for the demo scenario.

Deliverables:
1. scripts/warm_cache.py:
   - Imports POIService, OSRMService from the project.
   - Configures logging to INFO.
   - For each demo origin (default: ["清華大學"]):
     - geocode → generate_pois → build_matrix
   - Prints summary: cache files created, total OSRM calls, elapsed time.
2. Make it executable:
   `python scripts/warm_cache.py`
3. Optionally accept origin as a CLI arg:
   `python scripts/warm_cache.py "土城捷運站"`

Constraints:
- Run from project root.
- Pure stdlib + project imports. No new dependencies.
- Teaching Mode artifacts.
```

### Verification

```bash
rm -rf data/cache/*/*.json
python scripts/warm_cache.py
ls data/cache/poi/   # populated
ls data/cache/osrm/  # many files
# Now start a fresh game with 清華大學 — should be near-instant.
```

---

## Step 13 — README + Demo Dry Run

### Prompt

```
Write README.md per Spec Section 15. Then verify the project from scratch.

Deliverables:
1. README.md with: features, setup, demo scenario, architecture (brief),
   API credits, course info.
2. Verify in a fresh shell:
   - Delete .venv/
   - Follow README setup exactly
   - Play one full game
3. Fix any README errors discovered during verification.
```

### Student Ritual After Step 13

1. Have a friend (or family member) follow your README on their machine. Fix any unclear step.
2. Time yourself doing the demo: target 3–4 minutes for live demo, leaving 3–4 min for Q&A.
3. Print Section 19 (Q&A Bank) and read aloud. Mark which ones you can answer fluently.
4. Sleep before demo day.

---

## When the Agent Goes Off-Rails

- **Adds files outside the spec** → "Delete files outside Section 4 folder tree. Re-state Section 4."
- **Skips Teaching Mode** → "Re-do this step with full Section 18 Teaching Mode artifacts. Don't write any more code until they're produced."
- **Imports new packages** → "Remove the new dependency. Solve with packages in requirements.txt only."
- **Refactors files from a previous step** → "Don't modify files outside this step's scope. List what you changed and revert anything not in this step's deliverables."
- **Claims verification passed without you running it** → "I will run the verification myself. Wait."
- **Output cut off mid-step** → "Continue from where you stopped. Do not regenerate previously-completed sections."

If genuinely stuck:
- `git commit` what you have.
- Ask agent to summarize: where the project is, what's broken, what the minimal next step would be.
- Skip ahead — Step 11 (CSS) and Step 13 (README) are independent. **You can demo with Phase 1 only.**
