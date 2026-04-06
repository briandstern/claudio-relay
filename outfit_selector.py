"""
Weather fetching, tier/context logic, and outfit selection with rotation.
"""
import json
from datetime import datetime
from pathlib import Path

import httpx

import state

WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=40.8268&longitude=-73.6982"
    "&current=temperature_2m,apparent_temperature,weathercode,windspeed_10m"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode"
    "&temperature_unit=fahrenheit&wind_speed_unit=mph"
    "&timezone=America/New_York&forecast_days=1"
)

OUTFIT_DB_PATH = Path(__file__).parent / "outfit_db.json"

_WEATHER_CODES = {
    0: "Clear", 1: "Mostly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy", 48: "Foggy", 51: "Light Drizzle", 53: "Drizzle",
    55: "Heavy Drizzle", 61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
    71: "Light Snow", 73: "Snow", 75: "Heavy Snow",
    80: "Showers", 81: "Showers", 82: "Heavy Showers", 95: "Thunderstorm",
}


def fetch_weather() -> dict:
    with httpx.Client(timeout=15) as client:
        r = client.get(WEATHER_URL)
        r.raise_for_status()
        data = r.json()
    current = data.get("current", {})
    daily = data.get("daily", {})
    return {
        "feels_like_f": current.get("apparent_temperature"),
        "temp_f": current.get("temperature_2m"),
        "weathercode": current.get("weathercode", 0),
        "windspeed_mph": current.get("windspeed_10m"),
        "precip_prob": (daily.get("precipitation_probability_max") or [None])[0],
        "temp_max": (daily.get("temperature_2m_max") or [None])[0],
        "temp_min": (daily.get("temperature_2m_min") or [None])[0],
    }


def get_tier(feels_like_f: float) -> str:
    if feels_like_f < 25:
        return "frigid"
    elif feels_like_f < 43:
        return "cold"
    elif feels_like_f < 59:
        return "cool"
    elif feels_like_f < 73:
        return "warm"
    else:
        return "hot"


def get_day_context(dt: datetime = None) -> str:
    if dt is None:
        dt = datetime.now()
    return "office" if dt.weekday() < 5 else "weekend"


def load_outfit_db() -> dict:
    return json.loads(OUTFIT_DB_PATH.read_text(encoding="utf-8"))


def select_outfit(tier: str, context: str) -> dict:
    """Select the next outfit using rotation state. Falls back to adjacent tier if needed."""
    db = load_outfit_db()
    outfits = db.get(tier, {}).get(context, [])

    if not outfits:
        _fallbacks = {
            "frigid": "cold", "cold": "cool",
            "cool": "warm", "warm": "cool", "hot": "warm",
        }
        fallback_tier = _fallbacks.get(tier, "cool")
        outfits = db.get(fallback_tier, {}).get(context, [])
        if outfits:
            tier = fallback_tier

    if not outfits:
        raise ValueError(f"No outfits found for tier={tier} context={context}")

    idx = state.get_rotation_index(tier, context) % len(outfits)
    return outfits[idx]


def advance_rotation(tier: str, context: str):
    """Advance rotation index after a successful send."""
    db = load_outfit_db()
    outfits = db.get(tier, {}).get(context, [])
    if not outfits:
        return
    current = state.get_rotation_index(tier, context)
    state.set_rotation_index(tier, context, (current + 1) % len(outfits))


_WET_CODES = {51, 53, 55, 61, 63, 65, 80, 81, 82, 95}
_RAIN_SENSITIVE = ["suede", "canvas", "espadrille", "boat shoe", "duck boot"]


def is_wet_day(weather: dict) -> bool:
    precip = weather.get("precip_prob") or 0
    code = weather.get("weathercode", 0)
    return precip >= 50 or code in _WET_CODES


def apply_weather_overrides(outfit: dict, weather: dict) -> dict:
    """
    Swap rain-sensitive shoes (suede, canvas) for leather boots when rain is likely.
    Prepends a note to the stylist tip when a swap occurs.
    Returns a modified deep copy.
    """
    import copy
    if not is_wet_day(weather):
        return outfit

    outfit = copy.deepcopy(outfit)
    swapped = []
    for piece in outfit.get("pieces", []):
        if piece.get("category") != "SHOES":
            continue
        name_lower = piece.get("name", "").lower()
        if any(s in name_lower for s in _RAIN_SENSITIVE):
            swapped.append(piece["name"])
            piece["name"] = "Cognac Leather Chelsea Boots"
            piece["brand"] = "Thursday Boot Co."
            piece["color"] = "#8B5E3C"
            piece["color_name"] = "cognac"
            piece["image_url"] = None

    if swapped:
        swap_note = f"Rain today — swapped {swapped[0]} for leather boots. "
        outfit["stylist_note"] = swap_note + outfit.get("stylist_note", "")

    return outfit


def suggest_accessories(outfit: dict, weather: dict) -> dict:
    """
    Add contextually appropriate accessories that are missing from the outfit:
    - Belt: when trousers/chinos present, shirt is tucked, no belt, no jeans
    - Scarf: when cold/frigid, no scarf already, outerwear present
    Returns a modified deep copy.
    """
    import copy
    outfit = copy.deepcopy(outfit)
    pieces = outfit["pieces"]
    categories = {p.get("category", "").upper() for p in pieces}
    names_lower = " ".join(p.get("name", "").lower() for p in pieces)

    # ── Belt ──────────────────────────────────────────────────────────────
    has_trousers = "PANTS" in categories and "jean" not in names_lower
    has_tucked_layer = "SHIRT" in categories or any(
        p.get("category") == "LAYER" and "turtleneck" not in p.get("name", "").lower()
        for p in pieces
    )
    has_belt = "BELT" in categories or "belt" in names_lower

    if has_trousers and has_tucked_layer and not has_belt:
        # Match belt color to shoes
        shoe_color, shoe_color_name = "#8B5E3C", "cognac"
        for p in pieces:
            if p.get("category") == "SHOES":
                shoe_color = p.get("color", shoe_color)
                shoe_color_name = p.get("color_name", shoe_color_name)
                break
        pieces.append({
            "category": "BELT",
            "name": f"{shoe_color_name.title()} Leather Belt",
            "brand": "Allen Edmonds",
            "color": shoe_color,
            "color_name": shoe_color_name,
            "image_url": None,
        })

    # ── Scarf ─────────────────────────────────────────────────────────────
    feels = weather.get("feels_like_f") or 50
    has_scarf = "scarf" in names_lower
    if feels < 43 and not has_scarf and "OUTERWEAR" in categories:
        pieces.append({
            "category": "ACCESSORIES",
            "name": "Grey Wool Scarf",
            "brand": "Alex Mill",
            "color": "#8A8A8A",
            "color_name": "grey",
            "image_url": None,
        })

    outfit["pieces"] = pieces
    return outfit


def weather_description(weather: dict) -> str:
    """Short human-readable weather string for the card header."""
    feels = weather.get("feels_like_f")
    code = weather.get("weathercode", 0)
    precip = weather.get("precip_prob") or 0

    condition = _WEATHER_CODES.get(code, "Cloudy")
    if precip >= 50:
        condition += " · Rain likely"

    temp_str = f"{int(feels)}°F" if feels is not None else "—"
    return f"{temp_str} · {condition}"
