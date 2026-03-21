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
        'headline':    _lf(sb, 64),
        'name':        _lf(xb, 52),
        'sub':         _lf(sr, 42),
        'meta_k':      _lf(sb, 42),
        'meta_v':      _lf(sr, 42),
        'weather':     _lf(sb, 72),
        'section':     _lf(sb, 62),
        'num':         _lf(sb, 76),
        'item_name':   _lf(sb, 88),
        'item_brand':  _lf(sr, 64),
        'note':        _lf(si, 72),
        'note_attr':   _lf(sr, 60),
        'footer':      _lf(sb, 38),
        'footer_sm':   _lf(sr, 36),
        'tag':         _lf(sr, 36),
        'palette_lbl': _lf(sr, 60),
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
    Claudio Card v5 - split layout.
    No header, no footer.
    LEFT: weather strip + 2x2 items grid + palette
    RIGHT: full portrait (no crop)
    BOTTOM: stylist note
    """
    now      = datetime.now()
    day_str  = now.strftime("%A").upper()
    date_str = now.strftime("%B %d, %Y").upper()

    f    = _load_fonts()
    imgs = _generate_all_images(outfit, context, weather)

    main_p = imgs.pop('_main_pieces', [])
    ACC_CATS = {'ACCESSORIES', 'BELT', 'SCARF', 'WATCH'}

    canvas = Image.new('RGB', (W, H), BG)
    d      = ImageDraw.Draw(canvas)

    # -- Weather / outfit data -------------------------------------------------
    wmo_code   = weather.get('weathercode', 0)
    # Accept Open-Meteo format (temperature_2m in C) or scheduled task format (current_temp/temp_f in F)
    if 'temp_f' in weather:
        temp_f = round(float(weather['temp_f']))
    elif 'current_temp' in weather:
        temp_f = round(float(weather['current_temp']))
    else:
        temp_c = weather.get('temperature_2m', 20)
        temp_f = round(temp_c * 9 / 5 + 32)
    if 'wind' in weather:
        wind_mph = round(float(weather['wind']))
    else:
        wind_kph = weather.get('windspeed_10m', 0)
        wind_mph = round(wind_kph * 0.621)
    precip_pct = round(weather.get('precipitation_probability', weather.get('rain_prob', 0)))
    emoji      = WMO_EMOJI.get(wmo_code, '\u2600')
    condition  = WMO.get(wmo_code, 'Clear')
    rain_str   = f'  \u00b7  {precip_pct}% rain' if precip_pct > 10 else ''
    outfit_name  = outfit.get('name', "Today's Look")
    stylist_note = outfit.get('stylist_note', outfit.get('note', ''))

    # -- TOP WEATHER STRIP -----------------------------------------------------
    STRIP_Y = 46
    wx_str  = f"{temp_f}\u00b0F  \u00b7  {condition}  \u00b7  Wind {wind_mph} mph{rain_str}"
    d.text((PAD, STRIP_Y), wx_str,        font=f['weather'], fill=DARK)
    d.text((W - PAD, STRIP_Y), date_str,  font=f['weather'], fill=MID, anchor='rt')

    wh        = f['weather'].getbbox(wx_str)[3]
    strip_bot = STRIP_Y + wh + 26
    d.line([(PAD, strip_bot), (W - PAD, strip_bot)], fill=DIVIDER, width=2)
    BODY_TOP  = strip_bot + 34

    # -- COLUMN CONSTANTS ------------------------------------------------------
    LEFT_W  = 460
    COL_GAP = 28
    RIGHT_X = PAD + LEFT_W + COL_GAP   # 548
    RIGHT_W = W - RIGHT_X - PAD        # 472

    # -- RIGHT: PORTRAIT (full height, no crop) --------------------------------
    look_img = imgs.get('look')
    portrait_bot = BODY_TOP
    if look_img:
        lw, lh      = look_img.size
        scale       = RIGHT_W / lw
        new_ph      = int(lh * scale)
        look_scaled = look_img.resize((RIGHT_W, new_ph), Image.LANCZOS)
        canvas.paste(look_scaled, (RIGHT_X, BODY_TOP))
        portrait_bot = BODY_TOP + new_ph

    # Outfit name + context below portrait
    ctx_label = 'WEEKEND' if 'weekend' in context.lower() else 'OFFICE'
    tag_y = portrait_bot + 22
    d.text((RIGHT_X, tag_y),      outfit_name, font=f['item_name'], fill=DARK)
    d.text((RIGHT_X, tag_y + 64), ctx_label,   font=f['section'],   fill=ACCENT)

    # -- LEFT: 2x2 ITEM GRID ---------------------------------------------------
    n      = len(main_p)
    COLS   = 2
    CX_GAP = 16
    CW     = (LEFT_W - CX_GAP) // 2      # ~222px per cell
    IMG_H  = int(CW * 1.28)              # ~284px image area
    NAME_H  = 108
    BRAND_H = 80
    CH     = IMG_H + NAME_H + BRAND_H + 20
    CY_GAP = 18
    ROWS   = math.ceil(n / COLS) if n else 1

    grid_top = BODY_TOP

    for i, piece in enumerate(main_p):
        row = i // COLS
        col = i % COLS
        cx  = PAD + col * (CW + CX_GAP)
        cy  = grid_top + row * (CH + CY_GAP)

        d.rounded_rectangle([cx, cy, cx + CW, cy + CH], radius=10, fill=CELL_BG)

        item_img = imgs.get(f'item_{i}')
        if item_img:
            iw, ih = item_img.size
            sc     = min(CW / iw, IMG_H / ih)
            nw, nh = int(iw * sc), int(ih * sc)
            itm    = item_img.resize((nw, nh), Image.LANCZOS)
            canvas.paste(itm, (cx + (CW - nw) // 2, cy + (IMG_H - nh) // 2))

        label_top = cy + IMG_H + 8

        num_str = str(i + 1)
        d.text((cx + 10, label_top), num_str, font=f['num'], fill=ACCENT)
        num_w = f['num'].getbbox(num_str)[2]

        name_txt = piece.get('name', '')
        avail_w  = CW - num_w - 22
        while name_txt and f['item_name'].getbbox(name_txt)[2] > avail_w:
            name_txt = name_txt[:-1]
        if name_txt != piece.get('name', ''):
            name_txt = name_txt.rstrip() + '\u2026'
        d.text((cx + 14 + num_w, label_top), name_txt, font=f['item_name'], fill=DARK)

        col_nm    = _color_name(piece.get('color', '#888')).title()
        brand_txt = piece.get('brand', '')
        bl        = f"{col_nm}  \u00b7  {brand_txt}" if brand_txt else col_nm
        if f['item_brand'].getbbox(bl)[2] > CW - 16:
            bl = col_nm
        d.text((cx + 12, label_top + NAME_H), bl, font=f['item_brand'], fill=MID)

    grid_bot = grid_top + ROWS * CH + (ROWS - 1) * CY_GAP

    # -- PALETTE (full width, below both columns) ------------------------------
    SPLIT_BOT   = max(grid_bot, portrait_bot) + 50
    d.line([(PAD, SPLIT_BOT), (W - PAD, SPLIT_BOT)], fill=DIVIDER, width=2)
    PALETTE_TOP = SPLIT_BOT + 32

    n_sw = max(len(main_p), 1)
    sw   = min(140, (INNER - (n_sw - 1) * 18) // n_sw)
    sh   = 72
    for i, piece in enumerate(main_p):
        sx  = PAD + i * (sw + 18)
        rgb = _hex_rgb(piece.get('color', '#999999'))
        d.rounded_rectangle([sx, PALETTE_TOP, sx + sw, PALETTE_TOP + sh], radius=8, fill=rgb)
        cn  = _color_name(piece.get('color', '#888')).title()
        d.text((sx + sw // 2, PALETTE_TOP + sh + 10), cn,
               font=f['palette_lbl'], fill=LIGHT, anchor='mt')

    pal_bot = PALETTE_TOP + sh + 56

    # -- STYLIST NOTE ----------------------------------------------------------
    if stylist_note:
        d.line([(PAD, pal_bot), (W - PAD, pal_bot)], fill=DIVIDER, width=1)
        note_y = pal_bot + 30
        lh_n   = 88
        lines  = _wrap(stylist_note, f['note'], INNER)
        for line in lines[:3]:
            d.text((PAD, note_y), line, font=f['note'], fill=DARK)
            note_y += lh_n
        d.text((PAD, note_y + 10), "\u2014 Claudio  (Your AI Stylist)",
               font=f['note_attr'], fill=MID)

    canvas.save(output_path, 'PNG')
    return output_path
