"""
State management backed by a Railway Volume (or local directory).
All persistent state: rotation indices, last_sent date, claudio_context.
"""
import json
import os
from pathlib import Path

# Railway Volume mount — set DATA_DIR env var to override
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
STATE_FILE = DATA_DIR / "state.json"
CONTEXT_FILE = DATA_DIR / "claudio_context.md"
IMAGE_CACHE_DIR = DATA_DIR / "image_cache"


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
