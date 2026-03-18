from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import base64
import os
import tempfile
from card_generator import generate_card

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")
API_SECRET         = os.environ.get("API_SECRET")


class SendCardRequest(BaseModel):
    image_base64: str
    caption: str = ""


class GenerateAndSendRequest(BaseModel):
    weather: dict
    outfit:  dict
    context: str = "office"
    caption: str = ""


def _auth(authorization: str):
    if not API_SECRET or authorization != f"Bearer {API_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/send-card")
async def send_card(request: SendCardRequest, authorization: str = Header(None)):
    _auth(authorization)
    try:
        image_bytes = base64.b64decode(request.image_base64)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": request.caption},
                files={"photo": ("card.png", image_bytes, "image/png")},
                timeout=30.0,
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
async def generate_and_send(request: GenerateAndSendRequest, authorization: str = Header(None)):
    _auth(authorization)
    try:
        # Generate card to a temp file on Railway's filesystem
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            generate_card(request.weather, request.outfit, tmp_path, request.context)
            with open(tmp_path, "rb") as f:
                image_bytes = f.read()
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        # Send to Telegram
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": request.caption},
                files={"photo": ("card.png", image_bytes, "image/png")},
                timeout=60.0,
            )
            result = resp.json()
            if not result.get("ok"):
                raise HTTPException(status_code=500, detail=str(result))
            return {"ok": True, "message_id": result["result"]["message_id"]}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
