from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
import httpx, base64, os, tempfile
from datetime import datetime
from pathlib import Path
from card_generator import generate_card, _CTX_CACHE

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")
API_SECRET         = os.environ.get("API_SECRET")
GITHUB_TOKEN       = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO        = "briandstern/claudio-relay"
CONTEXT_FILENAME   = "claudio_context.md"
CONTEXT_PATH       = Path(__file__).parent / CONTEXT_FILENAME
SERVICE_URL        = os.environ.get("SERVICE_URL", "https://telegram-relay-production.up.railway.app")

# ── Startup / Lifespan ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Register Telegram webhook on startup."""
    webhook_url = f"{SERVICE_URL}/telegram-webhook"
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook",
                json={"url": webhook_url, "allowed_updates": ["message"]},
                timeout=10,
            )
            print(f"[webhook] registered: {r.json()}")
        except Exception as e:
            print(f"[webhook] registration failed: {e}")
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# ── Pydantic models ──────────────────────────────────────────────────────────

class SendCardRequest(BaseModel):
    image_base64: str
    caption: str = ""

class GenerateAndSendRequest(BaseModel):
    weather: dict
    outfit:  dict
    context: str = "office"
    caption: str = ""

# ── Helpers ──────────────────────────────────────────────────────────────────

def _auth(authorization: str):
    if not API_SECRET or authorization != f"Bearer {API_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

def _telegram_send(image_bytes: bytes, caption: str):
    """Synchronously send an image as a document to Telegram (no compression)."""
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
            files={"document": ("card.png", image_bytes, "image/png")},
        )
    result = resp.json()
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=str(result))
    return result

async def _push_context_to_github(content: str):
    """Push updated claudio_context.md back to GitHub for persistence."""
    if not GITHUB_TOKEN:
        print("[github] GITHUB_TOKEN not set — skipping push")
        return
    b64 = base64.b64encode(content.encode("utf-8")).decode()
    async with httpx.AsyncClient() as client:
        # Fetch current blob SHA
        r = await client.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CONTEXT_FILENAME}",
            headers={"Authorization": f"token {GITHUB_TOKEN}"},
            timeout=15,
        )
        sha = r.json().get("sha", "")
        body = {
            "message": f"context: Brian feedback via Telegram — {datetime.now().strftime('%Y-%m-%d')}",
            "content": b64,
        }
        if sha:
            body["sha"] = sha
        await client.put(
            f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CONTEXT_FILENAME}",
            headers={"Authorization": f"token {GITHUB_TOKEN}", "Content-Type": "application/json"},
            json=body,
            timeout=15,
        )
        print("[github] claudio_context.md pushed")

async def _append_feedback(text: str):
    """Append a Telegram message to claudio_context.md locally + on GitHub."""
    raw = CONTEXT_PATH.read_text(encoding="utf-8") if CONTEXT_PATH.exists() else ""
    date_str  = datetime.now().strftime("%Y-%m-%d")
    safe_text = text.replace("|", "-").replace("\n", " ").strip()
    new_row   = f"| {date_str} | {safe_text} | Brian via Telegram |"

    if "## Refinement Log" in raw:
        raw = raw.rstrip() + f"\n{new_row}\n"
    else:
        raw += (
            f"\n\n## Refinement Log\n\n"
            f"| Date | Change | Reason |\n|------|--------|--------|\n{new_row}\n"
        )

    # Write locally so the running process sees it immediately
    CONTEXT_PATH.write_text(raw, encoding="utf-8")
    # Invalidate in-memory context cache so next card uses updated context
    _CTX_CACHE.clear()
    # Push to GitHub so it survives service restarts
    await _push_context_to_github(raw)

# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request):
    """
    Receive Telegram updates. Any plain text message from Brian's chat is
    appended to claudio_context.md and pushed to GitHub.
    """
    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    message = update.get("message", {})
    text    = message.get("text", "").strip()
    chat_id = str(message.get("chat", {}).get("id", ""))

    # Only process plain-text messages from Brian's chat; ignore bot commands
    if not text or chat_id != str(TELEGRAM_CHAT_ID) or text.startswith("/"):
        return {"ok": True}

    await _append_feedback(text)

    # Confirm receipt in Telegram
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": "✓ Got it. Adding to context."},
            timeout=10,
        )

    return {"ok": True}

@app.post("/send-card")
async def send_card(request: SendCardRequest, authorization: str = Header(None)):
    """Legacy endpoint: accepts a base64-encoded PNG and sends to Telegram."""
    _auth(authorization)
    try:
        image_bytes = base64.b64decode(request.image_base64)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": request.caption},
                files={"photo": ("card.png", image_bytes, "image/png")},
                timeout=60,
            )
        result = resp.json()
        if not result.get("ok"):
            raise HTTPException(status_code=500, detail=str(result))
        return {"ok": True, "message_id": result["result"]["message_id"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate-and-send")
def generate_and_send(request: GenerateAndSendRequest, authorization: str = Header(None)):
    """
    Generate a Claudio style card via DALL-E 3 + PIL, then send to Telegram.
    Sync def so FastAPI runs it in a thread pool, avoiding event-loop blocking
    during the ~20-30s DALL-E generation.
    """
    _auth(authorization)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        generate_card(request.weather, request.outfit, tmp_path, request.context)

        with open(tmp_path, "rb") as f:
            image_bytes = f.read()

        result = _telegram_send(image_bytes, request.caption)
        return {"ok": True, "message_id": result["result"]["message_id"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
