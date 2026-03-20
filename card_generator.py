#!/usr/bin/env python3
"""
Claudio Card Generator v2
Editorial style: DALL-E 3 flat-lay product images + full look portrait.
Layout mirrors a professional stylist brief (Daily Outfit Brief format).
"""

import os, io, math, concurrent.futures
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import httpx
from openai import OpenAI

# ─── Canvas ───────────────────────────────────────────────────────────────────
W, H = 1080, 1520
PAD  = 52

# ─── Palette ──────────────────────────────────────────────────────────────────
BG       = (255, 255, 255)
DARK     = (18,  18,  18 )
MID      = (105, 99,  91 )
LIGHT    = (168, 160, 150)
DIVIDER  = (218, 212, 204)
ACCENT   = (139, 115, 85 )
WHITE    = (255, 255, 255)
CELL_BG  = (248, 246, 242)

# ─── WMO Weather Codes ────────────────────────────────────────────────────────
WMO = {
    0:"Clear Sky", 1:"Mainly Clear", 2:"Partly Cloudy", 3:"Overcast",
    45:"Fog", 48:"Fog", 51:"Drizzle", 53:"Drizzle", 55:"Drizzle",
    61:"Light Rain", 63:"Rain", 65:"Heavy Rain",
    71:"Light Snow", 73:"Snow", 75:"Heavy Snow", 77:"Snow Grains",
    80:"Showers", 81:"Showers", 82:"Heavy Showers",
    95:"Thunderstorm", 96:"Thunderstorm", 99:"Thunderstorm",
}

# ─── Fonts ────────────────────────────────────────────────────────────────────
FONTS_DIR = Path(__file__).parent / "fonts"

def _lf(paths, size):
    for p in paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default()

def _load_fonts():
    sb = [str(FONTS_DIR / "DMSans-Bold.ttf"),
          "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    sr = [str(FONTS_DIR / "DMSans-Regular.ttf"),
          "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    si = [str(FONTS_DIR / "InstrumentSerif-Italic.ttf"),
          "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"]
    xb = ["/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"]
    return {
        'headline':   _lf(sb,  54),
        'name':       _lf(xb,  32),
        'sub':        _lf(sr,  13),
        'meta_k':     _lf(sb,  12),
        'meta_v':     _lf(sr,  12),
        'section':    _lf(sb,  11),
        'num':        _lf(sb,  17),
        'item_name':  _lf(sb,  13),
        'item_brand': _lf(sr,  12),
        'note':       _lf(si,  17),
        'note_attr':  _lf(sr,  12),
        'footer':     _lf(sb,  14),
        'footer_sm':  _lf(sr,  12),
        'tag':        _lf(sr,  13),
        'palette_lbl':_lf(sr,  11),
    }

# ─── Color Utilities ──────────────────────────────────────────────────────────

def _hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _color_name(hex_c):
    r, g, b = _hex_rgb(hex_c)
    bri = (r * 299 + g * 587 + b * 114) // 1000
    mx  = max(r, g, b)
    mn  = min(r, g, b)
    sat = (mx - mn) / mx if mx else 0
    if bri < 28:   return "black"
    if bri > 228:  return "white"
    if sat < 0.12:
        if bri < 75:  return "charcoal"
        if bri < 140: return "gray"
        return "light gray"
    if mx == r:
        if g > b: return "brown" if bri < 120 else "tan"
        return "burgundy" if bri < 100 else "rose"
    if mx == g:
        return "olive" if r > b else ("forest green" if bri < 100 else "green")
    if bri < 70:  return "navy"
    if bri < 130: return "dark blue"
    return "blue"

def _luminance(rgb):
    return (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / (255000)

def _contrast(rgb):
    return (240, 238, 234) if _luminance(rgb) < 0.45 else DARK

# ─── Text Utility ─────────────────────────────────────────────────────────────

def _wrap(text, font, max_w):
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = ' '.join(cur + [w])
        if font.getbbox(test)[2] <= max_w:
            cur.append(w)
        else:
            if cur: lines.append(' '.join(cur))
            cur = [w]
    if cur: lines.append(' '.join(cur))
    return lines

# ─── Image Generation ─────────────────────────────────────────────────────────

def _client():
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    return OpenAI(api_key=key)

def _fetch(url):
    r = httpx.get(url, timeout=120, follow_redirects=True)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert('RGB')

def _gen_item_image(piece, client):
    col  = _color_name(piece.get('color', '#888888'))
    mat  = piece.get('material', '')
    name = piece.get('name', 'clothing item')
    mat_str = f"{mat} " if mat else ""
    prompt = (
        f"Professional studio product photography. "
        f"A single {col} {mat_str}{name}, laid flat on a pure white background. "
        f"Overhead top-down view. Soft even studio lighting, no harsh shadows. "
        f"High-end fashion editorial quality. Perfectly styled and pressed. "
        f"Isolated item only — no people, no props, no text, no labels."
    )
    resp = client.images.generate(
        model="dall-e-3", prompt=prompt,
        size="1024x1024", quality="hd", n=1
    )
    return _fetch(resp.data[0].url)

def _gen_look_image(outfit, context, weather, client):
    pieces = outfit.get('pieces', [])
    descs = []
    for p in pieces:
        col  = _color_name(p.get('color', '#888888'))
        name = p.get('name', '')
        mat  = p.get('material', '')
        descs.append(f"{col}{' ' + mat if mat else ''} {name}".strip())
    outfit_str = ", ".join(descs)

    loc_scene = {
        'office':        ('walking on a quiet city block near glass office buildings',
                          'overcast urban daylight, diffused shadows'),
        'weekend':       ('standing on a tree-lined residential street, slight motion in the leaves',
                          'soft golden afternoon sun, long natural shadows'),
        'date_night':    ('outside a dimly lit restaurant entrance, warm window light spilling onto the sidewalk',
                          'dusk, ambient streetlight mixed with warm interior glow'),
        'family_outing': ('in a city park, dappled light through trees',
                          'bright spring midday, natural fill light'),
    }.get(context, ('on a quiet city street', 'natural daylight, overcast'))

    loc, light_cue = loc_scene

    temp = int(round(float(weather.get('current_temp', 65))))
    season = "autumn" if 45 <= temp <= 65 else ("winter" if temp < 45 else ("summer" if temp > 80 else "spring"))

    prompt = (
        f"Photograph. Shot on a Leica SL2-S with a 75mm f/1.4 Summilux lens. "
        f"A well-dressed man in his early 30s, {loc}. "
        f"He is wearing: {outfit_str}. "
        f"{light_cue}, {season}. "
        f"Full-length frame, slight subject separation from background. "
        f"Authentic photographic qualities: natural skin texture with visible pores, "
        f"realistic fabric drape and slight creasing, true-to-life material sheen — "
        f"matte wool looks matte, leather shows natural surface variation. "
        f"Color grading is restrained and editorial, similar to a GQ or Esquire fashion story. "
        f"Slight natural film grain. No artificial skin smoothing, no plastic or CGI sheen, "
        f"no over-saturated colors, no digital compositing look. "
        f"The image should be indistinguishable from a frame pulled from a professional fashion shoot. "
        f"Subject has relaxed, natural posture — not stiff or posed. "
        f"No text overlays, no visible brand logos."
    )
    resp = client.images.generate(
        model="dall-e-3", prompt=prompt,
        size="1024x1792", quality="hd", n=1
    )
    return _fetch(resp.data[0].url)

def _generate_all_images(outfit, context, weather):
    """Generate all DALL-E images in parallel using a thread pool."""
    c = _client()
    pieces = outfit.get('pieces', [])
    results = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        item_futs = {ex.submit(_gen_item_image, p, c): i for i, p in enumerate(pieces)}
        look_fut  = ex.submit(_gen_look_image, outfit, context, weather, c)

        for fut, idx in item_futs.items():
            try:
                results[f'item_{idx}'] = fut.result(timeout=120)
            except Exception as e:
                print(f"[warn] item {idx} image failed: {e}")
                rgb = _hex_rgb(pieces[idx].get('color', '#999999'))
                results[f'item_{idx}'] = Image.new('RGB', (512, 512), rgb)

        try:
            results['look'] = look_fut.result(timeout=120)
        except Exception as e:
            print(f"[warn] look image failed: {e}")
            results['look'] = None

    return results

# ─── Main Card Generator ──────────────────────────────────────────────────────

def generate_card(weather: dict, outfit: dict, output_path: str, context: str = "office") -> str:
    """
    Render the full Claudio editorial style card and save as PNG.
    Calls DALL-E 3 to generate clothing item flat-lays and a full look portrait.
    """
    now      = datetime.now()
    day_str  = now.strftime("%A").upper()
    date_str = now.strftime("%B %d, %Y").upper()

    f   = _load_fonts()
    imgs = _generate_all_images(outfit, context, weather)

    canvas = Image.new('RGB', (W, H), BG)
    d      = ImageDraw.Draw(canvas)

    # ── Extract data ──────────────────────────────────────────────────────────
    temp      = int(round(float(weather.get('current_temp', 60))))
    high      = int(round(float(weather.get('high', 65))))
    low       = int(round(float(weather.get('low', 50))))
    wind      = int(round(float(weather.get('wind', 8))))
    rain      = int(round(float(weather.get('rain_prob', 0))))
    wcode     = int(weather.get('weathercode', 0))
    condition = WMO.get(wcode, weather.get('condition', 'Clear'))

    outfit_name  = outfit.get('name', 'The Edit')
    stylist_note = outfit.get('stylist_note', '')
    pieces       = outfit.get('pieces', [])
    style_tags   = outfit.get('style_tags', [])

    ACC_CATS = {'ACCESSORIES', 'BELT', 'SCARF', 'WATCH'}
    main_p = [p for p in pieces if p.get('category', '').upper() not in ACC_CATS]
    acc_p  = [p for p in pieces if p.get('category', '').upper() in ACC_CATS]

    ctx_label = {
        'office': 'Office Day', 'weekend': 'Weekend',
        'date_night': 'Date Night', 'family_outing': 'Family Day',
    }.get(context, 'Today')

    # ══════════════════════════════════════════════════════════════════════════
    # HEADER  (y: 0 → ~185)
    # ══════════════════════════════════════════════════════════════════════════
    y0 = PAD

    # Left: "DAILY OUTFIT BRIEF"
    d.text((PAD, y0), "DAILY OUTFIT BRIEF", font=f['headline'], fill=DARK)
    hl_h = f['headline'].getbbox("DAILY OUTFIT BRIEF")[3]

    # Right: name / date / city stack
    d.text((W - PAD, y0 + 2),           "BRIAN'S",                   font=f['sub'],  fill=MID,   anchor='rt')
    d.text((W - PAD, y0 + 19),          "Claudio",                   font=f['name'], fill=DARK,  anchor='rt')
    name_h = f['name'].getbbox("Claudio")[3]
    d.text((W - PAD, y0 + 19 + name_h + 5), f"{day_str}, {date_str}", font=f['sub'],  fill=MID,   anchor='rt')
    d.text((W - PAD, y0 + 19 + name_h + 21),"PORT WASHINGTON, NY",   font=f['sub'],  fill=LIGHT, anchor='rt')

    # Heavy rule under title
    r1y = y0 + hl_h + 18
    d.line([(PAD, r1y), (W - PAD, r1y)], fill=DARK, width=2)

    # Meta strip: PREPARED FOR | LOOK | SCHEDULE | WEATHER
    m_y = r1y + 14
    meta = [
        ("PREPARED FOR:", "Brian"),
        ("LOOK:", outfit_name),
        ("SCHEDULE:", ctx_label),
        ("WEATHER:", f"{temp}°F  ·  {condition}  ·  Wind {wind} mph"),
    ]
    mx = PAD
    for lbl, val in meta:
        lw = f['meta_k'].getbbox(lbl)[2]
        d.text((mx, m_y), lbl, font=f['meta_k'], fill=DARK)
        d.text((mx + lw + 5, m_y), val, font=f['meta_v'], fill=MID)
        sep_x = mx + lw + 5 + f['meta_v'].getbbox(val)[2] + 22
        if sep_x < W - PAD - 80:
            d.text((sep_x - 10, m_y), "|", font=f['meta_v'], fill=DIVIDER)
        mx = sep_x
        if mx > W - 200:
            break

    # Light rule under meta
    r2y = m_y + 22
    d.line([(PAD, r2y), (W - PAD, r2y)], fill=DIVIDER, width=1)
    BODY_TOP = r2y + 20

    # ══════════════════════════════════════════════════════════════════════════
    # LAYOUT CONSTANTS
    # ══════════════════════════════════════════════════════════════════════════
    FOOT_H   = 108
    BODY_BOT = H - FOOT_H
    BODY_H   = BODY_BOT - BODY_TOP

    COL_GAP = 22
    LEFT_W  = 422
    RIGHT_X = PAD + LEFT_W + COL_GAP
    RIGHT_W = W - PAD - RIGHT_X

    # ══════════════════════════════════════════════════════════════════════════
    # LEFT COLUMN — FLAT LAY GRID
    # ══════════════════════════════════════════════════════════════════════════
    d.text((PAD, BODY_TOP), "FLAT LAY GRID", font=f['section'], fill=LIGHT)
    GT = BODY_TOP + 22

    n    = len(main_p)
    cols = 2
    rows = math.ceil(n / cols)

    cx_gap = 10
    cy_gap = 14
    cw = (LEFT_W - (cols - 1) * cx_gap) // cols  # ~206px

    # Reserve space for accessories + palette at bottom
    acc_reserve = 55 if acc_p else 0
    PAL_H       = 70  # "today's palette" strip
    grid_h_avail = BODY_H - 22 - acc_reserve - PAL_H - 20
    ch = min(390, (grid_h_avail - (rows - 1) * cy_gap) // max(rows, 1))
    img_area_h = ch - 55  # room for labels at bottom of cell

    for idx, piece in enumerate(main_p):
        col = idx % cols
        row = idx // cols
        cx  = PAD + col * (cw + cx_gap)
        cy  = GT  + row * (ch + cy_gap)

        # Cell background
        d.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=7, fill=CELL_BG)

        # Clothing item image (centered in image area)
        item_img = imgs.get(f'item_{idx}')
        if item_img:
            sz     = min(cw - 16, img_area_h - 8)
            resized = item_img.resize((sz, sz), Image.LANCZOS)
            ix = cx + (cw - sz) // 2
            iy = cy + (img_area_h - sz) // 2
            canvas.paste(resized, (ix, iy))

        # Number + name + brand at bottom of cell
        label_y = cy + img_area_h + 6
        d.text((cx + 8,  label_y),      f"{idx + 1}.", font=f['num'],        fill=ACCENT)
        name_txt = piece.get('name', '')
        if len(name_txt) > 20: name_txt = name_txt[:18] + '…'
        d.text((cx + 28, label_y + 1),  name_txt,      font=f['item_name'],  fill=DARK)
        brand_txt = piece.get('brand', '')
        col_name  = _color_name(piece.get('color', '#888')).title()
        brand_line = f"{col_name}, {brand_txt}" if brand_txt else col_name
        if len(brand_line) > 26: brand_line = brand_line[:24] + '…'
        d.text((cx + 28, label_y + 18), brand_line,    font=f['item_brand'], fill=MID)

    # Accessories row
    grid_bot = GT + rows * (ch + cy_gap) - cy_gap
    if acc_p:
        ay = grid_bot + 12
        parts = []
        for p in acc_p:
            n_s = p.get('name', '')
            b_s = p.get('brand', '')
            parts.append(f"{n_s} ({b_s})" if b_s else n_s)
        d.text((PAD, ay),      "ACCESSORIES:", font=f['meta_k'], fill=DARK)
        acc_val = ", ".join(parts)
        if len(acc_val) > 55: acc_val = acc_val[:53] + '…'
        d.text((PAD + 92, ay), acc_val,        font=f['meta_v'], fill=MID)
        grid_bot = ay + 18

    # Today's Palette strip
    pal_top = grid_bot + 18
    d.text((PAD, pal_top), "TODAY'S PALETTE", font=f['section'], fill=LIGHT)
    pal_top += 18
    swatch_total_w = LEFT_W - 4
    sw = (swatch_total_w - (len(main_p) - 1) * 8) // max(len(main_p), 1)
    sh = 32
    for i, piece in enumerate(main_p):
        sx  = PAD + i * (sw + 8)
        rgb = _hex_rgb(piece.get('color', '#999999'))
        d.rounded_rectangle([sx, pal_top, sx + sw, pal_top + sh], radius=4, fill=rgb)
        cn  = _color_name(piece.get('color', '#888')).title()
        d.text((sx + sw // 2, pal_top + sh + 7), cn,
               font=f['palette_lbl'], fill=LIGHT, anchor='mt')

    # ══════════════════════════════════════════════════════════════════════════
    # RIGHT COLUMN — FULL LOOK VISUALIZATION
    # ══════════════════════════════════════════════════════════════════════════
    d.text((RIGHT_X, BODY_TOP), "FULL LOOK VISUALIZATION", font=f['section'], fill=LIGHT)
    LT = BODY_TOP + 22

    look_img    = imgs.get('look')
    note_start  = LT + 20

    if look_img:
        NOTE_RESERVE = 95
        max_lh = BODY_H - 22 - NOTE_RESERVE
        max_lw = RIGHT_W
        ow, oh = look_img.size
        scale  = min(max_lw / ow, max_lh / oh)
        lw, lh = int(ow * scale), int(oh * scale)
        resized = look_img.resize((lw, lh), Image.LANCZOS)
        lx = RIGHT_X + (RIGHT_W - lw) // 2
        ly = LT
        canvas.paste(resized, (lx, ly))

        # Time label in top-right corner of photo
        time_str = now.strftime("%I:%M %p").lstrip("0")
        d.text((lx + lw - 10, ly + 11), "Daylight",  font=f['item_brand'], fill=WHITE, anchor='rt')
        d.text((lx + lw - 10, ly + 25), time_str,    font=f['item_brand'], fill=WHITE, anchor='rt')

        note_start = ly + lh + 14

    # Stylist note
    if stylist_note:
        note_lines = _wrap(stylist_note, f['note'], RIGHT_W)
        lh_n = 25
        for i, line in enumerate(note_lines[:4]):
            d.text((RIGHT_X, note_start + i * lh_n), line, font=f['note'], fill=DARK)
        sig_y = note_start + min(len(note_lines), 4) * lh_n + 10
        d.text((RIGHT_X, sig_y), "— Claudio  (Your AI Stylist)", font=f['note_attr'], fill=MID)

    # ══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ══════════════════════════════════════════════════════════════════════════
    fy = H - FOOT_H + 16
    d.line([(PAD, fy - 14), (W - PAD, fy - 14)], fill=DIVIDER, width=1)

    d.text((PAD, fy),      "BRIAN'S PERSONAL STYLING", font=f['footer'],    fill=DARK)
    d.text((PAD, fy + 22), "Powered by Claudio  ·  Port Washington, NY",
           font=f['footer_sm'], fill=MID)

    if style_tags:
        tags_str = "  ·  ".join(t.upper() for t in style_tags[:3])
        d.text((W - PAD, fy + 11), tags_str, font=f['tag'], fill=LIGHT, anchor='rt')

    canvas.save(output_path, 'PNG')
    return output_path
