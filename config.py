from pathlib import Path

# API endpoints
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
OSRM_BASE = "https://router.project-osrm.org"

# Request headers
USER_AGENT = "WalkWars/1.0 (NTHU final project)"
ACCEPT_LANGUAGE = "zh-TW,en"
NOMINATIM_RATE_LIMIT_SEC = 1.05

# Pedestrian speed used to convert OSRM-reported distance into walking time.
# The public OSRM demo at router.project-osrm.org serves car-speed routing even
# on the /foot/ profile, so we ignore its duration and compute walking minutes
# from its (still accurate) routed distance. 5 km/h is the standard urban
# pedestrian pace.
WALKING_SPEED_KMH = 5.0

# Game parameters (locked for demo)
TURNS = 6
AP_PER_TURN = 15.0              # walking minutes
POI_RADIUS_M = 1500             # search bounding box, in metres
POI_TARGET_COUNT = 22           # try to land in [20, 25]
DEMO_ORIGIN = "清華大學"

# POI categories — try each keyword in order until ≥ 3 results for that category.
# IMPLEMENTATION_NOTES §5: multi-keyword lists replace the original single "keyword".
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
        "value": 1, "emoji": "🛒", "color": "#808080",
    },
    "generic": {
        "keywords": ["amenity"],
        "value": 1, "emoji": "📍", "color": "#a9a9a9",
    },
}

POI_FLOOR = 15      # if we cannot reach this count, raise NotEnoughPOIsError

# Combo bonuses
COMBO_LIFESTYLE_BONUS = 8       # ≥1 cafe + ≥1 park + ≥1 restaurant, pairwise ≤ 15 min
COMBO_LIFESTYLE_TIME = 15.0
COMBO_TOURIST_BONUS = 10        # ≥3 attractions owned
COMBO_TOURIST_COUNT = 3

# Territory bonus
TERRITORY_BONUS_PER_POI = 1

# Player display colours (Folium hex)
PLAYER_COLORS = {
    "human":   "#2c7fb8",       # blue
    "ai":      "#c0392b",       # red
    "neutral": "#7f8c8d",       # gray
}
PLAYER_INFLUENCE_TINT = {       # lighter shades for influenced neutral POIs
    "human":   "#a6cee3",
    "ai":      "#fb9a99",
    "neutral": "#bdc3c7",
}

# Cache & data directories (relative to where Flask is started)
CACHE_DIR = Path("data/cache")
GAMES_DIR = Path("data/games")
CACHE_ENABLED = True

# Flask
SECRET_KEY_ENV = "WALKWARS_SECRET"     # env var name; fallback "dev-secret"
