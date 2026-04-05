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
