"""
Wardrobe cataloging via GPT-4 Vision.
Extracts structured clothing items from photos sent via Telegram.
"""
import base64
import json
import os
import re
from datetime import datetime

from openai import OpenAI

import state

_SYSTEM_PROMPT = """You are a wardrobe cataloging assistant.
The user will send a photo of one or more clothing items.
Extract every distinct clothing item visible and return a JSON array.

For each item, include:
- category: one of OUTERWEAR, TOPS, PANTS, SHOES, ACCESSORIES, BELT
- name: specific descriptive name (e.g. "Navy Cashmere Crewneck Sweater", "Olive Pleated Trousers")
- color_name: simple color word (navy, olive, black, white, grey, brown, camel, cream, burgundy, charcoal, etc.)
- color: best-guess hex code for that color
- material: fabric if visible or inferrable (cashmere, merino wool, cotton, suede, leather, linen, etc.) — omit if unclear
- brand: brand name if visible on label or tag — omit if not visible
- condition: "good" or "worn" based on visible wear

Return ONLY a valid JSON array, no markdown, no explanation. Example:
[
  {"category": "TOPS", "name": "Navy Cashmere Crewneck Sweater", "color_name": "navy", "color": "#1B2A4A", "material": "cashmere", "brand": "Polo Ralph Lauren", "condition": "good"},
  {"category": "PANTS", "name": "Olive Pleated Trousers", "color_name": "olive", "color": "#6B7C4A", "material": "wool", "condition": "good"}
]"""


def extract_items_from_photo(image_bytes: bytes) -> list[dict]:
    """
    Send photo to GPT-4 Vision, extract all clothing items as structured dicts.
    Returns list of item dicts ready for wardrobe.json.
    """
    b64 = base64.b64encode(image_bytes).decode()
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                    {"type": "text", "text": "Catalog all clothing items in this photo."},
                ],
            },
        ],
        max_tokens=1000,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    items = json.loads(raw)

    # Stamp each item with today's date
    today = datetime.now().strftime("%Y-%m-%d")
    for item in items:
        item.setdefault("added", today)

    return items


def format_confirmation(added: list[dict]) -> str:
    """Build a Telegram confirmation message for newly added wardrobe items."""
    if not added:
        return "No new items found (everything in the photo was already in your wardrobe)."

    lines = [f"Added {len(added)} item{'s' if len(added) != 1 else ''} to your wardrobe:\n"]
    for item in added:
        mat = f" · {item['material']}" if item.get("material") else ""
        brand = f" ({item['brand']})" if item.get("brand") else ""
        lines.append(f"• {item['category']}: {item['name']}{brand}{mat}")

    lines.append("\nReply to correct anything.")
    return "\n".join(lines)
