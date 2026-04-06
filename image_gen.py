"""
Image generation with Railway Volume caching.
- Product images: DALL-E-3 (cached by piece description hash)
- Portrait: Google Imagen 3 primary, DALL-E-3 fallback (cached by outfit hash)
"""
import hashlib
import os
from pathlib import Path

import httpx
from openai import OpenAI

try:
    from google import genai as _ggenai
    from google.genai import types as _gtypes
except ImportError:
    _ggenai = None

import state


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:24]


def _cache_path(key: str) -> Path:
    state._ensure_dirs()
    return state.IMAGE_CACHE_DIR / f"{key}.png"


def _openai_client() -> OpenAI:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _fetch_url(url: str) -> bytes:
    with httpx.Client(timeout=30) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content


# ── Color helpers ──────────────────────────────────────────────────────────

_COLOR_MAP = {
    (0, 0, 128): "navy", (0, 0, 139): "dark blue", (0, 0, 205): "medium blue",
    (0, 0, 255): "blue", (70, 130, 180): "steel blue",
    (0, 128, 0): "green", (107, 142, 35): "olive", (128, 128, 0): "dark olive",
    (0, 128, 128): "teal", (64, 64, 64): "dark grey", (105, 105, 105): "dim grey",
    (128, 128, 128): "grey", (169, 169, 169): "light grey", (192, 192, 192): "silver",
    (255, 255, 255): "white", (0, 0, 0): "black", (139, 69, 19): "saddle brown",
    (160, 82, 45): "sienna", (210, 105, 30): "chocolate",
    (245, 245, 220): "beige", (245, 222, 179): "wheat", (210, 180, 140): "tan",
    (128, 0, 0): "maroon", (139, 0, 0): "dark red", (165, 42, 42): "brown",
    (255, 0, 0): "red", (255, 140, 0): "dark orange", (255, 165, 0): "orange",
    (107, 124, 77): "olive green", (72, 61, 139): "dark slate blue",
    (75, 0, 130): "indigo", (255, 215, 0): "gold",
}


def _hex_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def color_name(hex_c: str) -> str:
    if not hex_c or not hex_c.startswith("#"):
        return "neutral"
    try:
        rgb = _hex_rgb(hex_c)
        best = min(_COLOR_MAP, key=lambda c: sum((a - b) ** 2 for a, b in zip(c, rgb)))
        return _COLOR_MAP[best]
    except Exception:
        return "neutral"


# ── Product images ─────────────────────────────────────────────────────────

def gen_product_image(piece: dict) -> bytes:
    """Generate (or load cached) product image for a clothing piece."""
    col = piece.get("color_name") or color_name(piece.get("color", "#888888"))
    mat = piece.get("material", "")
    name = piece.get("name", "clothing item")
    brand = piece.get("brand", "")
    mat_str = f"{mat} " if mat else ""
    brand_str = f" by {brand}" if brand else ""

    prompt = (
        f"Simple product photo of a {col} {mat_str}{name}{brand_str}. "
        "Shown alone on a clean pure white background, like an online store listing. "
        "Just the single garment by itself — nothing else in the image. "
        "No props, no other items, no knolling, no flat-lay, no hands, no people. "
        "Natural fabric texture, true-to-life color. Professional e-commerce photo."
    )

    cached = _cache_path(_cache_key(prompt))
    if cached.exists():
        print(f"[image_gen] cache hit: {piece.get('name')}")
        return cached.read_bytes()

    client = _openai_client()
    resp = client.images.generate(
        model="dall-e-3", prompt=prompt,
        size="1024x1024", quality="standard", n=1,
    )
    data = _fetch_url(resp.data[0].url)
    cached.write_bytes(data)
    print(f"[image_gen] generated product image: {piece.get('name')}")
    return data


# ── Portrait ───────────────────────────────────────────────────────────────

def gen_portrait(outfit: dict, context: str, weather: dict) -> bytes:
    """Generate (or load cached) full-body portrait for the outfit."""
    pieces = outfit.get("pieces", [])
    descs = []
    for p in pieces:
        col = p.get("color_name") or color_name(p.get("color", "#888888"))
        name = p.get("name", "")
        category = p.get("category", "").lower()
        brand = p.get("brand", "")
        entry = f"{col} {name}".strip()
        if category:
            entry = f"{entry} (worn as {category})"
        if brand:
            entry += f" by {brand}"
        descs.append(entry)
    outfit_str = ", ".join(descs) if descs else "casual outfit"

    prompt = (
        "Full standing body shot of ONE man. SINGLE PERSON ONLY. "
        "CRITICAL: Show the COMPLETE figure — top of head at very top of frame, "
        "shoes and feet FULLY VISIBLE at very bottom of frame. "
        "DO NOT CROP. Nothing cut off. Full length head to toe. "
        f"He is wearing exactly these items: {outfit_str}. "
        "Render each garment accurately — the specific item type, color, and layering order matter. "
        "Standing upright, hands relaxed at sides or in pockets, "
        "slight confident smile, facing camera. "
        "Clean off-white studio background. "
        "Short brown hair, green eyes, lean athletic build, 6'2\", mid-30s. "
        "Soft even studio lighting. Photorealistic, full-length fashion catalog photo. "
        "Vertical 2:3 format. Wide enough frame to show complete figure head to toe."
    )

    cached = _cache_path(f"portrait_{_cache_key(outfit_str + context)}")
    if cached.exists():
        print(f"[image_gen] portrait cache hit: {outfit.get('name')}")
        return cached.read_bytes()

    data = _try_imagen(prompt) or _try_dalle_portrait(prompt)
    if data:
        cached.write_bytes(data)
        print(f"[image_gen] portrait generated: {outfit.get('name')}")
    return data


def _try_imagen(prompt: str) -> bytes | None:
    if _ggenai is None:
        return None
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        client = _ggenai.Client(api_key=api_key)
        result = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=prompt,
            config=_gtypes.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="2:3",
                safety_filter_level="block_only_high",
                person_generation="allow_adult",
            ),
        )
        if result.generated_images:
            return result.generated_images[0].image.image_bytes
    except Exception as e:
        print(f"[imagen] failed: {e}, falling back to DALL-E")
    return None


def _try_dalle_portrait(prompt: str) -> bytes | None:
    try:
        client = _openai_client()
        resp = client.images.generate(
            model="dall-e-3", prompt=prompt,
            size="1024x1792", quality="hd", n=1,
        )
        return _fetch_url(resp.data[0].url)
    except Exception as e:
        print(f"[dalle-portrait] failed: {e}")
    return None
