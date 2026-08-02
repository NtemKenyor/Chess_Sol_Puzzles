"""
content_engine.py
──────────────────────────────────────────────────────────────────────────
Shared "growth engine" for ChessSol video generation & posting.

This module exists because of one core lesson: the FB/IG algorithm doesn't
reward *volume*, it rewards videos that *look different from your last one*
and *hook viewers in the first 2 seconds*. Randomizing caption locations
("🇮🇳 🇷🇺 🇳🇴") does nothing for reach — it isn't a real ranking signal — so
none of that is here. What IS here:

  1. Visual variety      -> board theme / font style / arrow colors / zoom,
                             guaranteed to never repeat back-to-back
  2. Strong hooks         -> 2-second attention-grabbing opener card
  3. Difficulty mix       -> Easy/Medium/Hard/Expert/Impossible badge system
  4. Weekly content series-> different puzzle focus per weekday
  5. Audio variety        -> rotates through whatever files you drop in the
                             intro/music/click folders
  6. A/B-test logging     -> every render's full "recipe" is appended to a
                             CSV so that after N uploads you can join it to
                             FB Insights and see what actually drives views
  7. Retention pacing     -> countdown length & style varies per video
  8. Community CTAs       -> rotating comment-bait lines
  9. Randomized posting delay
 10. No-consecutive-repeat guard (backed by a tiny JSON state file)
"""

import os
import csv
import json
import random
import time
import datetime

STATE_FILE = "content_state.json"
ANALYTICS_FILE = "analytics_log.csv"


# ═══════════════════════════════════════════════════════════════════════
#  0. NO-CONSECUTIVE-REPEAT ENGINE
# ═══════════════════════════════════════════════════════════════════════
def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[state] Could not save state: {e}")


_STATE = _load_state()


def pick_unique(category, options):
    """
    Choose a random option from `options`, guaranteed to differ from the
    last choice made for this `category` (across runs, via STATE_FILE).
    Falls back to a plain random.choice if the category only has 1 option.
    """
    if not options:
        return None
    last = _STATE.get(category)
    pool = [o for o in options if _key(o) != last] or list(options)
    choice = random.choice(pool)
    _STATE[category] = _key(choice)
    _save_state(_STATE)
    return choice


def _key(option):
    """A hashable/JSON-able identity for an option (name if dict, else value)."""
    if isinstance(option, dict) and "name" in option:
        return option["name"]
    return option


# ═══════════════════════════════════════════════════════════════════════
#  1. VISUAL VARIETY — board themes, fonts, arrows, zoom
# ═══════════════════════════════════════════════════════════════════════
BOARD_THEMES = [
    {"name": "classic",  "colors": {"square light": "#f0d9b5", "square dark": "#b58863"}},
    {"name": "midnight", "colors": {"square light": "#dee3e6", "square dark": "#4b4b4b"}},
    {"name": "forest",   "colors": {"square light": "#eeeed2", "square dark": "#769656"}},
    {"name": "ocean",    "colors": {"square light": "#e8f1f2", "square dark": "#4a7a8c"}},
    {"name": "royal",    "colors": {"square light": "#ede7f6", "square dark": "#5e35b1"}},
    {"name": "sunset",   "colors": {"square light": "#ffe9d6", "square dark": "#d1495b"}},
    {"name": "mono",     "colors": {"square light": "#f5f5f5", "square dark": "#2b2b2b"}},
]

# Font "look": size multiplier + optional stroke (bold effect via PIL stroke_width)
FONT_STYLES = [
    {"name": "clean",    "scale": 1.00, "stroke": 0},
    {"name": "bold",     "scale": 1.05, "stroke": 2},
    {"name": "oversize", "scale": 1.20, "stroke": 1},
    {"name": "compact",  "scale": 0.90, "stroke": 0},
]

ARROW_COLOR_PAIRS = [
    {"name": "gold_orange", "solver": (255, 215,   0, 230), "opponent": (255,  87,  34, 210)},
    {"name": "blue_red",    "solver": (  0, 176, 255, 230), "opponent": (229,  57,  53, 210)},
    {"name": "green_purple","solver": ( 76, 175,  80, 230), "opponent": (156,  39, 176, 210)},
    {"name": "teal_amber",  "solver": (  0, 191, 165, 230), "opponent": (255, 160,   0, 210)},
    {"name": "pink_navy",   "solver": (236,  64, 122, 230), "opponent": ( 63,  81, 181, 210)},
]

# Subtle zoom/crop variants so consecutive videos don't feel visually identical.
# factor < 1.0 crops in (zoom), then upscales back to BOARD_SIZE.
ZOOM_VARIANTS = [
    {"name": "full",   "factor": 1.00},
    {"name": "tight",  "factor": 0.94},
    {"name": "close",  "factor": 0.90},
]

# Countdown pacing/style variety (retention experiment #7)
COUNTDOWN_STYLES = [
    {"name": "standard_20", "seconds": 20, "style": "full_descend"},
    {"name": "quick_10",    "seconds": 10, "style": "full_descend"},
    {"name": "quick_8",     "seconds": 8,  "style": "full_descend"},
    {"name": "medium_12",   "seconds": 12, "style": "full_descend"},
    {"name": "slow_reveal", "seconds": 15, "style": "hold_then_flash"},
]


def apply_zoom(im, factor, board_size):
    """Crop the image toward its center by `factor` then resize back up."""
    if factor >= 0.999:
        return im
    w, h = im.size
    new_w, new_h = int(w * factor), int(h * factor)
    left = (w - new_w) // 2
    top = (h - new_h) // 2
    cropped = im.crop((left, top, left + new_w, top + new_h))
    return cropped.resize((w, h))


# ═══════════════════════════════════════════════════════════════════════
#  2. HOOKS — first 2 seconds decide almost everything
# ═══════════════════════════════════════════════════════════════════════
HOOKS = [
    "Only 2% solve this.",
    "White to move.",
    "Black to move.",
    "Pause. Then solve.",
    "Can you beat a Grandmaster?",
    "Most players fail this.",
    "This took me 3 tries.",
    "Look closely before you scroll.",
    "The engine says there's one move.",
    "Everyone gets this wrong first try.",
]


# ═══════════════════════════════════════════════════════════════════════
#  3. DIFFICULTY BADGES — visible difficulty before the countdown starts
# ═══════════════════════════════════════════════════════════════════════
DIFFICULTY_BANDS = [
    (0,    1599, "EASY",      "🟢", "#4CAF50"),
    (1600, 1899, "MEDIUM",    "🟡", "#FDD835"),
    (1900, 2199, "HARD",      "🟠", "#FB8C00"),
    (2200, 2499, "EXPERT",    "🔴", "#E53935"),
    (2500, 9999, "IMPOSSIBLE","⚫", "#212121"),
]


def get_difficulty_badge(rating):
    """Return (label, emoji, hex_color) for a numeric puzzle rating."""
    try:
        r = int(rating)
    except (TypeError, ValueError):
        r = 1800
    for lo, hi, label, emoji, color in DIFFICULTY_BANDS:
        if lo <= r <= hi:
            return label, emoji, color
    return "MEDIUM", "🟡", "#FDD835"


# ═══════════════════════════════════════════════════════════════════════
#  4. WEEKLY CONTENT SERIES — returning viewers > random one-offs
# ═══════════════════════════════════════════════════════════════════════
# weekday(): Monday=0 ... Sunday=6
WEEKLY_SERIES = {
    0: {"label": "Beginner Monday",   "min": 1200, "max": 1700, "q": None},
    1: {"label": "Tactical Tuesday",  "min": 1600, "max": 2200, "q": "fork"},
    2: {"label": "Endgame Wednesday", "min": 1700, "max": 2400, "q": "endgame"},
    3: {"label": "Sacrifice Thursday","min": 1800, "max": 2600, "q": "sacrifice"},
    4: {"label": "Impossible Friday", "min": 2400, "max": 3000, "q": "mate"},
    5: {"label": "Weekend Mix",       "min": 1500, "max": 2600, "q": None},
    6: {"label": "Weekend Mix",       "min": 1500, "max": 2600, "q": None},
}


def todays_series():
    return WEEKLY_SERIES[datetime.datetime.now().weekday()]


# ═══════════════════════════════════════════════════════════════════════
#  5. COMMUNITY CTAs — comments are a ranking signal, invite them
# ═══════════════════════════════════════════════════════════════════════
CTAS = [
    "Comment your move ⬇️",
    "Don't scroll till you solve it 👀",
    "Did you find it? Say YES below 👇",
    "Would you play this sacrifice? 🤔",
    "Tag someone who'd fail this 😅",
    "Rate this puzzle 1-10 in the comments",
]


# ═══════════════════════════════════════════════════════════════════════
#  6. A/B TEST LOGGING
# ═══════════════════════════════════════════════════════════════════════
ANALYTICS_FIELDS = [
    "timestamp", "video_type", "board_theme", "font_style", "arrow_pair",
    "zoom", "countdown_style", "countdown_sec", "hook", "message", "cta",
    "series_label", "puzzle_ids", "ratings", "difficulty_labels",
    "hashtags", "output_video", "api_response",
]


def log_analytics(row):
    """
    Append one row describing exactly what "recipe" this video used.
    After ~300 uploads, join this CSV with your FB Insights export
    (by timestamp) to see which theme/hook/difficulty combos actually
    drive views, retention and shares.
    """
    file_exists = os.path.exists(ANALYTICS_FILE)
    try:
        with open(ANALYTICS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ANALYTICS_FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow({k: row.get(k, "") for k in ANALYTICS_FIELDS})
        print(f"[analytics] Logged run to {ANALYTICS_FILE}")
    except Exception as e:
        print(f"[analytics] Could not write log: {e}")


# ═══════════════════════════════════════════════════════════════════════
#  9. RANDOM POSTING DELAY — avoid posting at the exact same minute
# ═══════════════════════════════════════════════════════════════════════
def random_pre_post_delay(min_sec=30, max_sec=900):
    """
    Sleep a random amount of time before publishing. Call this right
    before send_to_social_media_api(), after the video is fully rendered,
    so cron can fire on a fixed schedule but uploads still land at
    varied, human-looking times.
    """
    delay = random.randint(min_sec, max_sec)
    mins = delay / 60
    print(f"[delay] Sleeping {delay}s (~{mins:.1f} min) before publishing...")
    time.sleep(delay)


# ═══════════════════════════════════════════════════════════════════════
#  HELPERS FOR CAPTION BUILDING (no locations, no hashtag spam)
# ═══════════════════════════════════════════════════════════════════════
def build_caption(base_message, series_label=None, cta=None, hashtags=None, max_tags=4):
    """
    Compose a clean caption: series label (optional) + hook-style message +
    one CTA + a SMALL number of relevant hashtags. Deliberately no random
    country/city names or huge tag lists — those don't move FB's ranking
    and can read as spammy.
    """
    parts = []
    if series_label:
        parts.append(f"🔥 {series_label}")
    parts.append(base_message)
    if cta:
        parts.append(cta)
    text = " — ".join(parts)

    if hashtags:
        tags = " ".join(random.sample(hashtags, min(max_tags, len(hashtags))))
        text = f"{text} {tags}"

    return text.encode("ascii", "ignore").decode().strip()
