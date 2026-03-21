#!/usr/bin/env python3
"""
Claudio Card Generator v4
Phone-optimised: 1080ÃÂÃÂ1920 (9:16), minimum 28px body text, stacked layout.
Layout: header ÃÂ¢ÃÂÃÂ full-width editorial portrait ÃÂ¢ÃÂÃÂ 2-col flat-lay grid ÃÂ¢ÃÂÃÂ palette ÃÂ¢ÃÂÃÂ note ÃÂ¢ÃÂÃÂ footer.
Context-aware: loads claudio_context.md to personalise DALL-E prompts.
"""

import os, io, re, math, concurrent.futures, time as _time
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import httpx
from openai import OpenAI

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Context File ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
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

    print(f"[ctx] Loaded context ÃÂ¢ÃÂÃÂ subject: {_CTX_CACHE['subject']}")
    _CTX_LOAD_TIME = _time.time()
    return _CTX_CACHE


# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Canvas ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
W, H   = 1080, 1920
PHONE_W = 390        # Target phone display width — fonts sized in phone-px
_S      = W / PHONE_W  # Scale factor (~2.77 × ): canvas px per phone px
PAD    = 60
INNER  = W - 2 * PAD        # 960px usable width

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Palette ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
BG      = (255, 255, 255)
DARK    = (18,  18,  18 )
MID     = (100, 94,  86 )
LIGHT   = (158, 150, 140)
DIVIDER = (218, 212, 204)
ACCENT  = (139, 115, 85 )
WHITE   = (255, 255, 255)
CELL_BG = (248, 246, 242)

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ WMO Weather Codes ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
WMO = {
    0:"Clear Sky", 1:"Mainly Clear", 2:"Partly Cloudy", 3:"Overcast",
    45:"Fog", 48:"Fog", 51:"Drizzle", 53:"Drizzle", 55:"Drizzle",
    61:"Light Rain", 63:"Rain", 65:"Heavy Rain",
    71:"Light Snow", 73:"Snow", 75:"Heavy Snow", 77:"Snow Grains",
    80:"Showers", 81:"Showers", 82:"Heavy Showers",
    95:"Thunderstorm", 96:"Thunderstorm", 99:"Thunderstorm",
}
WMO_EMOJI = {
    0:"ÃÂ¢ÃÂÃÂ",  1:"ÃÂ°ÃÂÃÂÃÂ¤", 2:"ÃÂ¢ÃÂÃÂ", 3:"ÃÂ¢ÃÂÃÂ",
    45:"ÃÂ°ÃÂÃÂÃÂ«", 48:"ÃÂ°ÃÂÃÂÃÂ«", 51:"ÃÂ°ÃÂÃÂÃÂ¦", 53:"ÃÂ°ÃÂÃÂÃÂ¦", 55:"ÃÂ°ÃÂÃÂÃÂ§",
    61:"ÃÂ°ÃÂÃÂÃÂ¦", 63:"ÃÂ°ÃÂÃÂÃÂ§", 65:"ÃÂ°ÃÂÃÂÃÂ§",
    71:"ÃÂ°ÃÂÃÂÃÂ¨", 73:"ÃÂ¢ÃÂÃÂ", 75:"ÃÂ¢ÃÂÃÂ",  77:"ÃÂ¢ÃÂÃÂ",
    80:"ÃÂ°ÃÂÃÂÃÂ¦", 81:"ÃÂ°ÃÂÃÂÃÂ§", 82:"ÃÂ¢ÃÂÃÂ",
    95:"ÃÂ¢ÃÂÃÂ", 96:"ÃÂ¢ÃÂÃÂ", 99:"ÃÂ¢ÃÂÃÂ",
}

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Fonts ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ
FONTS_DIR = Path(__file__).parent / "fonts"

def _lf(paths, size):
    for p in paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default()

def _lf_px(paths, phone_px):
    """Load font sized to render as phone_px on a ~390px-wide phone screen."""
    return _lf(paths, round(phone_px * _S))

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
        'headline':    _lf_px(sb, 24),
        'name':        _lf_px(xb, 22),
        'sub':         _lf_px(sr, 18),
        'meta_k':      _lf_px(sb, 18),
        'meta_v':      _lf_px(sr, 18),
        'weather':     _lf_px(sb, 26),
        'section':     _lf_px(sb, 22),
        'num':         _lf_px(sb, 28),
        'item_name':   _lf_px(sb, 32),
        'item_brand':  _lf_px(sr, 22),
        'note':        _lf_px(si, 24),
        'note_attr':   _lf_px(sr, 18),
        'footer':      _lf_px(sb, 18),
        'footer_sm':   _lf_px(sr, 16),
        'tag':         _lf_px(sr, 16),
        'palette_lbl': _lf_px(sr, 18),
    }

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Color Utilities ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

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

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Text Utility ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

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

# ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ Image Generation ÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂÃÂ¢ÃÂÃÂ

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
    """E-commerce product photography ÃÂ¢ÃÂÃÂ clean white background, no AI gloss."""
    col  = _color_name(piece.get('color', '#888888'))
    mat  = piece.get('material', '')
    name = piece.get('name', 'clothing item')
    mat_str = f"{mat} " if mat else ""
    prompt = (
        f"Flat lay product photo on a pure white surface. A single {col} {mat_str}{name} "
        f"placed flat on a white background, photographed from directly above. "
        f"Clean and minimal: just the garment lying flat on white, nothing else. "
        f"No people, no mannequins, no hangers, no studio equipment, no lighting stands, "
        f"no backdrops, no props, no shadows, no brand logos, no text. "
        f"Natural fabric texture: matte fabrics look matte, suede looks like suede, leather shows grain. "
        f"Photorealistic, 8K detail, e-commerce flat-lay style."
    )
    resp = client.images.generate(
        model="dall-e-3", prompt=prompt,
        size="1024x1024", quality="hd", n=1
    )
    return _fetch(resp.data[0].url)

def _gen_look_image(outfit, context, weather, client):
    """Realistic portrait of Brian wearing the outfit — clean white background."""
    pieces = outfit.get('pieces', [])
    descs  = []
    for p in pieces:
        col  = p.get('color_name', '') or _color_name(p.get('color', '#888888'))
        name = p.get('name', '')
        descs.append(f"{col} {name}".strip())
    outfit_str = ", ".join(descs) if descs else "casual outfit"

    prompt = (
        f"A realistic photo of a 37-year-old man with short brown hair, green eyes, and an athletic build. "
        f"He is wearing: {outfit_str}. "
        f"Simple clean off-white background. Natural relaxed standing posture, slight smile, looking at camera. "
        f"Catalog photography style — well-lit, natural, not dramatic. "
        f"Realistic proportions: average height, athletic but not exaggerated build. "
        f"Natural skin texture, realistic fabric drape. "
        f"The look of a confident, well-dressed dad in his late 30s. "
        f"No dramatic lighting, no outdoor backgrounds, no fashion editorial styling. "
        f"Photorealistic, high quality, clean and simple."
    )
    resp = client.images.generate(
        model="dall-e-3", prompt=prompt,
        size="1024x1792", quality="hd", n=1
    )
    return _fetch(resp.data[0].url)

def _generate_all_images(outfit, context, weather):
    """Generate images. Uses pre-provided image_url per piece when available; DALL-E only for portrait."""
    c = _client()
    ACC_CATS = {'ACCESSORIES', 'BELT', 'SCARF', 'WATCH'}
    all_pieces  = outfit.get('pieces', [])
    main_pieces = [p for p in all_pieces if p.get('category', '').upper() not in ACC_CATS][:4]
    results     = {'_main_pieces': main_pieces}

    def _load_piece_image(piece, idx):
        """Download from image_url if provided, else generate via DALL-E."""
        url = piece.get('image_url')
        if url:
            try:
                resp = httpx.get(url, timeout=30, follow_redirects=True)
                resp.raise_for_status()
                return Image.open(io.BytesIO(resp.content)).convert('RGB')
            except Exception as e:
                print(f"[warn] image_url fetch failed for piece {idx}: {e}")
        # Fallback: DALL-E generation
        return _gen_item_image(piece, c)

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        item_futs = {ex.submit(_load_piece_image, p, i): i for i, p in enumerate(main_pieces)}
        look_fut  = ex.submit(_gen_look_image, outfit, context, weather, c)

        for fut, idx in item_futs.items():
            try:
                results[f'item_{idx}'] = fut.result(timeout=60)
            except Exception as e:
                print(f"[warn] item {idx} image failed: {e}")
                rgb = _hex_rgb(main_pieces[idx].get('color', '#999999'))
                results[f'item_{idx}'] = Image.new('RGB', (512, 512), rgb)

        try:
            results['look'] = look_fut.result(timeout=120)
        except Exception as e:
            print(f"[warn] look image failed: {e}")
            results['look'] = Image.new('RGB', (512, 900), (240, 238, 234))

    return results

def generate_card(weather: dict, outfit: dict, output_path: str, context: str = "office") -> str:
    """
    Claudio Card v6 — simplified.
    LEFT:   2x2 item grid (images + name + brand)
    RIGHT:  full portrait
    BOTTOM: STYLIST TIP (large, fully wrapped)
    No weather strip, no labels, no palette, no branding.
    """
    f      = _load_fonts()
    imgs   = _generate_all_images(outfit, context, weather)
    main_p = imgs.pop('_main_pieces', [])

    canvas = Image.new('RGB', (W, H), BG)
    d      = ImageDraw.Draw(canvas)

    stylist_note = outfit.get('stylist_note', outfit.get('note', ''))

    # -- COLUMN CONSTANTS -------------------------------------------------------
    PAD      = 48
    LEFT_W   = 460
    COL_GAP  = 28
    RIGHT_X  = PAD + LEFT_W + COL_GAP   # 536
    RIGHT_W  = W - RIGHT_X - PAD        # 484
    INNER    = W - 2 * PAD              # 984
    BODY_TOP = PAD                       # no weather strip — start at top

    # -- RIGHT: PORTRAIT --------------------------------------------------------
    look_img = imgs.get('look')
    portrait_bot = BODY_TOP
    if look_img:
        lw, lh  = look_img.size
        scale   = RIGHT_W / lw
        new_pw  = RIGHT_W
        new_ph  = int(lh * scale)
        portrait = look_img.resize((new_pw, new_ph), Image.LANCZOS)
        canvas.paste(portrait, (RIGHT_X, BODY_TOP))
        portrait_bot = BODY_TOP + new_ph

    # -- LEFT: 2x2 ITEM GRID ----------------------------------------------------
    COLS    = 2
    CX_GAP  = 16
    CW      = (LEFT_W - CX_GAP) // 2    # 222 px
    IMG_H   = int(CW * 1.28)            # 284 px
    NAME_H  = round(32 * _S)            # ~89 px  (32 phone-px)
    BRAND_H = round(22 * _S)            # ~61 px  (22 phone-px)
    CH      = IMG_H + NAME_H + BRAND_H + 28
    CY_GAP  = 18
    n       = len(main_p)
    ROWS    = math.ceil(n / COLS) if n else 1

    for i, piece in enumerate(main_p):
        row = i // COLS
        col = i % COLS
        cx  = PAD + col * (CW + CX_GAP)
        cy  = BODY_TOP + row * (CH + CY_GAP)

        d.rounded_rectangle([cx, cy, cx + CW, cy + CH], radius=10, fill=CELL_BG)

        item_img = imgs.get(f'item_{i}')
        if item_img:
            iw, ih = item_img.size
            sc     = min(CW / iw, IMG_H / ih)
            nw, nh = int(iw * sc), int(ih * sc)
            itm    = item_img.resize((nw, nh), Image.LANCZOS)
            canvas.paste(itm, (cx + (CW - nw) // 2, cy + (IMG_H - nh) // 2))

        label_top = cy + IMG_H + 10

        # Item name — truncate to fit cell width
        name_txt = piece.get('name', '')
        avail_w  = CW - 14
        while name_txt and f['item_name'].getbbox(name_txt)[2] > avail_w:
            name_txt = name_txt[:-1]
        if name_txt != piece.get('name', ''):
            name_txt = name_txt.rstrip() + '\u2026'
        d.text((cx + 10, label_top), name_txt, font=f['item_name'], fill=DARK)

        # Brand + colour
        brand_txt = piece.get('brand', '')
        col_nm    = piece.get('color_name', _color_name(piece.get('color', '#888'))).title()
        bl        = f"{col_nm}  \u00b7  {brand_txt}" if brand_txt else col_nm
        if f['item_brand'].getbbox(bl)[2] > CW - 16:
            bl = brand_txt
        d.text((cx + 12, label_top + NAME_H + 6), bl, font=f['item_brand'], fill=MID)

    grid_bot = BODY_TOP + ROWS * CH + (ROWS - 1) * CY_GAP

    # -- DIVIDER ----------------------------------------------------------------
    SPLIT_BOT = max(grid_bot, portrait_bot) + 60
    d.line([(PAD, SPLIT_BOT), (W - PAD, SPLIT_BOT)], fill=DIVIDER, width=2)

    # -- STYLIST TIP ------------------------------------------------------------
    tip_y = SPLIT_BOT + 48
    d.text((PAD, tip_y), 'STYLIST TIP', font=f['section'], fill=ACCENT)

    note_y  = tip_y + round(22 * _S * 1.6)   # section line height + spacing
    note_lh = round(24 * _S * 1.5)            # 24 phone-px × line-height 1.5
    if stylist_note:
        for line in _wrap(stylist_note, f['note'], INNER):
            d.text((PAD, note_y), line, font=f['note'], fill=DARK)
            note_y += note_lh

    canvas.save(output_path, 'PNG')
    return output_path
