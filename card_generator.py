"""
Claudio Card Generator
Generates a 1080x1520 editorial style card using PIL/Pillow.
Called by main.py via generate_card(weather, outfit, output_path, context).
"""

import json
import math
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# --- Canvas & Color Palette ---

W, H = 1080, 1520
PAD  = 52

BG         = (247, 245, 240)
DARK       = (26, 26, 26)
MID        = (110, 105, 98)
LIGHT_MID  = (175, 168, 158)
ACCENT     = (139, 115, 85)
DIVIDER    = (212, 204, 190)
WHITE      = (255, 255, 255)

# WMO Weather Code -> condition text
WMO_CONDITIONS = {
    0: "Clear Sky",        1: "Mainly Clear",     2: "Partly Cloudy",  3: "Overcast",
    45: "Fog",             48: "Fog",
    51: "Light Drizzle",   53: "Drizzle",         55: "Heavy Drizzle",
    61: "Light Rain",      63: "Rain",            65: "Heavy Rain",
    71: "Light Snow",      73: "Snow",            75: "Heavy Snow",    77: "Snow Grains",
    80: "Light Showers",   81: "Showers",         82: "Heavy Showers",
    85: "Snow Showers",    86: "Heavy Snow Showers",
    95: "Thunderstorm",    96: "Thunderstorm + Hail", 99: "Severe Thunderstorm",
}

# --- Font Loading ---

def _load_font(paths, size):
    for p in paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()

def _load_fonts():
    serif      = ["/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"]
    serif_bold = ["/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"]
    serif_ital = ["/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"]
    sans       = ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    sans_bold  = ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]

    return {
        "outfit_name":    _load_font(serif_bold,  54),
        "header_brand":   _load_font(serif_bold,  40),
        "header_sub":     _load_font(sans_bold,   15),
        "weather_temp":   _load_font(sans_bold,   46),
        "weather_detail": _load_font(sans,        18),
        "label_caps":     _load_font(sans_bold,   13),
        "item_name":      _load_font(sans_bold,   16),
        "item_brand":     _load_font(sans,        13),
        "description":    _load_font(sans,        21),
        "stylist_note":   _load_font(serif_ital,  25),
        "stylist_label":  _load_font(sans_bold,   13),
        "footer_tag":     _load_font(sans,        18),
        "footer_tiny":    _load_font(sans,        13),
        "section_label":  _load_font(sans_bold,   12),
    }

# --- Color Utilities ---

def _hex_to_rgb(hex_color):
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _luminance(rgb):
    r, g, b = [x / 255.0 for x in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def _contrast_color(rgb):
    return (245, 242, 238) if _luminance(rgb) < 0.45 else DARK

# --- Swatch Rendering ---

def _make_fabric_swatch(width, height, color_hex):
    base_color = _hex_to_rgb(color_hex)
    swatch = Image.new('RGBA', (width, height), base_color + (255,))
    draw   = ImageDraw.Draw(swatch)
    for i in range(height // 3):
        alpha = int(28 * (1 - i / (height / 3)))
        draw.line([(0, i), (width, i)], fill=(255, 255, 255, alpha))
    shadow_start = int(height * 0.72)
    for i in range(shadow_start, height):
        alpha = int(16 * (i - shadow_start) / (height - shadow_start))
        draw.line([(0, i), (width, i)], fill=(0, 0, 0, alpha))
    draw.line([(3, 1), (width - 3, 1)], fill=(255, 255, 255, 70), width=1)
    draw.line([(3, 2), (width - 3, 2)], fill=(255, 255, 255, 35), width=1)
    return swatch


def _draw_swatch_cell(img, draw, fonts, x, y, cell_w, cell_h, piece):
    color_hex = piece.get('color', '#8A8A8A')
    category  = piece.get('category', '').upper()
    item_name = piece.get('name', '')
    brand     = piece.get('brand', '')

    label_h  = 22
    name_h   = 42
    swatch_h = cell_h - label_h - name_h
    swatch_w = cell_w
    swatch_y = y + label_h

    draw.text((x + swatch_w // 2, y + 12), category,
              font=fonts['section_label'], fill=LIGHT_MID, anchor='mm')

    swatch_img = _make_fabric_swatch(swatch_w, swatch_h, color_hex)
    mask = Image.new('L', (swatch_w, swatch_h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, swatch_w, swatch_h], radius=7, fill=255)
    img.paste(swatch_img.convert('RGB'), (x, swatch_y), mask)
    draw.rounded_rectangle([x, swatch_y, x + swatch_w, swatch_y + swatch_h],
                            radius=7, outline=DIVIDER, width=1)

    name_display = item_name if len(item_name) <= 20 else item_name[:17] + "..."
    draw.text((x + swatch_w // 2, swatch_y + swatch_h + 12), name_display,
              font=fonts['item_name'], fill=DARK, anchor='mm')
    draw.text((x + swatch_w // 2, swatch_y + swatch_h + 30), brand.upper(),
              font=fonts['item_brand'], fill=ACCENT, anchor='mm')

# --- Look Composition ---

LOOK_PROPORTIONS = {
    'OUTERWEAR':   {'h': 0.255, 'w': 0.85},
    'LAYER':       {'h': 0.200, 'w': 0.72},
    'SHIRT':       {'h': 0.215, 'w': 0.72},
    'PANTS':       {'h': 0.275, 'w': 0.56},
    'SHOES':       {'h': 0.155, 'w': 0.68},
    'ACCESSORIES': {'h': 0.100, 'w': 0.50},
    'BELT':        {'h': 0.055, 'w': 0.70},
    'SCARF':       {'h': 0.100, 'w': 0.60},
}

LOOK_ORDER = ['OUTERWEAR', 'LAYER', 'SHIRT', 'PANTS', 'SHOES', 'ACCESSORIES', 'BELT', 'SCARF']


def _render_look_composition(img, draw, fonts, x, y, panel_w, panel_h, pieces):
    piece_by_cat = {p['category'].upper(): p for p in pieces}
    ordered = [piece_by_cat[cat] for cat in LOOK_ORDER if cat in piece_by_cat]
    if not ordered:
        return

    n            = len(ordered)
    gap          = 12
    label_h      = 16
    total_weight = sum(LOOK_PROPORTIONS.get(p['category'].upper(), {'h': 0.18})['h'] for p in ordered)
    available_h  = panel_h - (n - 1) * (gap + label_h) - label_h - 16
    current_y    = y + 10

    for piece in ordered:
        cat   = piece['category'].upper()
        props = LOOK_PROPORTIONS.get(cat, {'h': 0.18, 'w': 0.70})
        p_h   = int(available_h * props['h'] / total_weight)
        p_w   = min(int(panel_w * props['w']), int(p_h * 2.5))
        p_x   = x + (panel_w - p_w) // 2

        color_hex  = piece.get('color', '#8A8A8A')
        swatch_img = _make_fabric_swatch(p_w, p_h, color_hex)
        mask       = Image.new('L', (p_w, p_h), 0)
        mask_draw  = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([0, 0, p_w, p_h], radius=8, fill=255)
        img.paste(swatch_img.convert('RGB'), (p_x, current_y), mask)
        draw.rounded_rectangle([p_x, current_y, p_x + p_w, current_y + p_h],
                                radius=8, outline=DIVIDER, width=1)

        text_color   = _contrast_color(_hex_to_rgb(color_hex))
        draw.text((p_x + 9, current_y + p_h - 9), cat,
                  font=fonts['section_label'], fill=text_color + (150,), anchor='lm')

        name_display = piece.get('name', '')
        if len(name_display) > 26:
            name_display = name_display[:23] + "..."
        draw.text((p_x + p_w // 2, current_y + p_h + 10), name_display,
                  font=fonts['footer_tiny'], fill=MID, anchor='mm')

        current_y += p_h + gap + label_h

# --- Word Wrap ---

def _wrap_text(text, font, max_width):
    words   = text.split()
    lines   = []
    current = []
    for word in words:
        test = ' '.join(current + [word])
        if font.getlength(test) <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(' '.join(current))
            current = [word]
    if current:
        lines.append(' '.join(current))
    return lines

# --- Main Entry Point ---

def generate_card(weather: dict, outfit: dict, output_path: str, context: str = "office") -> str:
    """Render the full Claudio style card and save as PNG. Returns output_path."""

    img  = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(img, 'RGBA')
    f    = _load_fonts()

    now      = datetime.now()
    day_str  = now.strftime("%A").upper()
    date_str = now.strftime("%B %-d").upper()
    year_str = now.strftime("%Y")

    temp        = int(round(float(weather.get('current_temp', 55))))
    high        = int(round(float(weather.get('high', 60))))
    low         = int(round(float(weather.get('low', 45))))
    wind        = int(round(float(weather.get('wind', 10))))
    rain_prob   = int(round(float(weather.get('rain_prob', 0))))
    weathercode = int(weather.get('weathercode', 0))
    condition   = WMO_CONDITIONS.get(weathercode, weather.get('condition', 'Clear'))

    # HEADER (y: 0 -> 142)
    draw.text((PAD, 36),      "BRIAN'S",   font=f['header_sub'],   fill=ACCENT, anchor='lm')
    draw.text((PAD, 80),      "Claudio", font=f['header_brand'], fill=DARK,   anchor='lm')
    draw.text((W - PAD, 36),  day_str,     font=f['header_sub'],   fill=MID,        anchor='rm')
    draw.text((W - PAD, 80),  date_str,    font=f['header_brand'], fill=DARK,        anchor='rm')
    draw.text((W - PAD, 108), year_str,    font=f['item_brand'],   fill=LIGHT_MID,  anchor='rm')
    draw.line([(PAD, 128), (W - PAD, 128)], fill=DIVIDER, width=1)

    # WEATHER BAR (y: 133 -> 238)
    wy = 188
    draw.text((PAD, wy), f"{temp}F", font=f['weather_temp'], fill=DARK, anchor='lm')
    temp_w = int(f['weather_temp'].getlength(f"{temp}F"))
    draw.text((PAD + temp_w + 14, wy - 13), f"H {high}", font=f['weather_detail'], fill=MID, anchor='lm')
    draw.text((PAD + temp_w + 14, wy + 7),  f"L {low}",  font=f['weather_detail'], fill=MID, anchor='lm')
    hl_w = int(f['weather_detail'].getlength(f"H {high}"))
    cx = PAD + temp_w + 14 + hl_w + 20
    draw.text((cx, wy - 13), condition,                          font=f['weather_detail'], fill=MID,       anchor='lm')
    draw.text((cx, wy + 7),  f"Wind {wind} mph  Rain {rain_prob}%", font=f['item_brand'],    fill=LIGHT_MID, anchor='lm')

    ctx_labels = {'office': 'OFFICE DAY', 'weekend': 'WEEKEND',
                  'date_night': 'DATE NIGHT', 'family_outing': 'FAMILY DAY'}
    badge_text = ctx_labels.get(context, 'TODAY')
    bw = int(f['label_caps'].getlength(badge_text)) + 28
    bx = W - PAD - bw
    by = wy - 18
    draw.rounded_rectangle([bx, by, bx + bw, by + 32], radius=5, fill=ACCENT)
    draw.text((bx + bw // 2, by + 16), badge_text, font=f['label_caps'], fill=WHITE, anchor='mm')
    draw.line([(PAD, 235), (W - PAD, 235)], fill=DIVIDER, width=1)

    # OUTFIT TITLE (y: 240 -> 348)
    outfit_name = outfit.get('name', 'The Edit')
    outfit_desc = outfit.get('description', '')
    draw.text((PAD, 275), outfit_name, font=f['outfit_name'],  fill=DARK, anchor='lm')
    draw.text((PAD, 330), outfit_desc, font=f['description'],  fill=MID,  anchor='lm')
    draw.line([(PAD, 352), (W - PAD, 352)], fill=DIVIDER, width=1)

    # MAIN PANEL (y: 358 -> 1158)
    PANEL_TOP    = 360
    PANEL_BOTTOM = 1158
    PANEL_H      = PANEL_BOTTOM - PANEL_TOP
    MID_X        = W // 2

    draw.text((MID_X // 2, PANEL_TOP + 24), "THE PIECES",
              font=f['section_label'], fill=LIGHT_MID, anchor='mm')
    draw.text((MID_X + (W - MID_X) // 2, PANEL_TOP + 24), "THE LOOK",
              font=f['section_label'], fill=LIGHT_MID, anchor='mm')
    draw.line([(MID_X, PANEL_TOP + 8), (MID_X, PANEL_BOTTOM - 8)], fill=DIVIDER, width=1)

    pieces = outfit.get('pieces', [])

    GRID_TOP    = PANEL_TOP + 48
    GRID_H      = PANEL_H - 48
    LEFT_PAD    = PAD
    LEFT_END    = MID_X - 20
    GRID_W      = LEFT_END - LEFT_PAD
    COL_GAP     = 16
    COL_W       = (GRID_W - COL_GAP) // 2
    max_rows    = 3
    n_pieces    = min(len(pieces), max_rows * 2)
    actual_rows = math.ceil(n_pieces / 2) if n_pieces else 1
    ROW_GAP     = 14
    CELL_H      = (GRID_H - ROW_GAP * (actual_rows - 1)) // max_rows

    for i, piece in enumerate(pieces[:6]):
        col    = i % 2
        row    = i // 2
        cell_x = LEFT_PAD + col * (COL_W + COL_GAP)
        cell_y = GRID_TOP + row * (CELL_H + ROW_GAP)
        _draw_swatch_cell(img, draw, f, cell_x, cell_y, COL_W, CELL_H, piece)

    RIGHT_PAD_L = MID_X + 24
    RIGHT_PAD_R = W - PAD
    RIGHT_W     = RIGHT_PAD_R - RIGHT_PAD_L
    RIGHT_TOP   = PANEL_TOP + 48
    _render_look_composition(img, draw, f, RIGHT_PAD_L, RIGHT_TOP, RIGHT_W, PANEL_H - 56, pieces)
    draw.line([(PAD, PANEL_BOTTOM), (W - PAD, PANEL_BOTTOM)], fill=DIVIDER, width=1)

    # STYLIST NOTE (y: 1163 -> 1388)
    NOTE_TOP = 1168
    draw.text((PAD, NOTE_TOP + 18), "STYLIST NOTE", font=f['stylist_label'], fill=ACCENT, anchor='lm')
    lbl_w = int(f['stylist_label'].getlength("STYLIST NOTE"))
    draw.ellipse([PAD + lbl_w + 8, NOTE_TOP + 14, PAD + lbl_w + 15, NOTE_TOP + 21], fill=ACCENT)

    note_text  = outfit.get('stylist_note', '')
    note_lines = _wrap_text(note_text, f['stylist_note'], W - PAD * 2)
    note_y     = NOTE_TOP + 52
    for line in note_lines[:6]:
        draw.text((PAD, note_y), line, font=f['stylist_note'], fill=DARK, anchor='lm')
        note_y += 36
    draw.line([(PAD, 1440), (W - PAD, 1440)], fill=DIVIDER, width=1)

    # FOOTER (y: 1445 -> 1520)
    style_tags = outfit.get('style_tags', ['Smart Casual', 'Classic Preppy'])
    tag_text   = "  .  ".join(style_tags)
    draw.text((W // 2, 1470), tag_text,
              font=f['footer_tag'], fill=MID, anchor='mm')
    draw.text((W // 2, 1502), "Claudio  .  Port Washington, NY",
              font=f['footer_tiny'], fill=LIGHT_MID, anchor='mm')

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, 'PNG')
    return output_path
