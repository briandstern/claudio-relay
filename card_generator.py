"""
Claudio Card Generator
Phone-optimised: 1080px wide.
Layout: header → [item grid (left) | portrait (right)] → stylist tip footer.
"""
import base64
import concurrent.futures
import io
import os
import subprocess
import sys
from datetime import datetime

from PIL import Image

import image_gen
import outfit_selector

# Install Playwright browsers at module load — ensures browser path matches runtime
subprocess.run(
    [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
    capture_output=True,
)


def _img_to_b64(data: bytes) -> str:
    """Convert raw image bytes to a base64 WebP data URI."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/webp;base64,{b64}"


def _weather_context_line(weather: dict) -> str:
    """One punchy line about today's conditions for the card footer."""
    from outfit_selector import is_wet_day
    feels = weather.get("feels_like_f")
    code = weather.get("weathercode", 0)
    wind = weather.get("windspeed_mph") or 0
    precip = weather.get("precip_prob") or 0
    temp = int(feels) if feels is not None else None

    if is_wet_day(weather):
        if code in {71, 73, 75}:
            return "Snow on the ground. Leather boots, sealed collar, no suede."
        return "Rain today. Leather over suede, sealed neckline on the platform."
    if temp is not None and temp < 25:
        return "Brutal out there. Coat buttoned, scarf tight, gloves in pocket."
    if temp is not None and temp < 43:
        return "Cold commute. Layer up — you can always remove at the office."
    if temp is not None and temp > 72:
        return "Warm one. Linen breathes, light layers only."
    if wind >= 20:
        return "Windy today. Keep the collar up and the jacket zipped on the platform."
    return ""


def _build_html(
    outfit: dict,
    item_imgs: list,
    portrait: bytes | None,
    weather: dict,
    context: str,
) -> str:
    pieces = outfit.get("pieces", [])
    stylist_note = outfit.get("stylist_note", "")
    outfit_name = outfit.get("name", "Today's Look")

    now = datetime.now()
    day_str = now.strftime("%A, %B %-d")
    weather_str = outfit_selector.weather_description(weather)
    context_label = "OFFICE" if context == "office" else "WEEKEND"

    # Adapt item image height based on piece count
    n = len(pieces)
    if n <= 4:
        img_h = 170
    elif n <= 6:
        img_h = 125
    else:
        img_h = 100

    cells_html = ""
    for piece, img_data in zip(pieces, item_imgs):
        category = piece.get("category", "").upper()
        name = piece.get("name", "")
        brand = piece.get("brand", "")
        color_hex = piece.get("color", "#EDEBE5")

        if img_data:
            img_src = _img_to_b64(img_data)
            img_tag = (
                f'<img src="{img_src}" alt="{name}" '
                f'style="width:100%;height:{img_h}px;object-fit:cover;'
                f'border-radius:10px 10px 0 0;">'
            )
        else:
            img_tag = (
                f'<div style="width:100%;height:{img_h}px;background:{color_hex};'
                f'border-radius:10px 10px 0 0;"></div>'
            )

        brand_html = f'<span class="brand">{brand}</span>' if brand else ""
        cells_html += (
            f'\n        <div class="cell">'
            f'\n            {img_tag}'
            f'\n            <div class="cell-label">'
            f'\n                <span class="cat">{category}</span>'
            f'\n                <span class="item-name">{name}</span>'
            f'\n                {brand_html}'
            f'\n            </div>'
            f'\n        </div>'
        )

    if portrait:
        port_src = _img_to_b64(portrait)
        portrait_html = f'<img src="{port_src}" alt="outfit" class="portrait-img">'
    else:
        portrait_html = '<div class="portrait-placeholder"></div>'

    css = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    width: 1080px;
    background: #FAFAF8;
    font-family: 'Inter', sans-serif;
  }
  .header {
    background: #1a1a1a;
    padding: 44px 56px 36px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }
  .brand-name {
    font-size: 12px; font-weight: 700;
    letter-spacing: 0.25em; color: #8B7355; margin-bottom: 10px;
  }
  .outfit-name { font-size: 40px; font-weight: 700; color: #fff; line-height: 1.1; }
  .header-right { text-align: right; }
  .day-label { font-size: 14px; color: #999; letter-spacing: 0.04em; }
  .weather-label { font-size: 22px; font-weight: 600; color: #fff; margin-top: 6px; }
  .context-badge {
    display: inline-block; background: #8B7355; color: #fff;
    font-size: 11px; font-weight: 700; letter-spacing: 0.18em;
    padding: 5px 16px; border-radius: 20px; margin-top: 12px;
  }
  .body { display: flex; background: #FAFAF8; }
  .grid-col { width: 490px; flex-shrink: 0; padding: 40px 24px 40px 56px; display: flex; flex-direction: column; justify-content: space-between; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .cell { background: #EDEBE5; border-radius: 10px; overflow: hidden; }
  .cell-label { padding: 10px 12px 13px; display: flex; flex-direction: column; gap: 3px; }
  .cat { font-size: 9px; font-weight: 700; letter-spacing: 0.18em; color: #8B7355; }
  .item-name { font-size: 12px; font-weight: 600; color: #1a1a1a; line-height: 1.3; }
  .brand { font-size: 11px; color: #999; }
  .portrait-col { flex: 1; min-width: 0; background: #F0EEE8; display: flex; align-items: stretch; }
  .portrait-img { width: 100%; height: 100%; object-fit: cover; object-position: center top; display: block; }
  .portrait-placeholder { width: 100%; background: #E8E5DF; }
  .footer { background: #1a1a1a; padding: 40px 56px; border-top: 3px solid #8B7355; }
  .tip-label { font-size: 10px; font-weight: 700; letter-spacing: 0.22em; color: #8B7355; margin-bottom: 14px; }
  .tip-text {
    font-family: 'Playfair Display', serif; font-style: italic;
    font-size: 22px; color: #F5F3EF; line-height: 1.55;
  }
  .weather-context {
    font-size: 13px; font-weight: 500; color: #8B7355;
    margin-top: 20px; letter-spacing: 0.03em;
  }
"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:ital@1&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
  <div class="header">
    <div>
      <div class="brand-name">CLAUDIO</div>
      <div class="outfit-name">{outfit_name}</div>
    </div>
    <div class="header-right">
      <div class="day-label">{day_str}</div>
      <div class="weather-label">{weather_str}</div>
      <div class="context-badge">{context_label}</div>
    </div>
  </div>
  <div class="body">
    <div class="grid-col">
      <div class="grid">{cells_html}</div>
    </div>
    <div class="portrait-col">{portrait_html}</div>
  </div>
  <div class="footer">
    <div class="tip-label">STYLIST TIP</div>
    <div class="tip-text">"{stylist_note}"</div>
    {f'<div class="weather-context">{_weather_context_line(weather)}</div>' if _weather_context_line(weather) else ''}
  </div>
</body>
</html>"""


def generate_card(weather: dict, outfit: dict, output_path: str, context: str = "office") -> str:
    """
    Generate the Claudio outfit card PNG.
    Fetches all images in parallel, builds HTML, screenshots with Playwright.
    Returns output_path.
    """
    pieces = outfit.get("pieces", [])

    def get_product_img(piece):
        try:
            return image_gen.gen_product_image(piece)
        except Exception as e:
            print(f"[card] product image failed for '{piece.get('name')}': {e}")
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        portrait_future = pool.submit(image_gen.gen_portrait, outfit, context, weather)
        item_futures = [pool.submit(get_product_img, p) for p in pieces]

        item_imgs = [f.result() for f in item_futures]
        try:
            portrait = portrait_future.result()
        except Exception as e:
            print(f"[card] portrait failed: {e}")
            portrait = None

    html = _build_html(outfit, item_imgs, portrait, weather, context)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.set_content(html, wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(1000)  # allow fonts to render
        page.screenshot(path=output_path, full_page=True)
        browser.close()

    return output_path
