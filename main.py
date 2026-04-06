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

    if weather is None:
        weather = fetch_weather()
    if outfit is None:
        context = get_day_context()
        tier = get_tier(weather["feels_like_f"])
        outfit = select_outfit(tier, context)

    # Idempotency: skip if a card was already sent today (bypass with force=True)
    today = datetime.now().strftime("%Y-%m-%d")
    if not request.force and state.get_last_sent() == today:
        return {"ok": True, "skipped": True, "reason": "already sent today"}

    # Apply weather overrides (swap suede → leather when rain) and fill in accessories
    outfit = apply_weather_overrides(outfit, weather)
    outfit = suggest_accessories(outfit, weather)

    tier = get_tier(weather["feels_like_f"])
    last_error = None

    for attempt in range(1, 3):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name

            generate_card(weather, outfit, tmp_path, context)

            with open(tmp_path, "rb") as f:
                image_bytes = f.read()

            result = telegram_client.send_card(image_bytes, request.caption)

            advance_rotation(tier, context)
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
    """Receive Telegram messages from Brian and append to context on the volume."""
    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    message = update.get("message", {})
    text = message.get("text", "").strip()
    chat_id = str(message.get("chat", {}).get("id", ""))

    if not text or chat_id != str(TELEGRAM_CHAT_ID) or text.startswith("/"):
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
