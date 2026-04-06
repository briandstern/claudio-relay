"""
Telegram client: send card, send alert text, register webhook.
"""
import os

import httpx

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def _base_url() -> str:
    return f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_card(image_bytes: bytes, caption: str = "") -> dict:
    """Send PNG as a document (no compression) to Brian's chat."""
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{_base_url()}/sendDocument",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
            files={"document": ("card.png", image_bytes, "image/png")},
        )
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram sendDocument failed: {result}")
    return result


def send_message(text: str) -> dict:
    """Send a plain text message to Brian's chat."""
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{_base_url()}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        )
    return resp.json()


def send_alert(message: str):
    """Send a failure alert. Swallows exceptions so it never blocks the caller."""
    try:
        send_message(f"Claudio failed: {message}")
    except Exception as e:
        print(f"[alert] failed to send Telegram alert: {e}")


def download_photo(file_id: str) -> bytes:
    """Download a photo from Telegram by file_id, return raw bytes."""
    with httpx.Client(timeout=30) as client:
        r = client.get(
            f"{_base_url()}/getFile",
            params={"file_id": file_id},
        )
        file_path = r.json()["result"]["file_path"]
        r2 = client.get(
            f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        )
        r2.raise_for_status()
        return r2.content


def register_webhook(service_url: str):
    """Register the Telegram webhook. Safe to call on every startup."""
    webhook_url = f"{service_url}/telegram-webhook"
    with httpx.Client(timeout=10) as client:
        r = client.post(
            f"{_base_url()}/setWebhook",
            json={"url": webhook_url, "allowed_updates": ["message"]},
        )
    print(f"[webhook] {r.json()}")
