import os
import chess
import chess.pgn
import chess.svg
import cairosvg
from PIL import Image, ImageDraw, ImageFont
import subprocess
import random
import shutil
import json
import requests

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
PGN_FOLDER      = "./legendary_games"    # e.g. Anderssen.pgn, VachierLagrave.pgn
IMG_FOLDER      = "./legendary_images"   # e.g. Adolf_Anderssen_1.jpg
DEFAULT_IMG     = "./default_person.png" # fallback if no photo found

FPS             = 30
INTRO_SEC       = 4     # legend intro card hold
LEGEND_CARD_SEC = 5     # initial board + info overlay
FINAL_SEC       = 4     # pause at the very end after endgame card
MAX_RESELECT    = 20    # max legend candidates to try per run

# ── Move Timer ────────────────────────────────────────────────
# How long each move is held on screen (in seconds).
# Supports decimals — tune to taste:
#   0.3  → very fast (blitz feel, great for long games)
#   0.5  → fast      (default, good for most games)
#   1.0  → normal    (comfortable to follow)
#   2.0  → slow      (study / educational pace)
MOVE_SEC        = 1

TEMP_DIR        = "frames"
OUTPUT_VIDEO    = "output_video/legendary_game.mp4"
FONT_PATH       = "./Roboto-Regular.ttf"
FONT_BOLD_PATH  = "./Roboto-Bold.ttf"
BOARD_SIZE      = 800

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
BG_MUSIC_VOLUME  = 0.35
CLICK_VOLUME     = 0.65
INCLUDE_BG_MUSIC = True

# ── Social copy ───────────────────────────────────────────────
MESSAGES = [
    "Watch how {legend} crushed this game! \u265f\ufe0f",
    "A masterpiece by {legend} — can you spot the brilliancy? \U0001f9e0",
    "{legend} at their finest! Every move a lesson. \U0001f525",
    "Genius in action: {legend} vs {opponent} \u265b",
    "Study this game by {legend} and level up your chess! \U0001f4c8",
]
HASHTAGS = [
    "#Chess", "#ChessLegends", "#GrandmasterChess", "#ChessMasterclass",
    "#ChessHistory", "#ChessStrategy", "#LearnChess", "#ChessReels",
    "#Checkmate", "#ChessLife", "#BoardGames", "#ChessIsLife",
    "#ChessTactics", "#ChessCommunity", "#ChessPlayer"
]

# ── Call-To-Action (Follow Us) ───────────────────────────────
# Shown on the endgame card and throughout the final pause.
# Customise these to match your page/brand.
CTA_ENABLED      = True
CTA_PAGE_NAME    = "ChessSol"                        # your page / handle name
CTA_PLATFORM     = "Facebook & Reels"                # shown as sub-line
CTA_MAIN_TEXT    = "Follow {page} for daily chess!"  # {page} → CTA_PAGE_NAME
CTA_SUB_TEXT     = "New legendary game every day  ♟"
CTA_ICON         = "♛"                               # icon shown left of main text
CTA_BG_COLOR     = (20, 20, 20, 210)                 # RGBA background of banner
CTA_ACCENT_COLOR = "#FFD700"                         # gold — matches brand
CTA_TEXT_COLOR   = "#FFFFFF"
CTA_SUB_COLOR    = "#AAAAAA"

# ─────────────────────────────────────────────
#  UTILITIES
# ─────────────────────────────────────────────
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
                              x_comm_id=None, fb_post_to=None):
    api_url = f'https://roynek.com/alltrenders/codes/python_API/social-media/{platform}'
    payload = {
        'link_2_post': link, 'message': text, 'media': media,
        'pages_ordered_ids': area, 'comm_id': x_comm_id, 'post_to': fb_post_to
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


# ─────────────────────────────────────────────
#  NAME RESOLUTION
#
#  Image files use:  Firstname_Surname_N.ext
#                    e.g. Adolf_Anderssen_1.jpg
#                         Maxime_Vachier-Lagrave_2.png
#
#  PGN files use:    Surname(s) concatenated, hyphens removed, CamelCase
#                    e.g. Anderssen.pgn
#                         VachierLagrave.pgn
#                         VallejoPons.pgn
#
#  Matching strategy
#  ─────────────────
#  From image stem "Adolf_Anderssen":
#    display_name = "Adolf Anderssen"
#    pgn_key      = "Anderssen"   (surname(s) after first word, hyphens stripped)
#
#  From image stem "Maxime_Vachier-Lagrave":
#    display_name = "Maxime Vachier-Lagrave"
#    pgn_key      = "VachierLagrave"
#
#  We then do a case-insensitive lookup against the PGN folder index.
# ─────────────────────────────────────────────

def parse_image_filename(filename):
    """
    Given an image filename like 'Adolf_Anderssen_2.jpg', return:
      display_name : "Adolf Anderssen"
      pgn_key      : "Anderssen"          (surname(s) joined, hyphens removed)
      img_index    : 2
    """
    stem  = os.path.splitext(filename)[0]    # "Adolf_Anderssen_2"
    parts = stem.split("_")                  # ["Adolf", "Anderssen", "2"]

    # Peel off trailing numeric index if present
    if parts and parts[-1].isdigit():
        img_index  = int(parts[-1])
        name_parts = parts[:-1]              # ["Adolf", "Anderssen"]
    else:
        img_index  = 0
        name_parts = parts

    display_name = " ".join(name_parts)      # "Adolf Anderssen"

    # Surname = everything after first word; strip hyphens for the PGN key
    surname_parts = name_parts[1:] if len(name_parts) > 1 else name_parts
    pgn_key = "".join(p.replace("-", "") for p in surname_parts)  # "Anderssen"

    return display_name, pgn_key, img_index


def build_pgn_index(pgn_folder):
    """
    Return dict: lowercase_stem -> full_path
    e.g. {"anderssen": "/path/Anderssen.pgn", "vachierlagrave": "..."}
    """
    index = {}
    for f in os.listdir(pgn_folder):
        if f.lower().endswith(".pgn"):
            stem = os.path.splitext(f)[0]
            index[stem.lower()] = os.path.join(pgn_folder, f)
    return index


def find_pgn_for_key(pgn_key, pgn_index):
    """
    Resolve pgn_key → PGN file path.
    1. Exact case-insensitive match.
    2. Substring match (pgn_key inside a PGN stem, or vice-versa).
    Returns path string or None.
    """
    key = pgn_key.lower()

    # 1 — exact
    if key in pgn_index:
        return pgn_index[key]

    # 2 — substring
    for stem, path in pgn_index.items():
        if key in stem or stem in key:
            return path

    return None


def get_all_legend_groups(img_folder):
    """
    Scan IMG_FOLDER and return a list of dicts, one per unique legend:
      [{"display_name": "Adolf Anderssen",
        "pgn_key":      "Anderssen",
        "images":       ["/path/Adolf_Anderssen_1.jpg", ...]}, ...]
    Ordered randomly (shuffled).
    """
    supported = (".jpg", ".jpeg", ".png", ".webp")
    groups    = {}   # pgn_key -> dict

    for f in sorted(os.listdir(img_folder)):
        if not f.lower().endswith(supported):
            continue
        display_name, pgn_key, _ = parse_image_filename(f)
        if pgn_key not in groups:
            groups[pgn_key] = {
                "display_name": display_name,
                "pgn_key":      pgn_key,
                "images":       [],
            }
        groups[pgn_key]["images"].append(os.path.join(img_folder, f))

    result = list(groups.values())
    random.shuffle(result)
    return result


# ─────────────────────────────────────────────
#  GAME SELECTION
# ─────────────────────────────────────────────

def pick_winning_game(pgn_path, display_name):
    """
    Read pgn_path and return a randomly chosen game where the legend won.
    Matching is done by surname (last word of display_name) inside the
    White/Black PGN header — covers most database formats.

    Returns (game, legend_color, meta_dict) or None.
    """
    surname = display_name.split()[-1].lower()   # "Anderssen", "Lagrave", etc.
    winning_games = []

    try:
        with open(pgn_path, encoding="utf-8", errors="ignore") as f:
            while True:
                game = chess.pgn.read_game(f)
                if game is None:
                    break
                result = game.headers.get("Result", "*")
                white  = game.headers.get("White", "").lower()
                black  = game.headers.get("Black", "").lower()

                if result == "1-0" and surname in white:
                    winning_games.append((game, chess.WHITE))
                elif result == "0-1" and surname in black:
                    winning_games.append((game, chess.BLACK))

    except Exception as e:
        print(f"[pgn] Error reading '{pgn_path}': {e}")
        return None

    if not winning_games:
        print(f"[pgn] No winning games for '{display_name}' in '{os.path.basename(pgn_path)}'")
        return None

    game, legend_color = random.choice(winning_games)
    meta = {
        "legend_name":  display_name,
        "legend_color": legend_color,
        "white":        game.headers.get("White", "?"),
        "black":        game.headers.get("Black", "?"),
        "event":        game.headers.get("Event", ""),
        "site":         game.headers.get("Site", ""),
        "date":         game.headers.get("Date", ""),
        "result":       game.headers.get("Result", ""),
        "eco":          game.headers.get("ECO", ""),
    }
    return game, legend_color, meta


def select_legend_and_game(img_folder, pgn_folder, max_attempts=MAX_RESELECT):
    """
    IMAGE-FIRST selection loop.

    For each randomly ordered legend found in IMG_FOLDER:
      1. Look up the matching PGN.
         → Missing PGN: log + skip (reselect).
      2. Find a winning game.
         → None found: log + skip (reselect).
      3. Pick a random photo.
         → No photo: use DEFAULT_IMG (never a blocker).

    Returns (game, meta, img_path) on first success.
    Raises RuntimeError after max_attempts exhausted.
    """
    pgn_index   = build_pgn_index(pgn_folder)
    all_legends = get_all_legend_groups(img_folder)

    if not all_legends:
        raise FileNotFoundError(f"No legend images found in '{img_folder}'")

    attempts = 0
    for info in all_legends:
        if attempts >= max_attempts:
            break
        attempts += 1

        display_name = info["display_name"]
        pgn_key      = info["pgn_key"]
        images       = info["images"]

        print(f"\n[select] Attempt {attempts}: {display_name} (pgn_key='{pgn_key}')")

        # ── 1. Find PGN ──────────────────────────────────────
        pgn_path = find_pgn_for_key(pgn_key, pgn_index)
        if pgn_path is None:
            print(f"[select] ⚠️  No PGN found for '{display_name}' — skipping.")
            continue
        print(f"[select] ✅ PGN: {os.path.basename(pgn_path)}")

        # ── 2. Find a winning game ───────────────────────────
        result = pick_winning_game(pgn_path, display_name)
        if result is None:
            print(f"[select] ⚠️  No winning game — skipping.")
            continue

        game, legend_color, meta = result
        side = "White" if legend_color == chess.WHITE else "Black"
        print(f"[select] ✅ Game: {meta['white']} vs {meta['black']} "
              f"({meta['event']} {meta['date']}) — legend plays as {side}")

        # ── 3. Pick photo (never blocks) ─────────────────────
        if images:
            img_path = random.choice(images)
            print(f"[select] ✅ Photo: {os.path.basename(img_path)}")
        elif os.path.exists(DEFAULT_IMG):
            img_path = DEFAULT_IMG
            print(f"[select] ⚠️  No photos for '{display_name}' — using default image.")
        else:
            img_path = None
            print(f"[select] ⚠️  No photos and no default image — intro card will be photo-free.")

        return game, meta, img_path

    raise RuntimeError(
        f"Could not find a valid legend+game pair after {attempts} attempt(s). "
        "Verify your PGN and image folders."
    )


def extract_moves(game):
    """Walk the main variation and return a list of chess.Move objects."""
    moves = []
    node  = game
    while node.variations:
        next_node = node.variations[0]
        moves.append(next_node.move)
        node = next_node
    return moves


# ─────────────────────────────────────────────
#  DEFAULT PERSON IMAGE
# ─────────────────────────────────────────────

def generate_default_person_png(out_path, size=200):
    """
    Rasterise a simple SVG silhouette to PNG as the default person image.
    Only called once — the file is reused on subsequent runs.
    """
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


# ─────────────────────────────────────────────
#  DRAWING HELPERS
# ─────────────────────────────────────────────

def load_font(size, bold=False):
    path = FONT_BOLD_PATH if bold else FONT_PATH
    for p in [path, FONT_PATH]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def render_board_png(board, last_move=None, flipped=False):
    """
    Render the board with square-colour highlights on the last move.
    White moves → gold tones. Black moves → blue tones. No arrows.
    Returns a PIL RGBA Image.
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
        lastmove=None,        # disable grey default; use fill instead
        fill=fill,
        flipped=flipped,
    ).encode("UTF-8")

    tmp = os.path.join(TEMP_DIR, "_tmp_board.png")
    cairosvg.svg2png(bytestring=svg_data, write_to=tmp)
    return Image.open(tmp).convert("RGBA")


def draw_top_bar(im, meta, move_number, total_moves):
    """Semi-transparent top bar: legend name · opponent · move counter."""
    bar_h = 82
    bar   = Image.new("RGBA", (BOARD_SIZE, bar_h), (10, 10, 10, 185))
    im.paste(bar, (0, 0), bar)
    draw  = ImageDraw.Draw(im, "RGBA")

    fn_lg  = load_font(30, bold=True)
    fn_sm  = load_font(22)
    fn_cnt = load_font(22)

    side     = "White" if meta["legend_color"] == chess.WHITE else "Black"
    opponent = meta["black"] if meta["legend_color"] == chess.WHITE else meta["white"]

    draw.text((14, 8),  meta["legend_name"],        font=fn_lg, fill="#FFD700")
    draw.text((14, 46), f"vs {opponent} · {side}",  font=fn_sm, fill="#CCCCCC")

    ctr  = f"Move {move_number}/{total_moves}"
    bbox = draw.textbbox((0, 0), ctr, font=fn_cnt)
    draw.text((BOARD_SIZE - (bbox[2] - bbox[0]) - 14, 30), ctr,
              font=fn_cnt, fill="#AAAAAA")
    return im


def draw_bottom_bar(im, meta):
    """Slim bottom bar: event · year · ECO."""
    bar_h = 46
    bar   = Image.new("RGBA", (BOARD_SIZE, bar_h), (10, 10, 10, 170))
    im.paste(bar, (0, BOARD_SIZE - bar_h), bar)
    draw  = ImageDraw.Draw(im, "RGBA")

    fn    = load_font(20)
    event = meta["event"] or "?"
    year  = (meta["date"] or "").split(".")[0]
    eco   = meta["eco"] or ""
    draw.text((14, BOARD_SIZE - bar_h + 12),
              f"{event}  ·  {year}  ·  {eco}", font=fn, fill="#AAAAAA")
    return im


ENDGAME_SEC     = 4     # how long the endgame card is shown


# ─────────────────────────────────────────────
#  CALL-TO-ACTION BANNER
# ─────────────────────────────────────────────

def draw_cta_banner(im, compact=False):
    """
    Paste a "Follow Us" CTA banner onto the bottom of a PIL Image.

    compact=False → full two-line banner (used on endgame card)
    compact=True  → single slimmer line (used during final pause)

    The banner sits flush at the bottom of the frame, above the
    bottom info bar when compact=True, or as a standalone block
    when used on the endgame card.
    """
    if not CTA_ENABLED:
        return im

    im   = im.convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")

    main_text = CTA_MAIN_TEXT.format(page=CTA_PAGE_NAME)

    if compact:
        # ── Single-line slim bar ───────────────────────────────
        BAR_H  = 48
        bar_y  = BOARD_SIZE - BAR_H
        bar    = Image.new("RGBA", (BOARD_SIZE, BAR_H), CTA_BG_COLOR)
        im.paste(bar, (0, bar_y), bar)
        draw   = ImageDraw.Draw(im, "RGBA")

        fn     = load_font(22, bold=True)
        fn_sm  = load_font(18)

        # Accent left stripe
        stripe = Image.new("RGBA", (5, BAR_H), (*_hex_to_rgb(CTA_ACCENT_COLOR), 255))
        im.paste(stripe, (0, bar_y), stripe)

        # Icon + main text
        full_txt = f"  {CTA_ICON}  {main_text}"
        draw.text((10, bar_y + 6), full_txt, font=fn, fill=CTA_TEXT_COLOR)

        # Sub text right-aligned
        bbox = draw.textbbox((0, 0), CTA_SUB_TEXT, font=fn_sm)
        tw   = bbox[2] - bbox[0]
        draw.text((BOARD_SIZE - tw - 12, bar_y + 10),
                  CTA_SUB_TEXT, font=fn_sm, fill=CTA_SUB_COLOR)

    else:
        # ── Full two-line prominent banner ────────────────────
        BAR_H  = 72
        bar_y  = BOARD_SIZE - BAR_H
        bar    = Image.new("RGBA", (BOARD_SIZE, BAR_H), CTA_BG_COLOR)
        im.paste(bar, (0, bar_y), bar)

        # Accent top border line
        border = Image.new("RGBA", (BOARD_SIZE, 3),
                           (*_hex_to_rgb(CTA_ACCENT_COLOR), 255))
        im.paste(border, (0, bar_y), border)

        draw  = ImageDraw.Draw(im, "RGBA")
        fn_lg = load_font(28, bold=True)
        fn_sm = load_font(20)

        # Icon + main text (centred)
        full_txt = f"{CTA_ICON}  {main_text}"
        bbox     = draw.textbbox((0, 0), full_txt, font=fn_lg)
        tw       = bbox[2] - bbox[0]
        draw.text(((BOARD_SIZE - tw) // 2, bar_y + 8),
                  full_txt, font=fn_lg, fill=CTA_ACCENT_COLOR)

        # Sub text (centred)
        bbox = draw.textbbox((0, 0), CTA_SUB_TEXT, font=fn_sm)
        tw   = bbox[2] - bbox[0]
        draw.text(((BOARD_SIZE - tw) // 2, bar_y + 44),
                  CTA_SUB_TEXT, font=fn_sm, fill=CTA_SUB_COLOR)

    return im.convert("RGB")


RESULT_LABEL = {
    "1-0":     ("WHITE WINS", "#FFD700"),
    "0-1":     ("BLACK WINS", "#3498DB"),
    "1/2-1/2": ("DRAW",       "#AAAAAA"),
}


def create_endgame_card(meta, board):
    """
    Final card shown after the last move.
    Darkened final board + centred result panel showing:
      - Crown icon + result text  (e.g. WHITE WINS)
      - Legend name
      - Opponent name
      - Event · Year
    """
    flipped = (meta["legend_color"] == chess.BLACK)
    im      = render_board_png(board, flipped=flipped)

    # Dark veil
    overlay = Image.new("RGBA", (BOARD_SIZE, BOARD_SIZE), (0, 0, 0, 185))
    im      = Image.alpha_composite(im, overlay)
    draw    = ImageDraw.Draw(im, "RGBA")

    result_str = meta.get("result", "*")
    label, accent = RESULT_LABEL.get(result_str, ("GAME OVER", "#FFFFFF"))

    # ── Card ──────────────────────────────────────────────────
    CARD_W, CARD_H = 540, 300
    cx = (BOARD_SIZE - CARD_W) // 2
    cy = (BOARD_SIZE - CARD_H) // 2

    card = Image.new("RGBA", (CARD_W, CARD_H), (12, 12, 12, 230))
    im.paste(card, (cx, cy), card)

    # Accent top strip
    strip = Image.new("RGBA", (CARD_W, 8), (*_hex_to_rgb(accent), 255))
    im.paste(strip, (cx, cy), strip)

    draw = ImageDraw.Draw(im, "RGBA")

    fn_result  = load_font(52, bold=True)
    fn_crown   = load_font(44)
    fn_name    = load_font(28, bold=True)
    fn_detail  = load_font(21)

    # Crown + result label
    crown_txt  = "♛ " + label
    bbox       = draw.textbbox((0, 0), crown_txt, font=fn_result)
    tw         = bbox[2] - bbox[0]
    draw.text((cx + (CARD_W - tw) // 2, cy + 22), crown_txt,
              font=fn_result, fill=accent)

    # Thin divider
    div_y = cy + 95
    draw.line([(cx + 30, div_y), (cx + CARD_W - 30, div_y)],
              fill=(80, 80, 80, 200), width=1)

    # Legend name
    legend_txt = meta["legend_name"]
    bbox       = draw.textbbox((0, 0), legend_txt, font=fn_name)
    tw         = bbox[2] - bbox[0]
    draw.text((cx + (CARD_W - tw) // 2, cy + 112),
              legend_txt, font=fn_name, fill="#FFD700")

    # "vs opponent"
    side     = "White" if meta["legend_color"] == chess.WHITE else "Black"
    opponent = meta["black"] if meta["legend_color"] == chess.WHITE else meta["white"]
    vs_txt   = f"vs {opponent}  ·  {side}"
    bbox     = draw.textbbox((0, 0), vs_txt, font=fn_detail)
    tw       = bbox[2] - bbox[0]
    draw.text((cx + (CARD_W - tw) // 2, cy + 158),
              vs_txt, font=fn_detail, fill="#CCCCCC")

    # Event · Year
    event    = meta.get("event") or ""
    year     = (meta.get("date") or "").split(".")[0]
    eco      = meta.get("eco") or ""
    evt_txt  = "  ·  ".join(filter(None, [event, year, eco]))
    if evt_txt:
        bbox = draw.textbbox((0, 0), evt_txt, font=fn_detail)
        tw   = bbox[2] - bbox[0]
        draw.text((cx + (CARD_W - tw) // 2, cy + 192),
                  evt_txt, font=fn_detail, fill="#888888")

    # "Game Over" footer line
    footer = "— Game Over —"
    bbox   = draw.textbbox((0, 0), footer, font=fn_detail)
    tw     = bbox[2] - bbox[0]
    draw.text((cx + (CARD_W - tw) // 2, cy + CARD_H - 38),
              footer, font=fn_detail, fill=(80, 80, 80, 200))

    # ── CTA banner (full, prominent) ──────────────────────────
    im = draw_cta_banner(im.convert("RGB"), compact=False)

    return im


def _hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def create_legend_intro_frame(meta, img_path, board):
    """
    Cinematic intro frame: darkened initial board with a centred legend card
    showing circular photo (or fallback placeholder), name, and game details.
    """
    flipped = (meta["legend_color"] == chess.BLACK)
    im      = render_board_png(board, flipped=flipped)

    # Dark veil over the board
    overlay = Image.new("RGBA", (BOARD_SIZE, BOARD_SIZE), (0, 0, 0, 170))
    im      = Image.alpha_composite(im, overlay)
    draw    = ImageDraw.Draw(im, "RGBA")

    # Card background
    CARD_W, CARD_H = 580, 340
    cx = (BOARD_SIZE - CARD_W) // 2
    cy = (BOARD_SIZE - CARD_H) // 2
    card = Image.new("RGBA", (CARD_W, CARD_H), (15, 15, 15, 225))
    im.paste(card, (cx, cy), card)
    draw = ImageDraw.Draw(im, "RGBA")

    # ── Photo ─────────────────────────────────────────────────
    photo_size = 200
    photo_x    = cx + 30
    photo_y    = cy + (CARD_H - photo_size) // 2

    if img_path and os.path.exists(img_path):
        try:
            photo = Image.open(img_path).convert("RGBA")
            photo = photo.resize((photo_size, photo_size), Image.LANCZOS)
            # Circular crop
            mask = Image.new("L", (photo_size, photo_size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, photo_size, photo_size), fill=255)
            photo.putalpha(mask)
            im.paste(photo, (photo_x, photo_y), photo)
            draw = ImageDraw.Draw(im, "RGBA")
            # Gold border ring
            draw.ellipse(
                (photo_x - 3, photo_y - 3,
                 photo_x + photo_size + 3, photo_y + photo_size + 3),
                outline="#FFD700", width=4
            )
        except Exception as e:
            print(f"[intro] Could not render photo: {e}")
            img_path = None   # fall through to placeholder below

    if not img_path or not os.path.exists(img_path):
        # Placeholder: dark circle + chess pawn emoji
        draw.ellipse(
            (photo_x, photo_y, photo_x + photo_size, photo_y + photo_size),
            fill=(44, 62, 80, 220), outline="#FFD700", width=3
        )
        fn_icon = load_font(80)
        draw.text((photo_x + 55, photo_y + 50), "\u265f", font=fn_icon, fill="#FFD700")

    # ── Text ──────────────────────────────────────────────────
    tx = photo_x + photo_size + 28
    ty = cy + 28

    fn_title  = load_font(34, bold=True)
    fn_sub    = load_font(22)
    fn_detail = load_font(19)

    side     = "White" if meta["legend_color"] == chess.WHITE else "Black"
    opponent = meta["black"] if meta["legend_color"] == chess.WHITE else meta["white"]

    draw.text((tx, ty),      meta["legend_name"], font=fn_title, fill="#FFD700")
    # draw.text((tx, ty + 50), "\u265b Chess Legend",   font=fn_sub,   fill="#AAAAAA")
    draw.text((tx, ty + 50), "Chess Legend",   font=fn_sub,   fill="#AAAAAA")

    lines = [
        f"vs {opponent}",
        f"Playing as {side}",
        meta["event"] or "",
        (meta["date"] or "").split(".")[0],
        f"Result: {meta['result']}",
    ]
    for i, line in enumerate(lines):
        if line:
            draw.text((tx, ty + 100 + i * 30), line, font=fn_detail, fill="#DDDDDD")

    return im.convert("RGB")


def create_game_frame(board, last_move, meta, move_number, total_moves):
    """One game replay frame: board + top bar + bottom bar."""
    flipped = (meta["legend_color"] == chess.BLACK)
    im = render_board_png(board, last_move=last_move, flipped=flipped)
    im = draw_top_bar(im, meta, move_number, total_moves)
    im = draw_bottom_bar(im, meta)
    return im.convert("RGB")


# ─────────────────────────────────────────────
#  FRAME GENERATION
# ─────────────────────────────────────────────
def save_frames(game, moves, meta, img_path):
    frame_count = 0

    def save(img):
        nonlocal frame_count
        img.save(os.path.join(TEMP_DIR, f"frame_{frame_count:05d}.png"))
        frame_count += 1

    def save_n(img, n):
        for _ in range(n):
            save(img)

    board       = game.board()
    total_moves = len(moves)

    # Frames per move — supports fractional seconds (e.g. MOVE_SEC = 0.5)
    move_frames = max(1, round(FPS * MOVE_SEC))

    # 1 ── Legend intro card ───────────────────────────────────
    print("[frames] Rendering intro card...")
    save_n(create_legend_intro_frame(meta, img_path, board), FPS * INTRO_SEC)

    # 2 ── Initial board ───────────────────────────────────────
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


# ─────────────────────────────────────────────
#  VIDEO ENCODING
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_VIDEO), exist_ok=True)

# Ensure the default person silhouette exists (generated once, reused)
if not os.path.exists(DEFAULT_IMG):
    generate_default_person_png(DEFAULT_IMG)

print("=" * 55)
print("  Legendary Chess — Video Generator")
print("=" * 55)

print("\n[main] Selecting legend and game...")
game, meta, img_path = select_legend_and_game(IMG_FOLDER, PGN_FOLDER)

print("\n[main] Extracting moves...")
moves = extract_moves(game)
print(f"[main] {len(moves)} moves to replay.")

intro_file = pick_intro_audio()

print("\n[main] Generating frames...")
save_frames(game, moves, meta, img_path)

print("\n[main] Encoding video...")
encode_video(intro_file=intro_file)

# ── Social copy ────────────────────────────────────────────────

# rotation = [
#     CHESS_LOCATION_PRESETS["india_south"],
#     CHESS_LOCATION_PRESETS["us_chess"],
#     CHESS_LOCATION_PRESETS["norway"],
#     CHESS_LOCATION_PRESETS["russia"],
#     CHESS_LOCATION_PRESETS["china_east"],
#     CHESS_LOCATION_PRESETS["global"],   # None → no tag, pure hashtag reach
# ]

# for i, post_data in enumerate(today_posts):
#     uploader.upload_video_from_url_to_reel_production(
#         video_url   = post_data["url"],
#         description = post_data["caption"],
#         location    = rotation[i % len(rotation)],
#     )

opponent    = meta["black"] if meta["legend_color"] == chess.WHITE else meta["white"]
msg         = random.choice(MESSAGES).format(legend=meta["legend_name"], opponent=opponent)
tags        = " ".join(random.sample(HASHTAGS, 4))
safe_msg    = f"{msg} {tags}".encode("ascii", "ignore").decode().strip()

print(f"\n📢  Social copy:\n{safe_msg}\n")

video_url = f"https://roynek.com/Chess_Sol_Puzzles/auto_post_legends/{OUTPUT_VIDEO}"
game_link = "https://roynek.com/Chess_Sol_Puzzles/public/"

output = send_to_social_media_api(
    platform='facebook', link=game_link, text=safe_msg,
    media=video_url, area='6', fb_post_to="reels"
)
print("Facebook API Response:", output)

output_x = send_to_social_media_api(
    platform='x', link=game_link, text=safe_msg,
    media=video_url, area='21'
)
print("X API Response:", output_x)

# ── Cleanup ────────────────────────────────────────────────────
for f in os.listdir(TEMP_DIR):
    os.remove(os.path.join(TEMP_DIR, f))
os.rmdir(TEMP_DIR)

print(f"\n✅  Done — video saved to: {OUTPUT_VIDEO}")