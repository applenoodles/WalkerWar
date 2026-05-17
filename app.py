import logging
import os

from dotenv import load_dotenv
from flask import (
    Flask, jsonify, redirect, render_template, request, session, url_for,
)

from config import DEMO_ORIGIN, TURNS
from services.game_engine import (
    GameNotFoundError,
    GeocodeFailedError,
    load_game_state,
    save_game_state,
    start_new_game,
)
from services.map_service import MapService
from services.osrm_service import OSRMService
from services.poi_service import NotEnoughPOIsError, POIService

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = Flask(__name__)
app.secret_key = os.environ.get("WALKWARS_SECRET", "dev-secret")

# Service singletons (more will be added in later steps)
poi_svc = POIService()
osrm_svc = OSRMService()
map_svc = MapService()


# ----------------------------------------------------------------------
# Public game routes
# ----------------------------------------------------------------------

@app.get("/")
def index():
    return render_template("index.html", default_origin=DEMO_ORIGIN)


@app.post("/new_game")
def new_game():
    origin_query = (request.form.get("origin") or "").strip()
    if not origin_query:
        return render_template(
            "index.html",
            default_origin=DEMO_ORIGIN,
            error="請輸入起點地名。",
        )
    try:
        gs = start_new_game(origin_query, poi_svc, osrm_svc)
    except (GeocodeFailedError, NotEnoughPOIsError) as e:
        return render_template("index.html", default_origin=origin_query, error=str(e))

    save_game_state(gs.game_id, gs)

    # Session keeps only the tiny game pointer; the full state stays on disk.
    session.clear()
    session["game_id"] = gs.game_id
    session["turn"] = gs.turn
    session["current_player"] = gs.current_player
    session.modified = True

    return redirect(url_for("game_view"))


@app.get("/game")
def game_view():
    game_id = session.get("game_id")
    if not game_id:
        return redirect(url_for("index"))
    try:
        gs = load_game_state(game_id)
    except GameNotFoundError:
        session.clear()
        return redirect(url_for("index"))
    map_html = map_svc.render_game_map(gs)
    return render_template(
        "game.html", gs=gs, total_turns=TURNS, map_html=map_html,
    )


# ----------------------------------------------------------------------
# Health & debug endpoints (kept through Phase 1; removed before final demo)
# ----------------------------------------------------------------------

@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/debug/pois")
def debug_pois():
    loc = poi_svc.geocode("清華大學")
    if not loc:
        return jsonify({"error": "geocode failed"}), 500
    try:
        pois = poi_svc.generate_pois(loc["lat"], loc["lon"])
    except NotEnoughPOIsError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify([p.to_dict() for p in pois])


@app.get("/debug/osrm")
def debug_osrm():
    loc = poi_svc.geocode("清華大學")
    if not loc:
        return jsonify({"error": "geocode failed"}), 500
    try:
        pois = poi_svc.generate_pois(loc["lat"], loc["lon"])
    except NotEnoughPOIsError as e:
        return jsonify({"error": str(e)}), 500
    if len(pois) < 2:
        return jsonify({"error": "need at least 2 POIs"}), 500
    a, b = pois[0], pois[1]
    route = osrm_svc.get_walking_route((a.lat, a.lon), (b.lat, b.lon))
    if route is None:
        return jsonify({"error": "osrm call failed"}), 500
    return jsonify({
        "from": {"name": a.name, "lat": a.lat, "lon": a.lon},
        "to":   {"name": b.name, "lat": b.lat, "lon": b.lon},
        "duration_min":     round(route["duration_min"], 2),
        "distance_m":       round(route["distance_m"], 1),
        "geometry_points":  len(route["geometry"]),
        "first_geom_point": route["geometry"][0] if route["geometry"] else None,
    })


@app.get("/debug/matrix")
def debug_matrix():
    loc = poi_svc.geocode("清華大學")
    if not loc:
        return jsonify({"error": "geocode failed"}), 500
    try:
        pois = poi_svc.generate_pois(loc["lat"], loc["lon"])
    except NotEnoughPOIsError as e:
        return jsonify({"error": str(e)}), 500
    try:
        matrix = osrm_svc.build_matrix(pois)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    sample_ids = [p.poi_id for p in pois[:3]]
    id_to_name = {p.poi_id: p.name for p in pois}
    sample = {
        id_to_name[a]: {id_to_name[b]: round(matrix[a][b], 2) for b in sample_ids}
        for a in sample_ids
    }
    sym_check = []
    for i, a in enumerate(pois[:5]):
        for b in pois[i + 1:5]:
            sym_check.append({
                "a": a.name, "b": b.name,
                "a_to_b": round(matrix[a.poi_id][b.poi_id], 2),
                "b_to_a": round(matrix[b.poi_id][a.poi_id], 2),
            })
    return jsonify({
        "n_pois": len(pois),
        "matrix_size": f"{len(matrix)} x {len(matrix)}",
        "diagonal_zero_ok": all(matrix[p.poi_id][p.poi_id] == 0 for p in pois),
        "sample_top3x3_min": sample,
        "symmetry_check_first5": sym_check,
    })


if __name__ == "__main__":
    app.run(debug=True)
