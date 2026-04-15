"""
Weather fetching, tier/context logic, outfit selection with rotation,
and AI-composed outfit generation from wardrobe.
"""
import json
import os
import re
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
    """Select today's outfit using date-based rotation — works without persistent Volume state.
    Each tier+context pair has a unique offset so they don't all cycle in lockstep.
    Falls back to adjacent tier if needed."""
    import hashlib as _hl
    from datetime import date as _date

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

    # Date-based rotation: advances every day without needing persistent Volume state.
    # Uses (day_number + tier_offset) % outfit_count so:
    #   - Different outfit every calendar day for the same tier/context
    #   - Different tiers/contexts don't land on the same index simultaneously
    day_num = (_date.today() - _date(2026, 1, 1)).days
    tier_offset = int(_hl.md5(f"{tier}:{context}".encode()).hexdigest()[:4], 16)
    idx = (day_num + tier_offset) % len(outfits)
    return outfits[idx]


def advance_rotation(tier: str, context: str):
    """Kept for compatibility — date-based selection no longer relies on this,
    but state is still updated for diagnostics."""
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

    # Cold + loafers: remind about socks
    feels = weather.get("feels_like_f") or 50
    if feels < 50 and not is_wet_day(weather):
        for piece in outfit.get("pieces", []):
            if piece.get("category") == "SHOES" and "loafer" in piece.get("name", "").lower():
                sock_note = "Cold enough for socks — charcoal or navy dress socks with the loafers. "
                outfit["stylist_note"] = sock_note + outfit.get("stylist_note", "")
                break

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


def compose_outfit(weather: dict, context: str) -> dict:
    """
    Use GPT-4o to compose an outfit from Brian's actual wardrobe.
    Includes style profile, weather, recent outfit history, and ratings feedback.
    Falls back to select_outfit() if wardrobe is empty.
    """
    from openai import OpenAI

    wardrobe = state.get_wardrobe()
    if not wardrobe:
        tier = get_tier(weather["feels_like_f"])
        return select_outfit(tier, context)

    style_ctx = state.get_context()
    recent = state.get_recent_outfits(14)
    ratings = state.get_outfit_ratings(20)

    tier = get_tier(weather.get("feels_like_f", 55))
    weather_str = weather_description(weather)
    context_label = (
        "office — fintech NYC (Clear Street, 4 WTC), business casual elevated"
        if context == "office"
        else "weekend — fashionable dad, Port Washington NY, relaxed but intentional"
    )

    recent_block = ""
    if recent:
        names = [r["name"] for r in recent[-7:] if r.get("name")]
        if names:
            recent_block = "\nRECENT OUTFITS — do not repeat these exact combinations:\n" + "\n".join(f"- {n}" for n in names)

    liked = [r for r in ratings if r.get("rating") == "up"]
    disliked = [r for r in ratings if r.get("rating") == "down"]
    liked_block = ""
    disliked_block = ""
    if liked:
        liked_block = "\nOUTFITS BRIAN LIKED — lean toward similar combinations:\n" + "\n".join(f"- {r['pieces_summary']}" for r in liked[-5:])
    if disliked:
        disliked_block = "\nOUTFITS BRIAN DISLIKED — avoid these combinations:\n" + "\n".join(f"- {r['pieces_summary']}" for r in disliked[-5:])

    prompt = f"""You are Claudio, Brian's personal stylist. Compose today's outfit.

BRIAN'S STYLE PROFILE:
{style_ctx[:3500]}

TODAY:
- Weather: {weather_str}
- Temperature tier: {tier}
- Context: {context_label}
{recent_block}{liked_block}{disliked_block}

BRIAN'S WARDROBE (use ONLY items from this list — exact names):
{json.dumps(wardrobe, indent=2)}

Compose a complete outfit. Rules:
- Every piece must come from the wardrobe list above
- Match the temperature tier and context
- 3+ distinct textures minimum
- Proper layering for the temperature
- Follow all style rules in the profile strictly

Return a JSON object with exactly this structure — no markdown, no extra text:
{{
  "name": "Short evocative name for the look (2-4 words)",
  "pieces": [
    {{
      "category": "OUTERWEAR|TOPS|LAYER|PANTS|SHOES|ACCESSORIES|BELT",
      "name": "exact item name from wardrobe",
      "color": "#hexcode",
      "color_name": "color word",
      "material": "material if known",
      "brand": "brand if known"
    }}
  ],
  "stylist_note": "2-3 sentences: why this outfit works today. Specific to weather and context. Confident, direct tone — like an Italian stylist who knows Brian well."
}}"""

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1200,
        temperature=0.8,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


def weather_description(weather: dict) -> str:
    """Human-readable weather string for the card header."""
    temp = weather.get("temp_f")
    feels = weather.get("feels_like_f")
    temp_max = weather.get("temp_max")
    temp_min = weather.get("temp_min")
    code = weather.get("weathercode", 0)
    precip = weather.get("precip_prob") or 0

    condition = _WEATHER_CODES.get(code, "Cloudy")
    if precip >= 50:
        condition += " · Rain likely"

    # Show actual temp as primary, feels-like only when meaningfully different
    if temp is not None:
        temp_str = f"{int(temp)}°F"
        if feels is not None and abs(temp - feels) >= 5:
            temp_str += f" (feels {int(feels)}°F)"
    else:
        temp_str = "—"

    # High / low
    range_str = ""
    if temp_max is not None and temp_min is not None:
        range_str = f" · H {int(temp_max)}° L {int(temp_min)}°"

    return f"{temp_str} · {condition}{range_str}"
