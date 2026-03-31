import os
import sqlite3
import chess
import chess.svg
import cairosvg
from PIL import Image, ImageDraw, ImageFont
import subprocess
import random
import shutil
import json
import requests

# ═════════════════════════════════════════════
#  CONFIGURATION
# ═════════════════════════════════════════════
DB_FILE         = "./legend_games.db"    # SQLite DB built by the ingestion script
IMG_FOLDER      = "./legendary_images"   # e.g. Adolf_Anderssen_1.jpg
DEFAULT_IMG     = "./default_person.png" # fallback if no legend photo found

FPS             = 30
INTRO_SEC       = 4     # legend intro card hold
LEGEND_CARD_SEC = 5     # initial board + info overlay
FINAL_SEC       = 4     # pause at the very end after endgame card
MAX_RESELECT    = 20    # max DB retries before giving up

# ── Move Timer ────────────────────────────────────────────────
# How long each move is held on screen (in seconds).
#   0.3  → very fast (blitz feel, great for long games)
#   0.5  → fast      (good for most games)
#   1.0  → normal    (comfortable to follow)
#   2.0  → slow      (study / educational pace)
MOVE_SEC        = 1.0

TEMP_DIR        = "frames"
OUTPUT_VIDEO    = "output_video/legendary_game.mp4"
FONT_PATH       = "./Roboto-Regular.ttf"
FONT_BOLD_PATH  = "./Roboto-Bold.ttf"
BOARD_SIZE      = 800

# ── Query Tags ────────────────────────────────────────────────
# Controls WHICH games are selected from the DB.
#
# Preset tags (set QUERY_TAG to one of these strings):
#   "checkmate"   → games that ended in checkmate          [DEFAULT]
#   "resignation" → games decided by resignation
#   "any_win"     → any decisive result (checkmate OR resignation)
#   "fischer"     → only Bobby Fischer games (checkmate wins)
#   "magnus"      → only Magnus Carlsen games (checkmate wins)
#   "draw"        → drawn games
#
# You can also combine: set QUERY_LEGEND and QUERY_TERMINATION separately.

QUERY_TAG         = "checkmate"   # <── change this one line to switch mode

# Advanced: override individual filters (leave "" to use QUERY_TAG defaults)
QUERY_LEGEND      = ""   # e.g. "Fischer" to pin a specific legend
QUERY_TERMINATION = ""   # e.g. "checkmate" or "resignation"

# ── Color highlights (from/to square tints — no arrows) ──────
HIGHLIGHT_WHITE_FROM = "#b8860b"   # dark gold
HIGHLIGHT_WHITE_TO   = "#FFD700"   # bright gold
HIGHLIGHT_BLACK_FROM = "#1a5276"   # dark blue
HIGHLIGHT_BLACK_TO   = "#3498DB"   # bright blue

# ── Intro Audio ───────────────────────────────────────────────
ls = ["./intro_sounds", "/intro_fake"]
INTRO_AUDIO_DIR = random.choice(ls)

# ── Background & Click Audio ──────────────────────────────────
BACKGROUND_MUSIC = "bg_music_free.wav"
CLICK_SOUND      = "move.mp3"
BG_MUSIC_VOLUME  = 0.45
CLICK_VOLUME     = 0.65
INCLUDE_BG_MUSIC = True

# ── Social copy ───────────────────────────────────────────────
# NOTE: emojis here are for the Facebook/X caption text only,
#       NOT rendered into the video frames (Roboto cannot display them).
MESSAGES = [
    "Watch how {legend} crushed this game! #Chess",
    "A masterpiece by {legend} - can you spot the brilliancy?",
    "{legend} at their finest! Every move a lesson.",
    "Genius in action: {legend} vs {opponent}",
    "Study this game by {legend} and level up your chess!",
    "This checkmate by {legend} is absolutely BRUTAL!",
    "{legend} shows no mercy - legendary chess at its finest!",
]
HASHTAGS = [
    "#Chess", "#ChessLegends", "#GrandmasterChess", "#ChessMasterclass",
    "#ChessHistory", "#ChessStrategy", "#LearnChess", "#ChessReels",
    "#Checkmate", "#ChessLife", "#BoardGames", "#ChessIsLife",
    "#ChessTactics", "#ChessCommunity", "#ChessPlayer"
]

# ── Call-To-Action (Follow Us) ────────────────────────────────
# Shown on the endgame card and the final pause.
# All text here is ASCII-safe (rendered into video frames by PIL/Roboto).
CTA_ENABLED      = True
CTA_PAGE_NAME    = "ChessSol"
CTA_MAIN_TEXT    = "Follow {page} for daily chess!"   # {page} -> CTA_PAGE_NAME
CTA_SUB_TEXT     = "New legendary game every day"
CTA_BG_COLOR     = (20, 20, 20, 215)
CTA_ACCENT_COLOR = "#FFD700"
CTA_TEXT_COLOR   = "#FFFFFF"
CTA_SUB_COLOR    = "#BBBBBB"


# ═════════════════════════════════════════════
#  UTILITIES
# ═════════════════════════════════════════════

def detect_ffmpeg():
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin
    local_bin = "./ffmpeg-7.0.2-amd64-static/ffmpeg"
    if os.path.exists(local_bin):
        os.chmod(local_bin, 0o755)
        return local_bin
    raise FileNotFoundError(
        "FFmpeg not found. Install it (sudo apt install ffmpeg) "
        "or place the static binary in the project root."
    )

FFMPEG_BIN = detect_ffmpeg()
print("Using FFmpeg:", FFMPEG_BIN)


def pick_intro_audio():
    supported = (".mp3", ".wav", ".ogg", ".m4a")
    if not os.path.isdir(INTRO_AUDIO_DIR):
        print(f"[intro] Folder '{INTRO_AUDIO_DIR}' not found — skipping intro audio.")
        return None
    files = [
        os.path.join(INTRO_AUDIO_DIR, f)
        for f in os.listdir(INTRO_AUDIO_DIR)
        if f.lower().endswith(supported)
    ]
    if not files:
        print(f"[intro] No audio files in '{INTRO_AUDIO_DIR}' — skipping.")
        return None
    chosen = random.choice(files)
    print(f"[intro] Selected intro: {os.path.basename(chosen)}")
    return chosen


def send_to_social_media_api(platform, link, text, media=None, area=None,
                              x_comm_id=None, fb_post_to=None, location=None):
    api_url = f'https://roynek.com/alltrenders/codes/python_API/social-media/{platform}'
    payload = {
        'link_2_post': link, 'message': text, 'media': media,
        'pages_ordered_ids': area, 'comm_id': x_comm_id,
        'post_to': fb_post_to, 'location': location
    }
    headers = {'Content-Type': 'application/json'}
    print(json.dumps(payload, ensure_ascii=False))
    try:
        r = requests.post(api_url, json=payload, headers=headers, timeout=3000)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print('Social Media Error:', e)
        return None


# ═════════════════════════════════════════════
#  QUERY TAG RESOLUTION
# ═════════════════════════════════════════════

# Maps a QUERY_TAG string → (legend_filter, termination_filter)
# legend_filter      : substring matched against the DB `legend` column ("" = any)
# termination_filter : exact match against `termination_type` column ("" = any)
QUERY_TAG_MAP = {
    "checkmate":   ("",         "checkmate"),
    "resignation": ("",         "resignation"),
    "any_win":     ("",         ""),           # result IN ('1-0','0-1') handled in SQL
    "draw":        ("",         "draw_or_other"),
    "fischer":     ("Fischer",  "checkmate"),
    "magnus":      ("Carlsen",  "checkmate"),
}


def resolve_query_filters():
    """
    Return (legend_filter, termination_filter) by combining QUERY_TAG
    with any manual QUERY_LEGEND / QUERY_TERMINATION overrides.
    """
    tag_legend, tag_term = QUERY_TAG_MAP.get(QUERY_TAG, ("", "checkmate"))

    legend_filter = QUERY_LEGEND.strip()      if QUERY_LEGEND.strip()      else tag_legend
    term_filter   = QUERY_TERMINATION.strip() if QUERY_TERMINATION.strip() else tag_term

    return legend_filter, term_filter


# ═════════════════════════════════════════════
#  DATABASE GAME SELECTION
# ═════════════════════════════════════════════

def build_db_query(legend_filter, term_filter):
    """
    Build a parameterised SELECT for games matching the filters.
    Only decisive wins (result IN ('1-0','0-1')) are selected unless
    QUERY_TAG is 'draw'.
    """
    conditions = []
    params     = []

    # For draw tag we accept draws; otherwise only decisive wins
    if QUERY_TAG == "draw":
        conditions.append("result = '1/2-1/2'")
    else:
        conditions.append("result IN ('1-0', '0-1')")

    if term_filter:
        conditions.append("termination_type = ?")
        params.append(term_filter)

    if legend_filter:
        conditions.append("legend LIKE ?")
        params.append(f"%{legend_filter}%")

    where = " AND ".join(conditions)
    sql   = f"SELECT * FROM games WHERE {where} ORDER BY RANDOM() LIMIT 50"
    return sql, params


def row_to_meta(row, col_names, legend_display_name, legend_color):
    """Convert a DB row dict into the meta dict expected by the drawing code."""
    r = dict(zip(col_names, row))
    return {
        "legend_name":  legend_display_name,
        "legend_color": legend_color,
        "white":        r.get("white", "?"),
        "black":        r.get("black", "?"),
        "event":        r.get("event", ""),
        "site":         r.get("site", ""),
        "date":         r.get("date", ""),
        "result":       r.get("result", ""),
        "eco":          r.get("eco", ""),
        "termination":  r.get("termination_type", ""),
        "moves_san":    r.get("moves", ""),        # space-separated SAN string
    }


def determine_legend_color(row_dict, legend_filter):
    """
    Work out which color the legend played.
    Uses the result + which name contains the legend filter.
    Falls back to result-based heuristic.
    """
    result = row_dict.get("result", "*")
    white  = row_dict.get("white", "").lower()
    black  = row_dict.get("black", "").lower()
    legend = row_dict.get("legend", "").lower()

    # The legend column is the PGN filename stem (e.g. "Fischer", "Carlsen")
    surname = legend.split()[-1] if legend else ""

    if result == "1-0":
        return chess.WHITE    # White won — legend played White
    elif result == "0-1":
        return chess.BLACK    # Black won — legend played Black
    else:
        # Draw — guess based on name match
        if surname and surname in white:
            return chess.WHITE
        return chess.BLACK


def legend_display_name_from_db(legend_col):
    """
    Convert the DB legend column (PGN filename stem, e.g. 'VachierLagrave')
    to a human-readable display name.

    We reconstruct it from the image folder when possible; otherwise
    fall back to inserting spaces before capital letters.
    """
    # Try to match against image filenames for a clean display name
    if os.path.isdir(IMG_FOLDER):
        supported = (".jpg", ".jpeg", ".png", ".webp")
        for f in os.listdir(IMG_FOLDER):
            if not f.lower().endswith(supported):
                continue
            display, pgn_key, _ = parse_image_filename(f)
            if pgn_key.lower() == legend_col.lower():
                return display

    # Fallback: insert spaces before uppercase letters in CamelCase
    import re
    spaced = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', legend_col)
    return spaced


def pick_game_from_db(db_file, max_attempts=MAX_RESELECT):
    """
    Query the SQLite DB using the resolved filters.
    Returns (meta, img_path) on success.
    Raises RuntimeError if no suitable game found.
    """
    legend_filter, term_filter = resolve_query_filters()
    print(f"\n[db] Query tag: '{QUERY_TAG}' → legend='{legend_filter}', "
          f"termination='{term_filter}'")

    sql, params = build_db_query(legend_filter, term_filter)

    conn     = sqlite3.connect(db_file)
    cursor   = conn.cursor()
    cursor.execute(sql, params)
    col_names = [d[0] for d in cursor.description]
    rows      = cursor.fetchall()
    conn.close()

    if not rows:
        raise RuntimeError(
            f"No games found in DB matching tag='{QUERY_TAG}'. "
            "Check your DB or relax the query filters."
        )

    print(f"[db] {len(rows)} candidate game(s) found. Picking one...")
    random.shuffle(rows)

    for row in rows[:max_attempts]:
        row_dict      = dict(zip(col_names, row))
        legend_col    = row_dict.get("legend", "")
        legend_color  = determine_legend_color(row_dict, legend_filter)
        display_name  = legend_display_name_from_db(legend_col)

        meta = row_to_meta(row, col_names, display_name, legend_color)

        # Validate moves string
        if not meta["moves_san"].strip():
            print(f"[db] Empty moves for game id={row_dict.get('id')} — skipping.")
            continue

        # Pick image
        img_path = pick_legend_image(display_name)

        side = "White" if legend_color == chess.WHITE else "Black"
        print(f"[db] Selected: {display_name} ({side}) vs "
              f"{'black' if legend_color == chess.WHITE else 'white'} player | "
              f"{meta['event']} {meta['date']} | "
              f"Termination: {meta['termination']}")

        return meta, img_path

    raise RuntimeError(
        f"Could not select a valid game after {max_attempts} attempt(s). "
        "Check your DB content."
    )


# ═════════════════════════════════════════════
#  MOVE RECONSTRUCTION FROM SAN STRING
# ═════════════════════════════════════════════

def moves_from_san_string(san_string):
    """
    Parse a space-separated SAN move string (as stored by the ingestion script)
    and return a list of chess.Move objects by replaying the game.

    e.g. "e4 e5 Nf3 Nc6 Bb5" → [Move(...), Move(...), ...]
    """
    board  = chess.Board()
    moves  = []
    tokens = san_string.strip().split()

    for token in tokens:
        # Skip move number indicators like "1." "2." etc. (shouldn't be present
        # in the DB format from the ingestion script, but guard just in case)
        if token.endswith(".") or token in ("*", "1-0", "0-1", "1/2-1/2"):
            continue
        try:
            move = board.push_san(token)
            moves.append(move)
        except Exception as e:
            print(f"[moves] Could not parse SAN token '{token}': {e} — stopping here.")
            break

    # Reset board (we pushed onto a scratch board just to get Move objects)
    return moves


# ═════════════════════════════════════════════
#  IMAGE SELECTION
# ═════════════════════════════════════════════

def parse_image_filename(filename):
    """
    'Adolf_Anderssen_2.jpg' → display_name='Adolf Anderssen',
                               pgn_key='Anderssen', img_index=2
    """
    stem  = os.path.splitext(filename)[0]
    parts = stem.split("_")
    if parts and parts[-1].isdigit():
        img_index  = int(parts[-1])
        name_parts = parts[:-1]
    else:
        img_index  = 0
        name_parts = parts
    display_name  = " ".join(name_parts)
    surname_parts = name_parts[1:] if len(name_parts) > 1 else name_parts
    pgn_key       = "".join(p.replace("-", "") for p in surname_parts)
    return display_name, pgn_key, img_index


def pick_legend_image(display_name):
    """
    Find images for display_name in IMG_FOLDER and return a random one.
    Falls back to DEFAULT_IMG, then None.
    """
    if not os.path.isdir(IMG_FOLDER):
        return _fallback_image()

    supported = (".jpg", ".jpeg", ".png", ".webp")
    # Build pgn_key from display name the same way the ingestion does
    parts         = display_name.split()
    surname_parts = parts[1:] if len(parts) > 1 else parts
    pgn_key       = "".join(p.replace("-", "") for p in surname_parts).lower()

    candidates = []
    for f in os.listdir(IMG_FOLDER):
        if not f.lower().endswith(supported):
            continue
        _, fkey, _ = parse_image_filename(f)
        if fkey.lower() == pgn_key:
            candidates.append(os.path.join(IMG_FOLDER, f))

    if candidates:
        chosen = random.choice(candidates)
        print(f"[img] Photo: {os.path.basename(chosen)}")
        return chosen

    print(f"[img] No images found for '{display_name}'")
    return _fallback_image()


def _fallback_image():
    if os.path.exists(DEFAULT_IMG):
        print(f"[img] Using default person image.")
        return DEFAULT_IMG
    return None


# ═════════════════════════════════════════════
#  DEFAULT PERSON IMAGE
# ═════════════════════════════════════════════

def generate_default_person_png(out_path, size=220):
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
         width="{size}" height="{size}" viewBox="0 0 100 100">
  <rect width="100" height="100" rx="50" fill="#2c3e50"/>
  <circle cx="50" cy="32" r="18" fill="#95a5a6"/>
  <ellipse cx="50" cy="76" rx="26" ry="22" fill="#95a5a6"/>
</svg>"""
    cairosvg.svg2png(bytestring=svg.encode(),
                     write_to=out_path,
                     output_width=size, output_height=size)
    print(f"[default_img] Generated default silhouette → {out_path}")


# ═════════════════════════════════════════════
#  DRAWING HELPERS
# ═════════════════════════════════════════════

def load_font(size, bold=False):
    path = FONT_BOLD_PATH if bold else FONT_PATH
    for p in [path, FONT_PATH]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def render_board_png(board, last_move=None, flipped=False):
    """
    Render board with square-colour highlights on the last move.
    White moves -> gold. Black moves -> blue. No arrows.
    """
    fill = {}
    if last_move is not None:
        if board.turn == chess.BLACK:          # White just moved
            fill[last_move.from_square] = HIGHLIGHT_WHITE_FROM
            fill[last_move.to_square]   = HIGHLIGHT_WHITE_TO
        else:                                  # Black just moved
            fill[last_move.from_square] = HIGHLIGHT_BLACK_FROM
            fill[last_move.to_square]   = HIGHLIGHT_BLACK_TO

    svg_data = chess.svg.board(
        board,
        size=BOARD_SIZE,
        lastmove=None,
        fill=fill,
        flipped=flipped,
    ).encode("UTF-8")

    tmp = os.path.join(TEMP_DIR, "_tmp_board.png")
    cairosvg.svg2png(bytestring=svg_data, write_to=tmp)
    return Image.open(tmp).convert("RGBA")


# ── Top bar ───────────────────────────────────────────────────
def draw_top_bar(im, meta, move_number, total_moves):
    """
    Semi-transparent top bar.
    Larger fonts so viewers can read easily on mobile.
    """
    bar_h = 100   # taller bar for bigger fonts
    bar   = Image.new("RGBA", (BOARD_SIZE, bar_h), (10, 10, 10, 195))
    im.paste(bar, (0, 0), bar)
    draw  = ImageDraw.Draw(im, "RGBA")

    # Accent bottom border
    border = Image.new("RGBA", (BOARD_SIZE, 3), (*_hex_to_rgb("#FFD700"), 200))
    im.paste(border, (0, bar_h - 3), border)
    draw = ImageDraw.Draw(im, "RGBA")

    fn_name = load_font(38, bold=True)   # was 30
    fn_sub  = load_font(26)              # was 22
    fn_cnt  = load_font(26)              # was 22

    side     = "White" if meta["legend_color"] == chess.WHITE else "Black"
    opponent = meta["black"] if meta["legend_color"] == chess.WHITE else meta["white"]
    # Truncate long opponent names
    opp_str  = opponent[:28] + "..." if len(opponent) > 28 else opponent

    draw.text((16, 10),  meta["legend_name"],         font=fn_name, fill="#FFD700")
    draw.text((16, 58),  f"vs {opp_str} - {side}",    font=fn_sub,  fill="#CCCCCC")

    ctr  = f"Move {move_number}/{total_moves}"
    bbox = draw.textbbox((0, 0), ctr, font=fn_cnt)
    draw.text((BOARD_SIZE - (bbox[2] - bbox[0]) - 16, 36), ctr,
              font=fn_cnt, fill="#AAAAAA")
    return im


# ── Bottom bar ────────────────────────────────────────────────
def draw_bottom_bar(im, meta):
    """Slim bottom bar: event - year - ECO. Larger font."""
    bar_h = 52   # was 46
    bar   = Image.new("RGBA", (BOARD_SIZE, bar_h), (10, 10, 10, 180))
    im.paste(bar, (0, BOARD_SIZE - bar_h), bar)
    draw  = ImageDraw.Draw(im, "RGBA")

    fn    = load_font(24)    # was 20
    event = (meta["event"] or "?")[:40]
    year  = (meta["date"] or "").split(".")[0]
    eco   = meta["eco"] or ""
    draw.text((16, BOARD_SIZE - bar_h + 13),
              f"{event}  -  {year}  -  {eco}", font=fn, fill="#AAAAAA")
    return im


# ═════════════════════════════════════════════
#  CALL-TO-ACTION BANNER
# ═════════════════════════════════════════════

ENDGAME_SEC = 5   # how long the endgame card is shown

def draw_cta_banner(im, compact=False):
    """
    "Follow Us" CTA banner — ASCII-safe text only (no emoji in PIL renders).
    compact=False → full 2-line banner on endgame card
    compact=True  → slim 1-line bar on final pause
    """
    if not CTA_ENABLED:
        return im

    im   = im.convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")

    main_text = CTA_MAIN_TEXT.format(page=CTA_PAGE_NAME)

    if compact:
        BAR_H = 56    # was 48
        bar_y = BOARD_SIZE - BAR_H
        bar   = Image.new("RGBA", (BOARD_SIZE, BAR_H), CTA_BG_COLOR)
        im.paste(bar, (0, bar_y), bar)

        # Accent left stripe
        stripe = Image.new("RGBA", (6, BAR_H), (*_hex_to_rgb(CTA_ACCENT_COLOR), 255))
        im.paste(stripe, (0, bar_y), stripe)

        draw   = ImageDraw.Draw(im, "RGBA")
        fn     = load_font(26, bold=True)   # was 22
        fn_sm  = load_font(21)              # was 18

        draw.text((16, bar_y + 9), main_text, font=fn, fill=CTA_TEXT_COLOR)

        bbox = draw.textbbox((0, 0), CTA_SUB_TEXT, font=fn_sm)
        tw   = bbox[2] - bbox[0]
        draw.text((BOARD_SIZE - tw - 14, bar_y + 14),
                  CTA_SUB_TEXT, font=fn_sm, fill=CTA_SUB_COLOR)

    else:
        BAR_H = 84    # was 72
        bar_y = BOARD_SIZE - BAR_H
        bar   = Image.new("RGBA", (BOARD_SIZE, BAR_H), CTA_BG_COLOR)
        im.paste(bar, (0, bar_y), bar)

        # Accent top border
        border = Image.new("RGBA", (BOARD_SIZE, 4),
                           (*_hex_to_rgb(CTA_ACCENT_COLOR), 255))
        im.paste(border, (0, bar_y), border)

        draw  = ImageDraw.Draw(im, "RGBA")
        fn_lg = load_font(34, bold=True)    # was 28
        fn_sm = load_font(24)               # was 20

        bbox = draw.textbbox((0, 0), main_text, font=fn_lg)
        tw   = bbox[2] - bbox[0]
        draw.text(((BOARD_SIZE - tw) // 2, bar_y + 10),
                  main_text, font=fn_lg, fill=CTA_ACCENT_COLOR)

        bbox = draw.textbbox((0, 0), CTA_SUB_TEXT, font=fn_sm)
        tw   = bbox[2] - bbox[0]
        draw.text(((BOARD_SIZE - tw) // 2, bar_y + 52),
                  CTA_SUB_TEXT, font=fn_sm, fill=CTA_SUB_COLOR)

    return im.convert("RGB")


# ═════════════════════════════════════════════
#  ENDGAME CARD
# ═════════════════════════════════════════════

RESULT_LABEL = {
    "1-0":     ("WHITE WINS", "#FFD700"),
    "0-1":     ("BLACK WINS", "#3498DB"),
    "1/2-1/2": ("DRAW",       "#AAAAAA"),
}

TERMINATION_LABEL = {
    "checkmate":    "by Checkmate",
    "resignation":  "by Resignation",
    "draw_or_other":"Draw",
}


def create_endgame_card(meta, board):
    """
    Darkened final board + centred result card.
    All text is ASCII-safe for PIL/Roboto rendering.
    """
    flipped = (meta["legend_color"] == chess.BLACK)
    im      = render_board_png(board, flipped=flipped)

    overlay = Image.new("RGBA", (BOARD_SIZE, BOARD_SIZE), (0, 0, 0, 190))
    im      = Image.alpha_composite(im, overlay)

    result_str  = meta.get("result", "*")
    label, accent = RESULT_LABEL.get(result_str, ("GAME OVER", "#FFFFFF"))
    term_label    = TERMINATION_LABEL.get(meta.get("termination", ""), "")

    # ── Card ──────────────────────────────────────────────────
    CARD_W, CARD_H = 580, 330   # wider + taller for bigger text
    cx = (BOARD_SIZE - CARD_W) // 2
    cy = (BOARD_SIZE - CARD_H) // 2 - 30   # shift up to leave room for CTA

    card = Image.new("RGBA", (CARD_W, CARD_H), (12, 12, 12, 235))
    im.paste(card, (cx, cy), card)

    # Accent top strip
    strip = Image.new("RGBA", (CARD_W, 10), (*_hex_to_rgb(accent), 255))
    im.paste(strip, (cx, cy), strip)

    draw = ImageDraw.Draw(im, "RGBA")

    fn_result = load_font(60, bold=True)   # was 52  — BIG result text
    fn_term   = load_font(28)              # termination sub-label
    fn_name   = load_font(36, bold=True)   # was 28  — legend name
    fn_detail = load_font(26)              # was 21  — detail lines
    fn_footer = load_font(22)              # was 21  — footer

    # Result label (e.g. "WHITE WINS")
    bbox = draw.textbbox((0, 0), label, font=fn_result)
    tw   = bbox[2] - bbox[0]
    draw.text((cx + (CARD_W - tw) // 2, cy + 14),
              label, font=fn_result, fill=accent)

    # Termination sub-label (e.g. "by Checkmate")
    if term_label:
        bbox = draw.textbbox((0, 0), term_label, font=fn_term)
        tw   = bbox[2] - bbox[0]
        draw.text((cx + (CARD_W - tw) // 2, cy + 82),
                  term_label, font=fn_term, fill="#AAAAAA")

    # Divider
    div_y = cy + 118
    draw.line([(cx + 30, div_y), (cx + CARD_W - 30, div_y)],
              fill=(80, 80, 80, 200), width=2)

    # Legend name
    bbox = draw.textbbox((0, 0), meta["legend_name"], font=fn_name)
    tw   = bbox[2] - bbox[0]
    draw.text((cx + (CARD_W - tw) // 2, cy + 128),
              meta["legend_name"], font=fn_name, fill="#FFD700")

    # vs opponent
    side     = "White" if meta["legend_color"] == chess.WHITE else "Black"
    opponent = meta["black"] if meta["legend_color"] == chess.WHITE else meta["white"]
    vs_txt   = f"vs {opponent}  -  {side}"
    bbox     = draw.textbbox((0, 0), vs_txt, font=fn_detail)
    tw       = bbox[2] - bbox[0]
    draw.text((cx + (CARD_W - tw) // 2, cy + 176),
              vs_txt, font=fn_detail, fill="#CCCCCC")

    # Event - Year - ECO
    event   = (meta.get("event") or "")[:35]
    year    = (meta.get("date") or "").split(".")[0]
    eco     = meta.get("eco") or ""
    evt_txt = "  -  ".join(filter(None, [event, year, eco]))
    if evt_txt:
        bbox = draw.textbbox((0, 0), evt_txt, font=fn_detail)
        tw   = bbox[2] - bbox[0]
        draw.text((cx + (CARD_W - tw) // 2, cy + 214),
                  evt_txt, font=fn_detail, fill="#888888")

    # Footer
    footer = "--- Game Over ---"
    bbox   = draw.textbbox((0, 0), footer, font=fn_footer)
    tw     = bbox[2] - bbox[0]
    draw.text((cx + (CARD_W - tw) // 2, cy + CARD_H - 40),
              footer, font=fn_footer, fill=(80, 80, 80, 200))

    # CTA banner (full, prominent)
    im = draw_cta_banner(im.convert("RGB"), compact=False)
    return im


# ═════════════════════════════════════════════
#  LEGEND INTRO CARD
# ═════════════════════════════════════════════

def create_legend_intro_frame(meta, img_path, board):
    """
    Cinematic intro: darkened board + centred legend card with photo.
    All text is ASCII-safe (no emoji in PIL renders).
    """
    flipped = (meta["legend_color"] == chess.BLACK)
    im      = render_board_png(board, flipped=flipped)

    overlay = Image.new("RGBA", (BOARD_SIZE, BOARD_SIZE), (0, 0, 0, 175))
    im      = Image.alpha_composite(im, overlay)
    draw    = ImageDraw.Draw(im, "RGBA")

    CARD_W, CARD_H = 620, 370   # wider + taller
    cx = (BOARD_SIZE - CARD_W) // 2
    cy = (BOARD_SIZE - CARD_H) // 2

    card = Image.new("RGBA", (CARD_W, CARD_H), (15, 15, 15, 230))
    im.paste(card, (cx, cy), card)

    # Gold top accent strip
    strip = Image.new("RGBA", (CARD_W, 8), (*_hex_to_rgb("#FFD700"), 255))
    im.paste(strip, (cx, cy), strip)

    draw = ImageDraw.Draw(im, "RGBA")

    # ── Photo ─────────────────────────────────────────────────
    photo_size = 220   # was 200
    photo_x    = cx + 30
    photo_y    = cy + (CARD_H - photo_size) // 2

    if img_path and os.path.exists(img_path):
        try:
            photo = Image.open(img_path).convert("RGBA")
            photo = photo.resize((photo_size, photo_size), Image.LANCZOS)
            mask  = Image.new("L", (photo_size, photo_size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, photo_size, photo_size), fill=255)
            photo.putalpha(mask)
            im.paste(photo, (photo_x, photo_y), photo)
            draw = ImageDraw.Draw(im, "RGBA")
            draw.ellipse(
                (photo_x - 4, photo_y - 4,
                 photo_x + photo_size + 4, photo_y + photo_size + 4),
                outline="#FFD700", width=5
            )
        except Exception as e:
            print(f"[intro] Could not render photo: {e}")
            img_path = None

    if not img_path or not os.path.exists(img_path):
        draw.ellipse(
            (photo_x, photo_y, photo_x + photo_size, photo_y + photo_size),
            fill=(44, 62, 80, 220), outline="#FFD700", width=4
        )
        fn_icon = load_font(90)
        # Use a simple "P" (pawn abbreviation) since emoji won't render in Roboto
        draw.text((photo_x + 70, photo_y + 55), "P", font=fn_icon, fill="#FFD700")

    # ── Text ──────────────────────────────────────────────────
    tx = photo_x + photo_size + 30
    ty = cy + 28

    fn_title  = load_font(42, bold=True)   # was 34
    fn_sub    = load_font(26)              # was 22
    fn_detail = load_font(23)              # was 19

    side     = "White" if meta["legend_color"] == chess.WHITE else "Black"
    opponent = meta["black"] if meta["legend_color"] == chess.WHITE else meta["white"]

    draw.text((tx, ty),      meta["legend_name"], font=fn_title, fill="#FFD700")
    draw.text((tx, ty + 55), "Chess Legend",      font=fn_sub,   fill="#AAAAAA")

    lines = [
        f"vs {opponent}",
        f"Playing as {side}",
        (meta["event"] or "")[:32],
        (meta["date"] or "").split(".")[0],
        f"Result: {meta['result']}",
    ]
    for i, line in enumerate(lines):
        if line:
            draw.text((tx, ty + 112 + i * 34), line, font=fn_detail, fill="#DDDDDD")

    return im.convert("RGB")


# ═════════════════════════════════════════════
#  GAME FRAME
# ═════════════════════════════════════════════

def create_game_frame(board, last_move, meta, move_number, total_moves):
    """One game replay frame: board + top bar + bottom bar."""
    flipped = (meta["legend_color"] == chess.BLACK)
    im = render_board_png(board, last_move=last_move, flipped=flipped)
    im = draw_top_bar(im, meta, move_number, total_moves)
    im = draw_bottom_bar(im, meta)
    return im.convert("RGB")


# ═════════════════════════════════════════════
#  FRAME GENERATION
# ═════════════════════════════════════════════

def save_frames(moves, meta, img_path):
    frame_count = 0

    def save(img):
        nonlocal frame_count
        img.save(os.path.join(TEMP_DIR, f"frame_{frame_count:05d}.png"))
        frame_count += 1

    def save_n(img, n):
        for _ in range(n):
            save(img)

    board       = chess.Board()
    total_moves = len(moves)
    move_frames = max(1, round(FPS * MOVE_SEC))

    # 1 ── Legend intro card ───────────────────────────────────
    print("[frames] Rendering intro card...")
    save_n(create_legend_intro_frame(meta, img_path, board), FPS * INTRO_SEC)

    # 2 ── Initial board (before moves) ───────────────────────
    save_n(create_game_frame(board, None, meta, 0, total_moves), FPS * LEGEND_CARD_SEC)

    # 3 ── Move replay ─────────────────────────────────────────
    print(f"[frames] Replaying {total_moves} moves at {MOVE_SEC}s/move "
          f"({move_frames} frames/move)...")
    last_move = None
    for i, move in enumerate(moves):
        board.push(move)
        last_move = move
        im = create_game_frame(board, move, meta, i + 1, total_moves)
        save_n(im, move_frames)
        if (i + 1) % 10 == 0:
            print(f"[frames]   ... {i + 1}/{total_moves}")

    # 4 ── Endgame card ────────────────────────────────────────
    print("[frames] Rendering endgame card...")
    save_n(create_endgame_card(meta, board), FPS * ENDGAME_SEC)

    # 5 ── Final pause (last board + compact CTA) ─────────────
    final_im = create_game_frame(board, last_move, meta, total_moves, total_moves)
    final_im = draw_cta_banner(final_im, compact=True)
    save_n(final_im, FPS * FINAL_SEC)

    print(f"[frames] Total frames: {frame_count}")


# ═════════════════════════════════════════════
#  VIDEO ENCODING
# ═════════════════════════════════════════════

def encode_video(intro_file=None):
    video_part  = f"-framerate {FPS} -i {TEMP_DIR}/frame_%05d.png"
    has_intro   = intro_file is not None and os.path.exists(intro_file)
    has_music   = INCLUDE_BG_MUSIC and os.path.exists(BACKGROUND_MUSIC)
    has_click   = os.path.exists(CLICK_SOUND)

    inputs, filter_parts, mix_labels, idx = [], [], [], 1

    if has_intro:
        inputs.append(f"-i {intro_file}")
        filter_parts.append(f"[{idx}:a]volume=1.0[intro]")
        mix_labels.append("[intro]"); idx += 1

    if has_music:
        inputs.append(f"-i {BACKGROUND_MUSIC}")
        filter_parts.append(f"[{idx}:a]volume={BG_MUSIC_VOLUME}[bg]")
        mix_labels.append("[bg]"); idx += 1

    if has_click:
        inputs.append(f"-i {CLICK_SOUND}")
        filter_parts.append(f"[{idx}:a]volume={CLICK_VOLUME}[clk]")
        mix_labels.append("[clk]"); idx += 1

    inputs_str = " ".join(inputs)
    n          = len(mix_labels)

    if n == 0:
        cmd = (f"{FFMPEG_BIN} -y {video_part} "
               f"-c:v libx264 -pix_fmt yuv420p {OUTPUT_VIDEO}")
    elif n == 1:
        lbl = mix_labels[0].strip("[]")
        cmd = (f"{FFMPEG_BIN} -y {video_part} {inputs_str} "
               f'-filter_complex "{filter_parts[0]}" '
               f"-map 0:v -map [{lbl}] "
               f"-c:v libx264 -pix_fmt yuv420p -shortest {OUTPUT_VIDEO}")
    else:
        mix_str = "".join(mix_labels)
        filter_parts.append(
            f"{mix_str}amix=inputs={n}:duration=longest:normalize=0[aout]"
        )
        cmd = (f"{FFMPEG_BIN} -y {video_part} {inputs_str} "
               f'-filter_complex "{";".join(filter_parts)}" '
               f"-map 0:v -map [aout] "
               f"-c:v libx264 -pix_fmt yuv420p -shortest {OUTPUT_VIDEO}")

    print("[ffmpeg]", cmd[:220], "...")
    subprocess.run(cmd, shell=True, check=True)


# ═════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_VIDEO), exist_ok=True)

if not os.path.exists(DEFAULT_IMG):
    generate_default_person_png(DEFAULT_IMG)

print("=" * 55)
print("  Legendary Chess -- Video Generator")
print("=" * 55)

# ── Select game from DB ───────────────────────────────────────
print(f"\n[main] Selecting game (tag: '{QUERY_TAG}')...")
meta, img_path = pick_game_from_db(DB_FILE)

# ── Reconstruct moves from SAN string ────────────────────────
print("\n[main] Reconstructing moves from DB...")
moves = moves_from_san_string(meta["moves_san"])
print(f"[main] {len(moves)} moves to replay.")

intro_file = pick_intro_audio()

# ── Frames ────────────────────────────────────────────────────
print("\n[main] Generating frames...")
save_frames(moves, meta, img_path)

# ── Encode ────────────────────────────────────────────────────
print("\n[main] Encoding video...")
encode_video(intro_file=intro_file)

# ── Social copy ───────────────────────────────────────────────
opponent = meta["black"] if meta["legend_color"] == chess.WHITE else meta["white"]
msg      = random.choice(MESSAGES).format(legend=meta["legend_name"], opponent=opponent)
tags     = " ".join(random.sample(HASHTAGS, 4))
safe_msg = f"{msg} {tags}".encode("ascii", "ignore").decode().strip()

print(f"\n  Social copy:\n{safe_msg}\n")

video_url = f"https://roynek.com/Chess_Sol_Puzzles/auto_post_legends/{OUTPUT_VIDEO}"
game_link = ""
location  = "us_chess"

output = send_to_social_media_api(
    platform='facebook', link=game_link, text=safe_msg,
    media=video_url, area='6', fb_post_to="reels", location=location
)
print("Facebook API Response:", output)


# ── Cleanup ───────────────────────────────────────────────────
for f in os.listdir(TEMP_DIR):
    os.remove(os.path.join(TEMP_DIR, f))
os.rmdir(TEMP_DIR)

print(f"\n  Done -- video saved to: {OUTPUT_VIDEO}")