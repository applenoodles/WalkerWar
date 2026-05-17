# IMPLEMENTATION_NOTES.md

> **Read this BEFORE the spec and prompts. These notes override anything in
> `WalkWars_Project_Spec.md` or `WalkWars_Agent_Prompts.md` where they
> conflict.**
>
> Purpose: a peer-review pass on the original docs flagged a small number of
> internal contradictions and missing details that would cause real bugs.
> Rather than rewrite the spec, the fixes live here. The agent should treat
> this file as the canonical truth for the listed items.

---

## 1. Reachable / Contest / AI — Single Coherent Rule

The original spec, Step 8 prompt, and Step 9 prompt disagreed on whether the
AI can target a human-owned POI. The correct rule, used everywhere:

```python
def reachable_poi_ids(gs, player_id) -> list[str]:
    """
    Returns POI ids the player can walk to this turn.

    Rules:
      1. Walking time <= AP_PER_TURN
      2. Not owned by the player themselves
      3. For AI: a POI owned by HUMAN is included ONLY IF that POI
         was claimed by human IN THE CURRENT TURN (-> contest target).
         Human-owned POIs from previous turns are NOT reachable for AI.
      4. For HUMAN: AI-owned POIs are NEVER reachable (human moves first;
         no contest flows in that direction in MVP).
    """
    player = gs.players[player_id]
    opponent_id = "ai" if player_id == "human" else "human"
    opponent = gs.players[opponent_id]
    result = []

    for poi in gs.pois:
        # Rule 1: AP budget
        if gs.matrix[player.current_poi_id][poi.poi_id] > AP_PER_TURN:
            continue
        # Rule 2: skip own POIs
        if poi.poi_id in player.owned_poi_ids:
            continue
        # Rules 3 & 4: opponent-owned handling
        if poi.poi_id in opponent.owned_poi_ids:
            if player_id == "ai" and _was_claimed_this_turn(gs, "human", poi.poi_id):
                pass  # contest candidate, allowed
            else:
                continue
        result.append(poi.poi_id)

    return result


def _was_claimed_this_turn(gs, player_id, poi_id) -> bool:
    """True iff player_id appended a move in gs.turn that landed on poi_id."""
    for entry in reversed(gs.move_history):
        if entry["turn"] != gs.turn:
            return False
        if entry["player"] == player_id and entry["to"] == poi_id and not entry.get("skipped"):
            return True
    return False
```

**Consequence for the AI:**

`AIService.choose_move` does **not** filter the input `reachable_ids` further.
It scores every id in `reachable_ids`, including any contest candidate. A
contest candidate slightly increases the score via a higher combo multiplier
if it would complete a combo for the AI — otherwise it's scored normally and
the AI will sometimes pick it, sometimes not.

**Consequence for Step 7 prompt:**

In Step 7, contests don't exist yet (Step 9 introduces them). For Step 7, AI
will be a placeholder skip — the reachable rule above is still correct, but
the AI never actually moves so the contest branch is never taken.

---

## 2. Turn Advancement Is Owned by `GameEngine.apply_move` ONLY

`app.py` must NEVER mutate `gs.turn`, `gs.current_player_id`, or `gs.finished`
directly. Only `apply_move` does that.

```python
def apply_move(gs, player_id, target_poi_id) -> dict:
    # ... validate, capture pre-move position, move, claim/contest, history ...

    # Advance current player
    if player_id == "human":
        gs.current_player_id = "ai"
    elif player_id == "ai":
        gs.current_player_id = "human"
        gs.turn += 1
        if gs.turn > TURNS:
            gs.finished = True

    return result
```

**Step 7 placeholder for the AI's turn:** the route makes a real
`engine.apply_move(gs, "ai", gs.players["ai"].current_poi_id)` call — i.e.
the AI submits a skip. This goes through the same engine code path, so turn
advancement is identical to the real Step 8 implementation. No special
"silently skip" branch in `app.py`.

This kills off-by-one risk between steps.

---

## 3. Skip Move — Accept Both Forms

`apply_move` treats these as the same action:
- `target_poi_id == "__skip__"`
- `target_poi_id == player.current_poi_id`

```python
SKIP_SENTINEL = "__skip__"

def apply_move(gs, player_id, target_poi_id):
    player = gs.players[player_id]
    pre_move_position = player.current_poi_id

    is_skip = (target_poi_id == SKIP_SENTINEL or
               target_poi_id == player.current_poi_id)

    if is_skip:
        gs.move_history.append({
            "turn": gs.turn, "player": player_id,
            "from": pre_move_position, "to": pre_move_position,
            "time": 0.0, "skipped": True,
            "contested": False, "stolen_from": None,
        })
        _advance_turn(gs, player_id)
        return {"ok": True, "claimed": False, "contested": False,
                "stolen_from": None, "walking_time": 0.0, "reason": "skip"}

    # ... rest of normal move logic ...
```

The "End Turn" button in `game.html` submits `poi_id=__skip__`.

---

## 4. All HTTP Calls Get a Timeout

Every `requests.get` / `requests.post` to Nominatim or OSRM must pass
`timeout=15`. The `@handle_api_errors` decorator already catches
`requests.Timeout`, but the timeout itself must be set explicitly on the
call.

```python
resp = requests.get(url, params=params, headers=headers, timeout=15)
```

Also: **never cache a failed response.** Only write the cache file after
verifying:
- Nominatim: HTTP 200 AND non-empty result list
- OSRM: HTTP 200 AND `data.get("code") == "Ok"`

---

## 5. Nominatim POI Fallback — Reach the Floor of 15 POIs

The original prompt assumed 6 keywords × 8 results each would always yield
≥15 POIs. For some origins this is true; for others (notably suburban/campus
areas) it isn't. Add a fallback **inside POIService**.

In `config.py`, replace the single-keyword strategy with a list:

```python
POI_CATEGORIES = {
    "cafe": {
        "keywords": ["cafe", "coffee", "咖啡"],
        "value": 2, "emoji": "☕", "color": "#a0522d",
    },
    "restaurant": {
        "keywords": ["restaurant", "food", "餐廳"],
        "value": 2, "emoji": "🍜", "color": "#d2691e",
    },
    "park": {
        "keywords": ["park", "garden", "公園"],
        "value": 3, "emoji": "🌳", "color": "#228b22",
    },
    "station": {
        "keywords": ["station", "MRT", "捷運", "車站"],
        "value": 3, "emoji": "🚉", "color": "#4682b4",
    },
    "attraction": {
        "keywords": ["attraction", "tourist", "viewpoint", "景點"],
        "value": 5, "emoji": "⭐", "color": "#daa520",
    },
    "shop": {
        "keywords": ["shop", "convenience", "商店"],
        "value": 1, "emoji": "🛒", "color": "#808080"
    },
    "generic": {
        "keywords": ["amenity"],
        "value": 1, "emoji": "📍", "color": "#a9a9a9",
    },
}

POI_FLOOR = 15      # minimum POIs to keep the game playable
```

In `POIService.generate_pois`:

1. For each category in the order above except `generic`, try each keyword in
   order until that category contributes ≥3 POIs, or all keywords are tried.
2. Dedupe across all categories by `(osm_type, osm_id)`.
3. Cap each category at ~6.
4. If total < `POI_FLOOR`, run `generic`'s keywords as fallback and assign
   `category="generic"` (value 1) to recovered POIs.
5. If still < `POI_FLOOR`, log a clear `ERROR` and raise a custom
   `NotEnoughPOIsError`. The `/new` route catches this, flashes a friendly
   message ("找不到足夠的地點，試試別的起點"), and redirects to `/`.

**Verification for Step 2 (replaces original):** for origin `清華大學`, total
POIs ≥ 15 and span ≥ 3 categories. Log the per-category count.

---

## 6. Folium Marker Click — Use JSON Escape, Don't Assume Iframe

Folium's `m.get_root().render()` produces an inline HTML/JS payload, **not**
an iframe (unless you wrap it). The original prompt's `window.parent` is
wrong in this setup.

In `services/map_service.py`, build popup HTML like this:

```python
import json

def _popup_html(self, poi: Place, walking_time: float) -> str:
    # JSON-encode the id so quotes / unicode in poi_id can't break the JS.
    poi_id_js = json.dumps(poi.poi_id)
    name_safe = html.escape(poi.name)         # from `import html`
    cat = POI_CATEGORIES[poi.category]

    return (
        f'<div class="poi-popup">'
        f'  <div><b>{name_safe}</b> {cat["emoji"]}</div>'
        f'  <div>Category: {poi.category} (value {poi.value})</div>'
        f'  <div>Walking time: {walking_time:.1f} min</div>'
        f'  <button type="button" onclick="window.submitMove({poi_id_js})">'
        f'    Move here'
        f'  </button>'
        f'</div>'
    )
```

In `templates/game.html`, define `window.submitMove` **before** the map
renders (it's the same window, not a parent frame):

```html
<form id="move-form" method="POST" action="/move" style="display:none">
  <input type="hidden" name="poi_id" id="poi_id_input">
</form>
<script>
  window.submitMove = function(id) {
    document.getElementById('poi_id_input').value = id;
    document.getElementById('move-form').submit();
  };
</script>
<div class="map-container">
  {{ map_html|safe }}
</div>
```

Always pass `poi.name` through `html.escape()` before embedding it in popup
HTML. Names can contain quotes or `&`.

---

## 7. Session — Store Only `game_id`

Original docs alternated between "store game_id only" and "store game_id +
turn + current_player". Settle on the simpler one:

```python
# In /new, after save_game_state(gs):
session["game_id"] = gs.game_id
session.modified = True
# Do NOT also store turn or current_player.
```

```python
# In any route that needs to read game state:
gs = load_game_state(session["game_id"])    # turn, current_player, all here
```

**Q&A answer:** "We only store the game_id in the cookie. The rest of the
game state lives on disk in `data/games/{game_id}.json`. This avoids
cookie–disk sync bugs and keeps the cookie under Flask's 4KB limit."

---

## 8. `/new` Uses `engine.new_game()`, Not Inline Construction

The Step 5 prompt told `app.py` to instantiate `GameState` directly. That
breaks the "app.py thin" rule.

Correct `/new`:

```python
@app.post("/new")
def new_game_route():
    origin = request.form["origin"]
    loc = poi_svc.geocode(origin)
    if not loc:
        flash("找不到地點，試試別的起點")
        return redirect("/")
    try:
        pois = poi_svc.generate_pois(loc["lat"], loc["lon"])
    except NotEnoughPOIsError:
        flash("這個起點附近 POI 太少，試試別的")
        return redirect("/")
    matrix = osrm_svc.build_matrix(loc["lat"], loc["lon"], pois)
    gs = engine.new_game(
        origin_label=loc["display_name"],
        origin_lat=loc["lat"], origin_lon=loc["lon"],
        pois=pois, matrix=matrix,
    )
    save_game_state(gs)
    session["game_id"] = gs.game_id
    session.modified = True
    return redirect("/game")
```

`GameEngine.new_game` builds both players starting at `"ORIGIN"`, sets turn
1, current_player "human", finished False.

---

## 9. Matrix Display Wording

In `game.html` Step 5 stub, the original phrasing "matrix entries" was
ambiguous. Use:

```
POIs: {{ gs.pois|length }}
Matrix nodes: {{ gs.pois|length + 1 }} (including ORIGIN)
Walking-time pairs computed: {{ pair_count }}
```

Compute `pair_count = C(N+1, 2)` in the route.

---

## 10. AI Combo Multiplier — Heuristic vs Final Scoring

Final scoring strictly checks pairwise walking times. The AI's combo
multiplier is a coarse heuristic that ignores the time check (it's just
trying to push the AI toward useful category mixes).

State this clearly in `ai_service.py` docstring AND in the Mock Q&A:

```
# In ai_service.py:
def choose_move(self, gs, ai_player, reachable_ids):
    """
    Greedy heuristic: score = (value * combo_multiplier) / walking_time.

    combo_multiplier:
        1.5  if claiming this POI would give the AI:
                 ≥1 cafe AND ≥1 park AND ≥1 restaurant
                 (CATEGORY check only — does NOT verify the 15-min
                 pairwise time requirement of the actual scoring rule).
        1.5  if claiming this POI would bring the AI to ≥3 attractions.
        1.0  otherwise.

    The 1.5 is a deliberately coarse approximation: it's cheap to compute
    and pushes the AI toward category variety. The actual combo bonus at
    final scoring still requires pairwise walking time ≤ 15 min for the
    lifestyle combo.
    """
```

Q&A answer pattern: "The AI's combo multiplier is a heuristic — it cares
about category counts only. The final scoring rule is stricter and checks
pairwise walking times. The AI sometimes earns the multiplier but not the
final bonus; that's intentional, it's a cheap signal during gameplay."

---

## 11. Discrete Voronoi — How to Talk About It

The "weighted Voronoi territory" is a **discrete walking-time assignment**
over POI nodes, not a continuous polygon partition of the map plane. Keep
the name in the spec for memorability, but the student should answer
precisely if asked.

Q&A model answer:

> "Strictly speaking I'm not drawing polygon Voronoi cells on the map plane.
> I'm doing the discrete graph version: for each neutral POI, I find the
> player whose nearest owned POI is closest by OSRM walking time, and assign
> that POI to them. It's a weighted nearest-neighbor assignment using
> walking time as the metric — the same idea as a weighted Voronoi
> partition, restricted to the POI set."

The Concept Card in spec Section 18 should be updated with this wording.

---

## 12. Demo-Day Insurance — Concrete Checklist

The spec mentions screenshots in the final checklist. Make this concrete:

Before demo, the student must have:

1. **Pre-warmed cache** for `清華大學`:
   ```bash
   python scripts/warm_cache.py "清華大學"
   ```
2. **A pre-played game JSON** at `data/games/demo_ready.json` showing a
   completed, interesting game (territory + combos triggered). Used as
   fallback if live play has issues.
3. **Four screenshots** in `docs/screenshots/`:
   - `index.png` — home screen
   - `game.png` — mid-game with both players' POIs and reachable highlights
   - `contest.png` — move history showing a contest
   - `end.png` — final score screen with territory tinting
4. **Demo recipe** in README:
   - Start Flask server before walking into the room.
   - Open `/` in browser.
   - Submit "清華大學" — must land on `/game` in under 5 seconds (cache hot).
   - Play 2 turns live.
   - Use a separate browser tab pre-pointed at `data/games/demo_ready.json`
     to show end-game state without playing 6 full turns.

---

## 13. What This Document Does NOT Change

- The overall step order (1 through 13) is unchanged.
- The class signatures in spec Section 6 are unchanged.
- The scoring formula and combo rules in Section 11 are unchanged.
- The folder structure in Section 4 is unchanged (`scripts/` already exists
  there; it just doesn't have `__init__.py` — `scripts/` is for CLIs, not a
  Python package).

If anything in this document and the original spec conflict on items NOT
listed above, the original spec wins.
