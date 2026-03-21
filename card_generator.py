#!/usr/bin/env python3
"""
Claudio Card Generator v4
Phone-optimised: 1080Ã1920 (9:16), minimum 28px body text, stacked layout.
Layout: header â full-width editorial portrait â 2-col flat-lay grid â palette â note â footer.
Context-aware: loads claudio_context.md to personalise DALL-E prompts.
"""

import os, io, re, math, concurrent.futures, time as _time
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import httpx
from openai import OpenAI

# âââ Context File âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
_CTX_CACHE: dict = {}
_CTX_LOAD_TIME: float = 0.0

def _load_context() -> dict:
    """Load and parse claudio_context.md into a usable dict (cached)."""
    global _CTX_LOAD_TIME
    if _CTX_CACHE and (_time.time() - _CTX_LOAD_TIME < 300):
        return _CTX_CACHE
    _CTX_CACHE.clear()

    ctx_path = Path(__file__).parent / "claudio_context.md"
    if not ctx_path.exists():
        _CTX_CACHE['subject'] = "a well-dressed man in his mid-30s, athletic build"
        _CTX_CACHE['raw'] = ""
        return _CTX_CACHE

    raw = ctx_path.read_text(encoding='utf-8')
    _CTX_CACHE['raw'] = raw

    who_match = re.search(r'## Who I Am\s+(.*?)(?=\n##|\Z)', raw, re.DOTALL)
    if who_match:
        who_text = who_match.group(1).strip()
        build = "athletic build"
        build_match = re.search(r'athletic build \(([^)]+)\)', who_text)
        if build_match:
            build = f"athletic build ({build_match.group(1)})"
        age_match = re.search(r'(mid-\d0s|early \d0s|late \d0s)', who_text)
        age = age_match.group(1) if age_match else "mid-30s"
        _CTX_CACHE['subject'] = f"a well-dressed man in his {age}, {build}"
    else:
        _CTX_CACHE['subject'] = "a well-dressed man in his mid-30s, athletic build"

    loc_match = re.search(r'Check weather for ([^(]+)\(home', raw)
    _CTX_CACHE['home_location'] = loc_match.group(1).strip() if loc_match else "Port Washington, NY"

    print(f"[ctx] Loaded context â subject: {_CTX_CACHE['subject']}")
    _CTX_LOAD_TIME = _time.time()
    return _CTX_CACHE


# âââ Canvas âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
W, H   = 1080, 1920
PAD    = 60
INNER  = W - 2 * PAD        # 960px usable width

# âââ Palette ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
BG      = (255, 255, 255)
DARK    = (18,  18,  18 )
MID     = (100, 94,  86 )
LIGHT   = (158, 150, 140)
DIVIDER = (218, 212, 204)
ACCENT  = (139, 115, 85 )
WHITE   = (255, 255, 255)
CELL_BG = (248, 246, 242)

# âââ WMO Weather Codes ââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
WMO = {
    0:"Clear Sky", 1:"Mainly Clear", 2:"Partly Cloudy", 3:"Overcast",
    45:"Fog", 48:"Fog", 51:"Drizzle", 53:"Drizzle", 55:"Drizzle",
    61:"Light Rain", 63:"Rain", 65:"Heavy Rain",
    71:"Light Snow", 73:"Snow", 75:"Heavy Snow", 77:"Snow Grains",
    80:"Showers", 81:"Showers", 82:"Heavy Showers",
    95:"Thunderstorm", 96:"Thunderstorm", 99:"Thunderstorm",
}
WMO_EMOJI = {
    0:"â",  1:"ð¤", 2:"â", 3:"â",
    45:"ð«", 48:"ð«", 51:"ð¦", 53:"ð¦", 55:"ð§",
    61:"ð¦", 63:"ð§", 65:"ð§",
    71:"ð¨", 73:"â", 75:"â",  77:"â",
    80:"ð¦", 81:"ð§", 82:"â",
    95:"â", 96:"â", 99:"â",
}

# âââ Fonts ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
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
        'headline':    _lf(sb, 44),   # DAILY OUTFIT BRIEF
        'name':        _lf(xb, 36),   # Claudio
        'sub':         _lf(sr, 28),   # date, city
        'meta_k':      _lf(sb, 26),   # weather key labels
        'meta_v':      _lf(sr, 26),   # weather values
        'weather':     _lf(sb, 30),   # weather strip
        'section':     _lf(sb, 26),   # FULL LOOK / FLAT LAY GRID
        'num':         _lf(sb, 36),   # item numbers
        'item_name':   _lf(sb, 34),   # item names (bold)
        'item_brand':  _lf(sr, 28),   # color Â· brand detail
        'note':        _lf(si, 32),   # stylist note italic
        'note_attr':   _lf(sr, 26),   # â Claudio attribution
        'footer':      _lf(sb, 28),   # footer label
        'footer_sm':   _lf(sr, 24),   # footer subtext
        'tag':         _lf(sr, 24),   # style tags
        'palette_lbl': _lf(sr, 26),   # color name under swatch
    }

# âââ Color Utilities ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

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
    return (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 255000

# âââ Text Utility âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

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

# âââ Image Generation âââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

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
    """E-commerce product photography â clean white background, no AI gloss."""
    col  = _color_name(piece.get('color', '#888888'))
    mat  = piece.get('material', '')
    name = piece.get('name', 'clothing item')
    mat_str = f"{mat} " if mat else ""
    prompt = (
        f"Professional e-commerce product photography. Pure white background, soft studio lighting. "
        f"A single {col} {mat_str}{name}, laid flat or displayed cleanly. "
        f"The kind of product photo you would find on Mr Porter, SSENSE, or Nordstrom. "
        f"Natural fabric texture and realistic drape â matte fabrics look matte, "
        f"suede looks like suede, leather shows natural grain. "
        f"No AI artifacts, no floating garments, no impossible folds. "
        f"No people, no props, no text, no brand logos. 8K detail, photorealistic."
    )
    resp = client.images.generate(
        model="dall-e-3", prompt=prompt,
        size="1024x1024", quality="hd", n=1
    )
    return _fetch(resp.data[0].url)

def _gen_look_image(outfit, context, weather, client):
    """Street-style editorial portrait â The Sartorialist aesthetic."""
    ctx     = _load_context()
    subject = ctx.get('subject', 'a well-dressed man in his mid-30s, athletic build')

    pieces = outfit.get('pieces', [])
    descs  = []
    for p in pieces:
        col  = _color_name(p.get('color', '#888888'))
        name = p.get('name', '')
        mat  = p.get('material', '')
        descs.append(f"{col}{' ' + mat if mat else ''} {name}".strip())
    outfit_str = ", ".join(descs)

    loc_scene = {
        'office':        ('walking on a quiet city block near glass office buildings in lower Manhattan',
                          'overcast urban daylight, naturally diffused shadows'),
        'weekend':       ('on a tree-lined street in Brooklyn, slight motion in the leaves',
                          'soft golden afternoon sun, long natural shadows'),
        'date_night':    ('outside a dimly lit restaurant entrance in the West Village, '
                          'warm window light spilling onto the pavement',
                          'dusk, ambient street light mixed with warm interior glow'),
        'family_outing': ('in Central Park, dappled light filtering through trees',
                          'bright spring midday, natural fill light'),
    }.get(context, ('on a quiet city street in New York', 'natural overcast daylight'))

    loc, light_cue = loc_scene
    temp   = int(round(float(weather.get('current_temp', 65))))
    season = "autumn" if 45 <= temp <= 65 else ("winter" if temp < 45 else ("summer" if temp > 80 else "spring"))

    prompt = (
        f"Candid street-style photograph. Shot on a Leica SL2-S, 75mm f/1.4 Summilux lens. "
        f"{subject.capitalize()}, {loc}. "
        f"He is wearing: {outfit_str}. "
        f"{light_cue}, {season}. "
        f"Full-length frame showing the complete outfit. Shallow depth of field, "
        f"subject separated from background. "
        f"IMPORTANT: Subject is NOT looking at the camera â he is looking slightly to the side, "
        f"in mid-stride, or his gaze is cast downward. Face may be partially turned. "
        f"The Sartorialist / GQ street-style aesthetic: candid, natural, never posed or stiff. "
        f"Authentic photographic qualities: natural skin texture, realistic fabric drape and "
        f"slight creasing, true-to-life material sheen â matte wool looks matte, "
        f"suede looks soft, leather shows natural grain variation. "
        f"Restrained, editorial color grading. Slight natural film grain. "
        f"No artificial skin smoothing, no plastic sheen, no studio backgrounds pretending "
        f"to be outdoors, no symmetrical poses, no impossible hand positions. "
        f"The image should be indistinguishable from a real street-style photograph. "
        f"No text overlays, no visible brand logos."
    )
    resp = client.images.generate(
        model="dall-e-3", prompt=prompt,
        size="1024x1792", quality="hd", n=1
    )
    return _fetch(resp.data[0].url)

def _generate_all_images(outfit, context, weather):
    """Generate all DALL-E images in parallel. Caps flat-lay at 4 main pieces."""
    c = _client()
    ACC_CATS = {'ACCESSORIES', 'BELT', 'SCARF', 'WATCH'}
    all_pieces  = outfit.get('pieces', [])
    main_pieces = [p for p in all_pieces if p.get('category', '').upper() not in ACC_CATS][:4]
    results     = {'_main_pieces': main_pieces}

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        item_futs = {ex.submit(_gen_item_image, p, c): i for i, p in enumerate(main_pieces)}
        look_fut  = ex.submit(_gen_look_image, outfit, context, weather, c)

        for fut, idx in item_futs.items():
            try:
                results[f'item_{idx}'] = fut.result(timeout=120)
            except Exception as e:
                print(f"[warn] item {idx} image failed: {e}")
                rgb = _hex_rgb(main_pieces[idx].get('color', '#999999'))
                results[f'item_{idx}'] = Image.new('RGB', (512, 512), rgb)

        try:
            results['look'] = look_fut.result(timeout=120)
        except Exception as e:
            print(f"[warn] look image failed: {e}")
            results['look'] = None

    return results


# âââ Main Card Generator ââââââââââââââââââââââââââââââââââââââââââââââââââââââ

def generate_card(weather: dict, outfit: dict, output_path: str, context: str = "office") -> str:
    """
    Render the Claudio editorial card at 1080Ã1920 (phone-optimised).
    Stacked layout:
      HEADER â FULL LOOK portrait (full-width crop) â FLAT LAY GRID â PALETTE â NOTE â FOOTER
    """
    now      = datetime.now()
    day_str  = now.strftime("%A").upper()
    date_str = now.strftime("%B %d, %Y").upper()

    f    = _load_fonts()
    imgs = _generate_all_images(outfit, context, weather)

    main_p = imgs.pop('_main_pieces', [])
    ACC_CATS = {'ACCESSORIES', 'BELT', 'SCARF', 'WATCH'}
    acc_p  = [p for p in outfit.get('pieces', [])
              if p.get('category', '').upper() in ACC_CATS]

    canvas = Image.new('RGB', (W, H), BG)
    d      = ImageDraw.Draw(canvas)

    # ââ Weather / outfit data âââââââââââââââââââââââââââââââââââââââââââââââââ
    temp      = int(round(float(weather.get('current_temp', 60))))
    wind      = int(round(float(weather.get('wind', 8))))
    rain      = int(round(float(weather.get('rain_prob', 0))))
    wcode     = int(weather.get('weathercode', 0))
    condition = WMO.get(wcode, weather.get('condition', 'Clear'))
    emoji     = WMO_EMOJI.get(wcode, '')

    outfit_name  = outfit.get('name', 'The Edit')
    stylist_note = outfit.get('stylist_note', '')
    style_tags   = outfit.get('style_tags', [])

    ctx_label = {
        'office': 'Office Day', 'weekend': 'Weekend',
        'date_night': 'Date Night', 'family_outing': 'Family Day',
    }.get(context, 'Today')

    # ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    # HEADER
    # ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    y = PAD

    # Left: masthead
    d.text((PAD, y), "DAILY OUTFIT BRIEF", font=f['headline'], fill=DARK)
    hl_h = f['headline'].getbbox("DAILY OUTFIT BRIEF")[3]

    # Right: name stack
    d.text((W - PAD, y),          "BRIAN'S",  font=f['sub'],  fill=MID,  anchor='rt')
    d.text((W - PAD, y + 30),     "Claudio",  font=f['name'], fill=DARK, anchor='rt')
    name_h = f['name'].getbbox("Claudio")[3]
    d.text((W - PAD, y + 30 + name_h + 6),
           f"{day_str}, {date_str}", font=f['sub'], fill=MID, anchor='rt')

    # Rule under masthead
    r1y = y + max(hl_h, name_h + 70) + 16
    d.line([(PAD, r1y), (W - PAD, r1y)], fill=DARK, width=2)

    # Weather strip â emoji + temp + condition + wind, outfit name right-aligned
    wy = r1y + 18
    rain_str = f"  Â·  {rain}% rain" if rain >= 20 else ""
    weather_str = f"{emoji}  {temp}Â°F  Â·  {condition}  Â·  Wind {wind} mph{rain_str}"
    d.text((PAD,     wy), weather_str, font=f['weather'], fill=DARK)
    d.text((W - PAD, wy), outfit_name, font=f['weather'], fill=ACCENT, anchor='rt')

    wh = f['weather'].getbbox(weather_str)[3]
    r2y = wy + wh + 16
    d.line([(PAD, r2y), (W - PAD, r2y)], fill=DIVIDER, width=1)

    BODY_TOP = r2y + 24

    # ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    # FULL LOOK â full-width portrait, cropped to ~460px display height
    # ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    PHOTO_DISPLAY_H = 460   # px shown on card (cropped from top of portrait)

    d.text((PAD, BODY_TOP), "FULL LOOK", font=f['section'], fill=LIGHT)
    photo_top = BODY_TOP + 36

    look_img = imgs.get('look')
    if look_img:
        ow, oh   = look_img.size
        # Scale to fill inner width, then crop height
        scale    = INNER / ow
        lw, lh   = INNER, int(oh * scale)
        resized  = look_img.resize((lw, lh), Image.LANCZOS)
        crop_h   = min(PHOTO_DISPLAY_H, lh)
        cropped  = resized.crop((0, 0, lw, crop_h))
        canvas.paste(cropped, (PAD, photo_top))

        # Subtle overlay labels on photo
        d.text((PAD + lw - 14, photo_top + 14),
               ctx_label.upper(), font=f['section'], fill=WHITE, anchor='rt')
        time_str = now.strftime("%I:%M %p").lstrip("0")
        d.text((PAD + lw - 14, photo_top + 46),
               time_str, font=f['item_brand'], fill=WHITE, anchor='rt')

    photo_bot = photo_top + PHOTO_DISPLAY_H + 24

    # ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    # FLAT LAY GRID â 2 columns, max 4 items
    # ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    d.text((PAD, photo_bot), "FLAT LAY GRID", font=f['section'], fill=LIGHT)
    grid_top = photo_bot + 36

    n    = len(main_p)
    cols = 2
    rows = math.ceil(n / cols) if n else 1

    cx_gap  = 14
    cy_gap  = 16
    cw      = (INNER - (cols - 1) * cx_gap) // cols   # ~473 px
    LABEL_H = 76   # bottom label zone inside each cell

    # Dynamically size rows to fill space between grid_top and RESERVED bottom
    FOOTER_ZONE  = 130   # absolute footer height
    PALETTE_ZONE = 130   # palette section height
    NOTE_ZONE    = 150   # stylist note height (or 30 if no note)
    note_reserve = NOTE_ZONE if stylist_note else 30
    available_h  = H - grid_top - FOOTER_ZONE - PALETTE_ZONE - note_reserve - 20
    ch           = min(480, max(240, (available_h - (rows - 1) * cy_gap) // max(rows, 1)))
    img_area_h   = ch - LABEL_H

    for idx, piece in enumerate(main_p):
        col_i = idx % cols
        row_i = idx // cols
        cx    = PAD + col_i * (cw + cx_gap)
        cy    = grid_top + row_i * (ch + cy_gap)

        # Cell background
        d.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=10, fill=CELL_BG)

        # Product image (square, centred in image area)
        item_img = imgs.get(f'item_{idx}')
        if item_img:
            sz      = min(cw - 20, img_area_h - 12)
            resized = item_img.resize((sz, sz), Image.LANCZOS)
            ix      = cx + (cw - sz) // 2
            iy      = cy + (img_area_h - sz) // 2
            canvas.paste(resized, (ix, iy))

        # Number
        num_str = f"{idx + 1}."
        d.text((cx + 12, cy + img_area_h + 10), num_str, font=f['num'], fill=ACCENT)
        num_w = f['num'].getbbox(num_str)[2]

        # Item name (truncate to fit)
        name_txt = piece.get('name', '')
        max_name_w = cw - num_w - 28
        while name_txt and f['item_name'].getbbox(name_txt)[2] > max_name_w:
            name_txt = name_txt[:-1]
        if name_txt != piece.get('name', ''):
            name_txt = name_txt.rstrip() + 'â¦'
        d.text((cx + 14 + num_w, cy + img_area_h + 12), name_txt,
               font=f['item_name'], fill=DARK)

        # Color Â· brand
        brand_txt  = piece.get('brand', '')
        col_name   = _color_name(piece.get('color', '#888')).title()
        brand_line = f"{col_name}  Â·  {brand_txt}" if brand_txt else col_name
        if f['item_brand'].getbbox(brand_line)[2] > cw - 20:
            brand_line = col_name
        d.text((cx + 12, cy + img_area_h + 12 + 40), brand_line,
               font=f['item_brand'], fill=MID)

    grid_bot = grid_top + rows * (ch + cy_gap) - cy_gap + 28

    # ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    # TODAY'S PALETTE
    # ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    d.text((PAD, grid_bot), "TODAY'S PALETTE", font=f['section'], fill=LIGHT)
    pal_top = grid_bot + 34

    n_sw = max(len(main_p), 1)
    sw   = min(90, (INNER - (n_sw - 1) * 12) // n_sw)
    sh   = 64
    for i, piece in enumerate(main_p):
        sx  = PAD + i * (sw + 12)
        rgb = _hex_rgb(piece.get('color', '#999999'))
        d.rounded_rectangle([sx, pal_top, sx + sw, pal_top + sh], radius=6, fill=rgb)
        cn  = _color_name(piece.get('color', '#888')).title()
        d.text((sx + sw // 2, pal_top + sh + 8), cn,
               font=f['palette_lbl'], fill=LIGHT, anchor='mt')

    pal_bot = pal_top + sh + 38

    # ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    # STYLIST NOTE â prominent, 32px italic
    # ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    note_bot = pal_bot
    if stylist_note:
        d.line([(PAD, pal_bot + 8), (W - PAD, pal_bot + 8)], fill=DIVIDER, width=1)
        note_y     = pal_bot + 26
        note_lines = _wrap(stylist_note, f['note'], INNER)
        lh_n = 44
        for i, line in enumerate(note_lines[:3]):
            d.text((PAD, note_y + i * lh_n), line, font=f['note'], fill=DARK)
        sig_y     = note_y + min(len(note_lines), 3) * lh_n + 10
        d.text((PAD, sig_y), "â Claudio  (Your AI Stylist)", font=f['note_attr'], fill=MID)
        note_bot = sig_y + 38

    # Accessories (compact single line)
    if acc_p:
        parts   = [f"{p.get('name','')} ({p.get('brand','')})" if p.get('brand') else p.get('name','') for p in acc_p]
        acc_str = "Also: " + ", ".join(parts)
        if f['footer_sm'].getbbox(acc_str)[2] > INNER:
            acc_str = acc_str[:int(len(acc_str)*0.8)] + 'â¦'
        d.text((PAD, note_bot + 6), acc_str, font=f['footer_sm'], fill=MID)
        note_bot += 36

    # ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    # FOOTER â pinned to bottom
    # ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
    fy = H - 118
    d.line([(PAD, fy), (W - PAD, fy)], fill=DIVIDER, width=1)
    d.text((PAD, fy + 16),  "BRIAN'S PERSONAL STYLING",
           font=f['footer'],    fill=DARK)
    d.text((PAD, fy + 54),  "Powered by Claudio  Â·  Port Washington, NY",
           font=f['footer_sm'], fill=MID)

    if style_tags:
        tags_str = "  Â·  ".join(t.upper() for t in style_tags[:3])
        d.text((W - PAD, fy + 34), tags_str, font=f['tag'], fill=LIGHT, anchor='rt')

    canvas.save(output_path, 'PNG')
    return output_path
