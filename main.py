import hashlib
import os
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import state
import telegram_client
from card_generator import generate_card
from outfit_selector import (
    advance_rotation,
    apply_weather_overrides,
    compose_outfit,
    fetch_weather,
    get_day_context,
    get_tier,
    select_outfit,
    suggest_accessories,
)

API_SECRET = os.environ.get("API_SECRET", "")
SERVICE_URL = os.environ.get("SERVICE_URL", "https://telegram-relay-production.up.railway.app")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    telegram_client.register_webhook(SERVICE_URL)
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def _auth(authorization: str | None):
    if not API_SECRET or authorization != f"Bearer {API_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")


class GenerateRequest(BaseModel):
    weather: dict | None = None
    outfit: dict | None = None
    context: str = "office"
    caption: str = ""
    force: bool = False


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/generate-and-send")
def generate_and_send(request: GenerateRequest, authorization: str = Header(None)):
    """
    Fetch weather + select outfit (if not provided), generate card, send to Telegram.
    Sync so FastAPI threads it — keeps the event loop free during ~30s generation.
    Retries once before alerting Brian via Telegram.
    """
    _auth(authorization)

    weather = request.weather
    outfit = request.outfit
    context = request.context
    used_static_db = False

    if weather is None:
        weather = fetch_weather()
    if outfit is None:
        context = get_day_context()
        wardrobe = state.get_wardrobe()
        if wardrobe:
            outfit = compose_outfit(weather, context)
        else:
            tier = get_tier(weather["feels_like_f"])
            outfit = select_outfit(tier, context)
            used_static_db = True

    # Idempotency: skip if a card was already sent today (bypass with force=True)
    today = datetime.now().strftime("%Y-%m-%d")
    if not request.force and state.get_last_sent() == today:
        return {"ok": True, "skipped": True, "reason": "already sent today"}

    # Apply weather overrides (swap suede → leather when rain) and fill in accessories
    outfit = apply_weather_overrides(outfit, weather)
    outfit = suggest_accessories(outfit, weather)

    tier = get_tier(weather["feels_like_f"])

    # Build outfit hash + summary for rating buttons and history
    pieces_summary = ", ".join(p.get("name", "") for p in outfit.get("pieces", []))
    outfit_hash = hashlib.sha256(pieces_summary.encode()).hexdigest()[:16]
    state.store_outfit_for_rating(outfit_hash, outfit.get("name", ""), pieces_summary)

    last_error = None

    for attempt in range(1, 3):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name

            generate_card(weather, outfit, tmp_path, context)

            with open(tmp_path, "rb") as f:
                image_bytes = f.read()

            result = telegram_client.send_card(image_bytes, request.caption, outfit_hash=outfit_hash)

            if used_static_db:
                advance_rotation(tier, context)
            state.add_recent_outfit(outfit.get("name", ""), pieces_summary)
            state.set_last_sent(datetime.now().strftime("%Y-%m-%d"))

            return {"ok": True, "message_id": result["result"]["message_id"]}

        except Exception as e:
            last_error = e
            print(f"[generate-and-send] attempt {attempt} failed: {e}")

        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    telegram_client.send_alert(f"Card generation failed after 2 attempts: {last_error}")
    raise HTTPException(status_code=500, detail=str(last_error))


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram messages, photos, and inline button callbacks from Brian."""
    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    # ── Inline button callback (👍 / 👎 ratings) ──────────────────────────
    callback = update.get("callback_query")
    if callback:
        query_id = callback.get("id")
        data = callback.get("data", "")
        chat_id = str(callback.get("from", {}).get("id", ""))
        if chat_id == str(TELEGRAM_CHAT_ID):
            parts = data.split("_")
            if len(parts) == 3 and parts[0] == "rate":
                outfit_hash, direction = parts[1], parts[2]
                state.add_outfit_rating(outfit_hash, direction)
                emoji = "👍 Noted." if direction == "up" else "👎 Noted — won't repeat that combination."
                telegram_client.answer_callback_query(query_id, emoji)
            else:
                telegram_client.answer_callback_query(query_id)
        else:
            telegram_client.answer_callback_query(query_id)
        return {"ok": True}

    message = update.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))

    if chat_id != str(TELEGRAM_CHAT_ID):
        return {"ok": True}

    # ── Photo: catalog clothing items ──────────────────────────────────────
    if message.get("photo"):
        import wardrobe_catalog
        try:
            file_id = message["photo"][-1]["file_id"]
            image_bytes = telegram_client.download_photo(file_id)
            items = wardrobe_catalog.extract_items_from_photo(image_bytes)
            added = state.add_wardrobe_items(items)
            confirmation = wardrobe_catalog.format_confirmation(added)
            telegram_client.send_message(confirmation)
        except Exception as e:
            print(f"[wardrobe] photo catalog failed: {e}")
            telegram_client.send_message(f"Couldn't catalog that photo: {e}")
        return {"ok": True}

    # ── Text: style feedback → context ────────────────────────────────────
    text = message.get("text", "").strip()
    if not text or text.startswith("/"):
        return {"ok": True}

    state.append_context(text)
    telegram_client.send_message("Got it. Adding to context.")
    return {"ok": True}


@app.post("/update-context")
async def update_context(request: Request, authorization: str = Header(None)):
    """Append text to claudio_context.md on the volume (authenticated)."""
    _auth(authorization)
    body = await request.json()
    text = body.get("text", "").strip()
    if text:
        state.append_context(text)
    return {"ok": True}
