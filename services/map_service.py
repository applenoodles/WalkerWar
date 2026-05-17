import logging

import folium

from models.game_state import GameState

logger = logging.getLogger(__name__)


class MapService:
    """Renders the Folium / Leaflet map for the game screen."""

    def render_game_map(self, gs: GameState) -> str:
        """
        Build an interactive Leaflet map showing every POI + the origin and
        return its full HTML string (ready for `{{ map_html|safe }}` in Jinja).

        Step 6 has no interactivity yet:
          - Origin: black flag icon, popup says 「起點」.
          - All other POIs: gray info icon, popup shows name / category / value.
          - Tooltip on hover = POI name (helps when many markers overlap).

        Step 7+ will rebuild this with player-colored markers and click handlers.
        Per CLAUDE.md we use `m.get_root().render()`; never use `.save()`.
        """
        m = folium.Map(
            location=[gs.origin_lat, gs.origin_lon],
            zoom_start=15,                 # street-level — fits a 1.5 km radius
            tiles="OpenStreetMap",
            control_scale=True,
            width="100%",
            height="500px",
        )

        for p in gs.pois:
            is_origin = (p.poi_id == "origin")
            if is_origin:
                icon = folium.Icon(color="black", icon="flag")
                popup_html = f"<b>🚩 {p.name}</b><br>起點"
                tooltip = f"🚩 {p.name}（起點）"
            else:
                icon = folium.Icon(color="gray", icon="info-sign")
                popup_html = (
                    f"<b>{p.name}</b>"
                    f"<br>類別：{p.category}"
                    f"<br>分數：{p.value}"
                )
                tooltip = p.name

            folium.Marker(
                location=[p.lat, p.lon],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=tooltip,
                icon=icon,
            ).add_to(m)

        logger.info(
            "Map rendered for game %s with %d markers (incl. origin)",
            gs.game_id, len(gs.pois),
        )
        return m.get_root().render()
