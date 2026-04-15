"""
Claudio Cron Runner — deployed as a Railway Cron Service.
Scheduled: 0 10 * * * UTC  (= 6am ET in summer EDT / 5am ET in winter EST)
The app's last_sent idempotency prevents duplicate sends if the schedule drifts.
"""
import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

RAILWAY_URL = os.environ.get(
    "RAILWAY_URL", "https://telegram-relay-production.up.railway.app"
)
API_SECRET = os.environ.get("API_SECRET", "")
ET = ZoneInfo("America/New_York")


def main():
    now_et = datetime.now(ET)
    print(f"[cron] running at {now_et.strftime('%Y-%m-%d %H:%M %Z')}")

    last_error = None
    for attempt in range(1, 3):
        try:
            print(f"[cron] attempt {attempt}/2")
            with httpx.Client(timeout=180) as client:
                resp = client.post(
                    f"{RAILWAY_URL}/generate-and-send",
                    headers={"Authorization": f"Bearer {API_SECRET}"},
                    json={},
                )
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                print(f"[cron] success — message_id={data.get('message_id')}")
                sys.exit(0)
            raise RuntimeError(f"HTTP {resp.status_code}: {data}")

        except Exception as e:
            last_error = e
            print(f"[cron] attempt {attempt} failed: {e}")
            if attempt < 2:
                time.sleep(30)

    # Both attempts failed — the main service will have already alerted Brian,
    # but log it here too for Railway cron logs
    print(f"[cron] all attempts failed: {last_error}")
    sys.exit(1)


if __name__ == "__main__":
    main()
