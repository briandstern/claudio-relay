"""
State management backed by a Railway Volume (or local directory).
All persistent state: rotation indices, last_sent date, claudio_context, wardrobe.
"""
import json
import os
from pathlib import Path

# Railway Volume mount — set DATA_DIR env var to override
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
STATE_FILE = DATA_DIR / "state.json"
CONTEXT_FILE = DATA_DIR / "claudio_context.md"
IMAGE_CACHE_DIR = DATA_DIR / "image_cache"
WARDROBE_FILE = DATA_DIR / "wardrobe.json"


def _ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _read_state() -> dict:
    _ensure_dirs()
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _write_state(s: dict):
    _ensure_dirs()
    STATE_FILE.write_text(json.dumps(s, indent=2))


def get_rotation_index(tier: str, context: str) -> int:
    return _read_state().get("rotation", {}).get(f"{tier}_{context}", 0)


def set_rotation_index(tier: str, context: str, idx: int):
    s = _read_state()
    s.setdefault("rotation", {})[f"{tier}_{context}"] = idx
    _write_state(s)


def get_last_sent() -> str:
    """Returns last sent date as YYYY-MM-DD, or empty string."""
    return _read_state().get("last_sent", "")


def set_last_sent(date_str: str):
    s = _read_state()
    s["last_sent"] = date_str
    _write_state(s)


def get_context() -> str:
    """Read claudio_context.md from volume, falling back to repo copy."""
    _ensure_dirs()
    if CONTEXT_FILE.exists():
        return CONTEXT_FILE.read_text(encoding="utf-8")
    repo_copy = Path(__file__).parent / "claudio_context.md"
    if repo_copy.exists():
        return repo_copy.read_text(encoding="utf-8")
    return ""


def get_wardrobe() -> list:
    """Return list of wardrobe items from volume."""
    _ensure_dirs()
    if WARDROBE_FILE.exists():
        try:
            return json.loads(WARDROBE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def add_wardrobe_items(items: list):
    """Append new items to wardrobe.json, skipping duplicates by name+category."""
    existing = get_wardrobe()
    existing_keys = {
        (i.get("category", "").upper(), i.get("name", "").lower())
        for i in existing
    }
    added = []
    for item in items:
        key = (item.get("category", "").upper(), item.get("name", "").lower())
        if key not in existing_keys:
            existing.append(item)
            existing_keys.add(key)
            added.append(item)
    WARDROBE_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return added


def get_recent_outfits(n: int = 14) -> list:
    """Return last n outfit summaries (for deduplication in compose prompt)."""
    return _read_state().get("recent_outfits", [])[-n:]


def add_recent_outfit(name: str, pieces_summary: str):
    from datetime import datetime
    s = _read_state()
    recent = s.get("recent_outfits", [])
    recent.append({
        "name": name,
        "pieces_summary": pieces_summary,
        "date": datetime.now().strftime("%Y-%m-%d"),
    })
    s["recent_outfits"] = recent[-30:]
    _write_state(s)


def store_outfit_for_rating(outfit_hash: str, outfit_name: str, pieces_summary: str):
    """Store outfit metadata keyed by hash so ratings can reference it later."""
    s = _read_state()
    store = s.get("outfit_rating_store", {})
    store[outfit_hash] = {"outfit_name": outfit_name, "pieces_summary": pieces_summary}
    # Keep last 30 entries
    if len(store) > 30:
        for k in list(store.keys())[:-30]:
            del store[k]
    s["outfit_rating_store"] = store
    _write_state(s)


def add_outfit_rating(outfit_hash: str, rating: str):
    """Record a thumbs up/down for an outfit. rating: 'up' or 'down'."""
    from datetime import datetime
    s = _read_state()
    store = s.get("outfit_rating_store", {})
    info = store.get(outfit_hash, {})
    ratings = s.get("outfit_ratings", [])
    for r in ratings:
        if r["outfit_hash"] == outfit_hash:
            r["rating"] = rating
            _write_state(s)
            return
    ratings.append({
        "outfit_hash": outfit_hash,
        "outfit_name": info.get("outfit_name", ""),
        "pieces_summary": info.get("pieces_summary", ""),
        "rating": rating,
        "date": datetime.now().strftime("%Y-%m-%d"),
    })
    s["outfit_ratings"] = ratings[-50:]
    _write_state(s)


def get_outfit_ratings(n: int = 20) -> list:
    return _read_state().get("outfit_ratings", [])[-n:]


def append_context(text: str):
    """Append a feedback entry to claudio_context.md on the volume."""
    _ensure_dirs()
    # Seed from repo copy if volume copy doesn't exist yet
    if not CONTEXT_FILE.exists():
        repo_copy = Path(__file__).parent / "claudio_context.md"
        if repo_copy.exists():
            CONTEXT_FILE.write_text(repo_copy.read_text(encoding="utf-8"), encoding="utf-8")

    raw = CONTEXT_FILE.read_text(encoding="utf-8") if CONTEXT_FILE.exists() else ""

    from datetime import datetime
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_text = text.replace("|", "-").replace("\n", " ").strip()
    new_row = f"| {date_str} | {safe_text} | Brian via Telegram |"

    if "## Refinement Log" in raw:
        raw = raw.rstrip() + f"\n{new_row}\n"
    else:
        raw += (
            "\n\n## Refinement Log\n\n"
            "| Date | Change | Reason |\n|------|--------|--------|\n"
            f"{new_row}\n"
        )
    CONTEXT_FILE.write_text(raw, encoding="utf-8")
