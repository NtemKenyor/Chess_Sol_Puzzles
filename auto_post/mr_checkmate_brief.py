import os
import chess
import chess.svg
import cairosvg
import pickle
import math
import json
import random
import shutil
import subprocess
import requests

from PIL import Image, ImageDraw, ImageFont
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import time

# ═══════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════
NUM_PUZZLES   = 1
FPS           = 30
COUNTDOWN_SEC = 15
INTRO_SEC     = 3
ARROW_SEC     = 1
MOVE_SEC      = 1
FINAL_SEC     = 3
BREAK_SEC     = 2

TEMP_DIR      = "frames_mates"
OUTPUT_VIDEO  = "output_video/chess_short_mate_monetised.mp4"
FONT_PATH     = "./Roboto-Regular.ttf"
BOARD_SIZE    = 800

# ── Intro Audio ───────────────────────────────────────────
# ls = ["./intro_sounds", "/intro_fake"]
ls = ["/intro_fake"]
INTRO_AUDIO_DIR = random.choice(ls)

# ── Background & Click Audio ──────────────────────────────
BACKGROUND_MUSIC = "bg_music_free2.mp3"
# BACKGROUND_MUSIC = "bg_music.mp3" #whale shout and lion roar - in dispute
CLICK_SOUND      = "move.mp3"
BG_MUSIC_VOLUME  = 0.12
CLICK_VOLUME     = 0.65
INCLUDE_BG_MUSIC = True

# ── Arrow Colors ──────────────────────────────────────────
ARROW_COLOR_SOLVER   = (255, 215,   0, 230)   # gold    #FFD700
ARROW_COLOR_OPPONENT = (255,  87,  34, 210)   # orange  #FF5722

# ═══════════════════════════════════════════════════════════
#  BOARD COLOR THEMES  ← NEW
# ═══════════════════════════════════════════════════════════
BOARD_COLOR_THEMES = [
    {
        "name": "Classic",
        "square light":       "#F0D9B5",
        "square dark":        "#B58863",
        "square light lastmove": "#CDD26A",
        "square dark lastmove":  "#AABA44",
    },
    {
        "name": "Ocean Blue",
        "square light":       "#DEE3E6",
        "square dark":        "#4A90D9",
        "square light lastmove": "#A8C8E8",
        "square dark lastmove":  "#2E72B8",
    },
    {
        "name": "Forest Green",
        "square light":       "#FFFFDD",
        "square dark":        "#4A7C59",
        "square light lastmove": "#D4F0A0",
        "square dark lastmove":  "#2E6B3A",
    },
    {
        "name": "Royal Purple",
        "square light":       "#EDE6F2",
        "square dark":        "#7B5EA7",
        "square light lastmove": "#D4B8E0",
        "square dark lastmove":  "#5E3F8A",
    },
    {
        "name": "Sunset",
        "square light":       "#FFF0E0",
        "square dark":        "#C8602A",
        "square light lastmove": "#FFD0A0",
        "square dark lastmove":  "#A84010",
    },
    {
        "name": "Slate",
        "square light":       "#D8DDE0",
        "square dark":        "#546E7A",
        "square light lastmove": "#B0BEC5",
        "square dark lastmove":  "#37474F",
    },
]

# Pick ONE theme randomly for the entire video run
SELECTED_THEME = random.choice(BOARD_COLOR_THEMES)
print(f"[theme] Board color theme: {SELECTED_THEME['name']}")

# ── Checkmate Puzzle Themes ───────────────────────────────
PUZZLE_THEMES = [
    {"addon": "CHECKMATE", "random": "true"},
]

# ── Social Copy ───────────────────────────────────────────
SOCIAL_MESSAGES = [
    "Can you find the checkmate in all {n} puzzles? 👑 Drop your score!",
    "{n} checkmate puzzles — how many did you see coming?",
    "Checkmate challenge 🔥 — {n} real-game mates, can you ace them?",
    "Train like a GM — {n} checkmate sequences back to back!",
    "These {n} checkmates happened in real games — would you have seen them?",
]

YT_TITLES = [
    "Can You Find the Checkmate? {n} Real Game Puzzles",
    "{n} Checkmate Puzzles — Only GrandMasters Get Them All",
    "Checkmate in Every Puzzle — {n} Tactical Challenges",
    "{n} Real Checkmates — How Many Can You Spot?",
    "The King Has No Escape — {n} Checkmate Challenges",
]

HASHTAGS = [
    "#ChessTactics", "#ChessStrategy", "#Checkmate", "#Grandmaster",
    "#Chess", "#ChessReels", "#BoardGames", "#ChessPunks", "#ChessSol",
    "#LearnChess", "#ChessMasterclass", "#ChessTips", "#PuzzleSolving",
    "#MentalGym", "#StrategicThinking", "#SpeedChess", "#CheckmateChallenge",
    "#ChessMarathon",
]

# ── Platform Toggles ──────────────────────────────────────
YT_CLIENT_SECRETS = "secrets/client_secrets.json"
YT_TOKEN_FILE     = "secrets/token.pickle"
YT_SCOPES         = ["https://www.googleapis.com/auth/youtube.upload"]
UPLOAD_TO_YOUTUBE = False
POST_TO_FACEBOOK  = True
FB_AREA           = "10"
FB_POST_TO        = "reels"


# ═══════════════════════════════════════════════════════════
#  CHECKMATE VERIFICATION
# ═══════════════════════════════════════════════════════════

def verify_puzzle(fen, moves):
    try:
        board = chess.Board(fen)
        for uci in moves:
            board.push(chess.Move.from_uci(uci))

        confirmed = board.is_checkmate()
        n_solver  = math.ceil(len(moves) / 2)

        if confirmed:
            mate_label      = f"Mate in {n_solver}"
            puzzle_type     = "checkmate"
            board_message   = _pick_checkmate_message(n_solver)
            final_message   = "♚ Checkmate!"
            transition_hint = f"Next: {mate_label}"
        else:
            mate_label      = ""
            puzzle_type     = _classify_non_mate(board, moves)
            board_message   = _pick_non_mate_message(puzzle_type)
            final_message   = "✓ Puzzle complete!"
            transition_hint = _non_mate_transition(puzzle_type)

        return {
            "is_confirmed_mate": confirmed,
            "solver_move_count": n_solver,
            "mate_label":        mate_label,
            "puzzle_type":       puzzle_type,
            "board_message":     board_message,
            "final_message":     final_message,
            "transition_hint":   transition_hint,
        }

    except Exception as e:
        print(f"  [verify] ⚠ Exception during verification: {e}")
        return {
            "is_confirmed_mate": False,
            "solver_move_count": 0,
            "mate_label":        "",
            "puzzle_type":       "tactics",
            "board_message":     "Find the best move!",
            "final_message":     "✓ Puzzle complete!",
            "transition_hint":   "Next: Tactics puzzle",
        }


def _classify_non_mate(board, moves):
    if board.is_check():
        return "combination"
    piece_count = len(board.piece_map())
    if piece_count <= 10:
        return "endgame"
    return "tactics"


def _pick_checkmate_message(n_solver):
    msgs_by_depth = {
        1: [
            "Checkmate in 1 — can you see it?",
            "One move wins — find it!",
            "The king is trapped — finish it!",
        ],
        2: [
            "Checkmate is near — can you see it?",
            "Find the Mate in 2!",
            "Two moves to end the game!",
            "This checkmate happened in a real game!",
        ],
        3: [
            "Mate in 3 — only a GrandMaster sees this!",
            "Find the forced Mate in 3!",
            "Three moves to checkmate — spot the sequence!",
        ],
    }
    msgs_deep = [
        "Deep combination leading to checkmate!",
        "The king has nowhere to run!",
        "Spot the forced mate sequence!",
        "Only a GrandMaster can spot this mate!",
    ]
    pool = msgs_by_depth.get(n_solver, msgs_deep)
    return random.choice(pool)


def _pick_non_mate_message(puzzle_type):
    msgs = {
        "endgame": [
            "Endgame strategy — find the winning plan!",
            "Convert this endgame advantage!",
            "Technique wins in the endgame!",
            "Master the endgame — find the plan!",
        ],
        "combination": [
            "Tactical combination — possible checkmate ahead!",
            "Find the winning combination!",
            "A GrandMaster combination — can you see it?",
        ],
        "tactics": [
            "Best move wins material — find it!",
            "Tactical puzzle — spot the winning move!",
            "Find the strongest continuation!",
            "Sharp tactics — what would you play?",
        ],
    }
    pool = msgs.get(puzzle_type, msgs["tactics"])
    return random.choice(pool)


def _non_mate_transition(puzzle_type):
    hints = {
        "endgame":     "Next: Endgame Strategy",
        "combination": "Next: Tactical Combination",
        "tactics":     "Next: Tactics Puzzle",
    }
    return hints.get(puzzle_type, "Next: Puzzle")


# ═══════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════
def detect_ffmpeg():
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin
    local_bin = "./ffmpeg-7.0.2-amd64-static/ffmpeg"
    if os.path.exists(local_bin):
        os.chmod(local_bin, 0o755)
        return local_bin
    raise FileNotFoundError("FFmpeg not found. Install via: sudo apt install ffmpeg")

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
        print(f"[intro] No audio files in '{INTRO_AUDIO_DIR}' — skipping intro audio.")
        return None
    chosen = random.choice(files)
    print(f"[intro] Selected: {os.path.basename(chosen)}")
    return chosen


def fetch_puzzles(target_count):
    seen_ids = set()
    unique   = []
    max_rounds = 3

    for round_num in range(max_rounds):
        if len(unique) >= target_count:
            break
        print(f"\n[fetch] Round {round_num + 1} — need {target_count - len(unique)} more")

        for theme_cfg in PUZZLE_THEMES:
            if len(unique) >= target_count:
                break
            try:
                params  = {**theme_cfg, "limit": 100, "random": "true"}
                url     = "https://roynek.com/Chess_Sol_Puzzles/api/puzzles"
                print(f"  Fetching: {params}")
                resp    = requests.get(url, params=params, timeout=30)
                data    = resp.json()
                results = data.get("results", [])
                random.shuffle(results)

                before = len(unique)
                for p in results:
                    pid = p.get("id")
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        unique.append(p)

                print(f"  → +{len(unique) - before} new (pool: {len(unique)}/{target_count})")
            except Exception as e:
                print(f"  ✗ Error fetching theme {theme_cfg}: {e}")

    random.shuffle(unique)
    selected = unique[:target_count]
    print(f"\n[fetch] Collected: {len(unique)} | Selected: {len(selected)}")
    if len(selected) < target_count:
        print(f"[fetch] ⚠ Only {len(selected)} puzzles available")
    return selected


# ═══════════════════════════════════════════════════════════
#  SOCIAL MEDIA
# ═══════════════════════════════════════════════════════════
def send_to_social_media_api(platform, link, text, media=None, area=None,
                              x_comm_id=None, fb_post_to=None):
    api_url = f"https://roynek.com/alltrenders/codes/python_API/social-media/{platform}"
    payload = {
        "link_2_post": link, "message": text, "media": media,
        "pages_ordered_ids": area, "comm_id": x_comm_id, "post_to": fb_post_to,
    }
    headers = {"Content-Type": "application/json"}
    print(json.dumps(payload, ensure_ascii=False))
    try:
        r = requests.post(api_url, json=payload, headers=headers, timeout=3000)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print("Social Media Error:", e)
        return None


# ═══════════════════════════════════════════════════════════
#  YOUTUBE UPLOAD
# ═══════════════════════════════════════════════════════════
def get_youtube_service():
    creds = None
    if os.path.exists(YT_TOKEN_FILE):
        with open(YT_TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(YT_CLIENT_SECRETS, YT_SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(YT_TOKEN_FILE), exist_ok=True)
        with open(YT_TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)


def send_to_youtube(video_path, title, description, tags=None,
                    privacy="public", made_for_kids=False):
    if not os.path.exists(video_path):
        print(f"[youtube] ✗ File not found: {video_path}")
        return None
    try:
        youtube = get_youtube_service()
        body = {
            "snippet": {
                "title":       title[:100],
                "description": description[:5000],
                "tags":        tags or [],
                "categoryId":  "20",
            },
            "status": {
                "privacyStatus":           privacy,
                "selfDeclaredMadeForKids": made_for_kids,
            },
        }
        media   = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media,
        )
        print(f"[youtube] Uploading: {video_path}")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[youtube] {int(status.progress() * 100)}% uploaded...")
        video_id = response.get("id")
        print(f"[youtube] ✅ Done — https://youtube.com/watch?v={video_id}")
        return video_id
    except Exception as e:
        print(f"[youtube] ✗ Upload failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════
#  DRAWING HELPERS
# ═══════════════════════════════════════════════════════════
SQUARE_SIZE = BOARD_SIZE // 8

def square_to_pixel(square):
    col = chess.square_file(square)
    row = 7 - chess.square_rank(square)
    return col * SQUARE_SIZE + SQUARE_SIZE // 2, row * SQUARE_SIZE + SQUARE_SIZE // 2


def draw_arrow(draw, from_sq, to_sq, color=(255, 170, 0, 220), shaft_w=18, head_size=36):
    x1, y1 = square_to_pixel(from_sq)
    x2, y2 = square_to_pixel(to_sq)
    angle   = math.atan2(y2 - y1, x2 - x1)
    tip_x   = x2 - head_size * 0.6 * math.cos(angle)
    tip_y   = y2 - head_size * 0.6 * math.sin(angle)
    dx, dy  = math.sin(angle) * shaft_w / 2, math.cos(angle) * shaft_w / 2
    draw.polygon([
        (x1 + dx, y1 - dy), (x1 - dx, y1 + dy),
        (tip_x - dx, tip_y + dy), (tip_x + dx, tip_y - dy),
    ], fill=color)
    px, py = math.sin(angle) * head_size, math.cos(angle) * head_size
    draw.polygon([
        (x2, y2),
        (tip_x + px, tip_y - py),
        (tip_x - px, tip_y + py),
    ], fill=color)


def load_fonts():
    try:
        return (
            ImageFont.truetype(FONT_PATH, 60),
            ImageFont.truetype(FONT_PATH, 30),
            ImageFont.truetype(FONT_PATH, 24),
            ImageFont.truetype(FONT_PATH, 18),   # small — for watermark
        )
    except Exception:
        fb = ImageFont.load_default()
        return fb, fb, fb, fb


def draw_watermark(im, draw, font_wm):
    """
    Draw a semi-transparent 'Mr. Checkmate' sticker in the bottom-right corner.
    Uses a rounded pill background with a king icon + brand text.
    """
    icon_text  = "♚ Mr. Checkmate"
    padding_x  = 14
    padding_y  = 8
    margin     = 12          # distance from the edge

    tb   = draw.textbbox((0, 0), icon_text, font=font_wm)
    tw   = tb[2] - tb[0]
    th   = tb[3] - tb[1]

    box_w = tw + padding_x * 2
    box_h = th + padding_y * 2
    x1    = BOARD_SIZE - box_w - margin
    y1    = BOARD_SIZE - box_h - margin
    x2    = BOARD_SIZE - margin
    y2    = BOARD_SIZE - margin

    # Semi-transparent dark pill
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    radius  = box_h // 2
    ov_draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=(0, 0, 0, 160))
    im.alpha_composite(overlay)

    # Re-get draw handle after composite
    draw2 = ImageDraw.Draw(im, "RGBA")
    draw2.text(
        (x1 + padding_x, y1 + padding_y),
        icon_text, font=font_wm, fill="#FFD700"
    )


def create_frame_image(board, last_move=None, arrow_move=None, arrow_color=None,
                       timer=None, rating=None, side_to_move=None,
                       puzzle_num=None, total_puzzles=None, message=None,
                       mate_label=None):
    # ── Board SVG with selected color theme ──────────────
    svg_data = chess.svg.board(
        board,
        size=BOARD_SIZE,
        lastmove=last_move,
        flipped=False,
        colors=SELECTED_THEME,   # ← inject the random theme
    ).encode("UTF-8")
    tmp_png = os.path.join(TEMP_DIR, "_tmp_frame.png")
    cairosvg.svg2png(bytestring=svg_data, write_to=tmp_png)

    im   = Image.open(tmp_png).convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")

    if arrow_move is not None:
        draw_arrow(draw, arrow_move.from_square, arrow_move.to_square,
                   color=arrow_color or ARROW_COLOR_SOLVER)

    font_lg, font_md, font_sm, font_wm = load_fonts()

    # Top bar
    bar = Image.new("RGBA", (BOARD_SIZE, 95), (0, 0, 0, 170))
    im.paste(bar, (0, 0), bar)
    draw = ImageDraw.Draw(im, "RGBA")

    # Puzzle counter (top-right)
    if puzzle_num and total_puzzles:
        pt = f"Puzzle {puzzle_num}/{total_puzzles}"
        pb = draw.textbbox((0, 0), pt, font=font_sm)
        draw.text((BOARD_SIZE - (pb[2] - pb[0]) - 14, 10), pt, font=font_sm, fill="#AAAAAA")

    # Mate label (top-right, below counter)
    if mate_label:
        mb = draw.textbbox((0, 0), mate_label, font=font_sm)
        draw.text((BOARD_SIZE - (mb[2] - mb[0]) - 14, 38), mate_label,
                  font=font_sm, fill="#FF4444")

    # Rating + side (top-left)
    draw.text((14, 10), f"Rating: {rating}",       font=font_sm, fill="white")
    draw.text((14, 40), f"{side_to_move} to move", font=font_md, fill="#FFD700")

    # Bottom message
    if message:
        msg_bar = Image.new("RGBA", (BOARD_SIZE, 42), (0, 0, 0, 150))
        im.paste(msg_bar, (0, BOARD_SIZE - 42), msg_bar)
        draw = ImageDraw.Draw(im, "RGBA")
        tb   = draw.textbbox((0, 0), message, font=font_sm)
        draw.text(((BOARD_SIZE - (tb[2] - tb[0])) // 2, BOARD_SIZE - 36),
                  message, font=font_sm, fill="lightblue")

    # Countdown
    if timer is not None:
        draw = ImageDraw.Draw(im, "RGBA")
        txt  = str(timer)
        bbox = draw.textbbox((0, 0), txt, font=font_lg)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        cx, cy = (BOARD_SIZE - w) // 2, (BOARD_SIZE - h) // 2
        draw.text((cx + 3, cy + 3), txt, font=font_lg, fill=(0, 0, 0, 180))
        draw.text((cx,     cy),     txt, font=font_lg, fill="white")

    # ── Watermark sticker ─────────────────────────────────
    draw_watermark(im, draw, font_wm)

    return im.convert("RGB")


def create_transition_frame(next_puzzle_num, total_puzzles,
                            mate_label="", transition_hint=""):
    im   = Image.new("RGBA", (BOARD_SIZE, BOARD_SIZE), (20, 20, 30, 255))
    draw = ImageDraw.Draw(im)
    font_lg, font_md, font_sm, font_wm = load_fonts()

    draw.rectangle([(0, 0),              (BOARD_SIZE, 8)],          fill="#FFD700")
    draw.rectangle([(0, BOARD_SIZE - 8), (BOARD_SIZE, BOARD_SIZE)], fill="#FFD700")

    icon  = "♚"
    ib    = draw.textbbox((0, 0), icon, font=font_lg)
    draw.text(((BOARD_SIZE - (ib[2] - ib[0])) // 2, 170), icon, font=font_lg, fill="#FFD700")

    heading = "Next Puzzle"
    hb      = draw.textbbox((0, 0), heading, font=font_md)
    draw.text(((BOARD_SIZE - (hb[2] - hb[0])) // 2, 270), heading, font=font_md, fill="white")

    num_txt = f"{next_puzzle_num} / {total_puzzles}"
    nb      = draw.textbbox((0, 0), num_txt, font=font_md)
    draw.text(((BOARD_SIZE - (nb[2] - nb[0])) // 2, 320), num_txt, font=font_md, fill="#FFD700")

    label_to_show = mate_label if mate_label else transition_hint
    label_color   = "#FF4444" if mate_label else "#AAAAAA"
    if label_to_show:
        lb = draw.textbbox((0, 0), label_to_show, font=font_sm)
        draw.text(((BOARD_SIZE - (lb[2] - lb[0])) // 2, 375),
                  label_to_show, font=font_sm, fill=label_color)

    tips = [
        "The king has nowhere to run  ♟",
        "Find the forced checkmate!",
        "Every move leads to mate  ⚡",
        "A GrandMaster would nail this",
        "Think ahead — the mate is there",
    ]
    tip = random.choice(tips)
    tb  = draw.textbbox((0, 0), tip, font=font_sm)
    draw.text(((BOARD_SIZE - (tb[2] - tb[0])) // 2, 440), tip, font=font_sm, fill="#888888")

    # Watermark on transition card too
    draw_watermark(im, draw, font_wm)

    return im.convert("RGB")


# ═══════════════════════════════════════════════════════════
#  FRAME GENERATION
# ═══════════════════════════════════════════════════════════
def save_puzzle_frames(board, moves, rating, side_to_move,
                       puzzle_num, total_puzzles, frame_count,
                       verification):
    def save(img):
        nonlocal frame_count
        img.save(os.path.join(TEMP_DIR, f"frame_{frame_count:06d}.png"))
        frame_count += 1

    def save_n(img, n):
        for _ in range(n):
            save(img)

    working = board.copy()
    common  = dict(
        rating=rating, side_to_move=side_to_move,
        puzzle_num=puzzle_num, total_puzzles=total_puzzles,
        message=verification["board_message"],
        mate_label=verification["mate_label"],
    )

    # 1 ── Intro hold
    save_n(create_frame_image(working, **common), FPS * INTRO_SEC)

    # 2 ── Move loop
    for i, move_uci in enumerate(moves):
        move        = chess.Move.from_uci(move_uci)
        is_solver   = (i % 2 == 1)
        arrow_color = ARROW_COLOR_SOLVER if is_solver else ARROW_COLOR_OPPONENT

        save_n(create_frame_image(working, arrow_move=move,
                                  arrow_color=arrow_color, **common),
               FPS * ARROW_SEC)

        working.push(move)

        if i == 0:
            for sec in range(COUNTDOWN_SEC, 0, -1):
                save_n(create_frame_image(working, last_move=move,
                                          timer=sec, **common), FPS)
        else:
            sol_common = {**common, "message": "Solution!"}
            save_n(create_frame_image(working, last_move=move, **sol_common),
                   FPS * MOVE_SEC)

    # 3 ── Final pause
    final_common = {**common, "message": verification["final_message"]}
    save_n(create_frame_image(working, **final_common), FPS * FINAL_SEC)

    return frame_count


def save_transition_frames(next_puzzle_num, total_puzzles, frame_count,
                           next_verification):
    im = create_transition_frame(
        next_puzzle_num, total_puzzles,
        mate_label      = next_verification["mate_label"],
        transition_hint = next_verification["transition_hint"],
    )
    for _ in range(FPS * BREAK_SEC):
        im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:06d}.png"))
        frame_count += 1
    return frame_count


# ═══════════════════════════════════════════════════════════
#  VIDEO ENCODING
# ═══════════════════════════════════════════════════════════
def encode_video(intro_file=None):
    video_part   = f"-framerate {FPS} -i {TEMP_DIR}/frame_%06d.png"
    has_intro    = intro_file is not None and os.path.exists(intro_file)
    has_music    = INCLUDE_BG_MUSIC and os.path.exists(BACKGROUND_MUSIC)
    has_click    = os.path.exists(CLICK_SOUND)
    inputs       = []
    filter_parts = []
    mix_labels   = []
    idx          = 1

    if has_intro:
        inputs.append(f"-i {intro_file}")
        filter_parts.append(f"[{idx}:a]volume=1.0[intro]")
        mix_labels.append("[intro]")
        idx += 1
    if has_music:
        inputs.append(f"-stream_loop -1 -i {BACKGROUND_MUSIC}")
        filter_parts.append(f"[{idx}:a]volume={BG_MUSIC_VOLUME}[bg]")
        mix_labels.append("[bg]")
        idx += 1
    if has_click:
        inputs.append(f"-i {CLICK_SOUND}")
        filter_parts.append(f"[{idx}:a]volume={CLICK_VOLUME}[clk]")
        mix_labels.append("[clk]")
        idx += 1

    inputs_str = " ".join(inputs)
    n_audio    = len(mix_labels)

    if n_audio == 0:
        cmd = (f"{FFMPEG_BIN} -y {video_part} "
               f"-c:v libx264 -pix_fmt yuv420p -preset medium -crf 23 {OUTPUT_VIDEO}")
    elif n_audio == 1:
        label = mix_labels[0].strip("[]")
        cmd   = (f"{FFMPEG_BIN} -y {video_part} {inputs_str} "
                 f'-filter_complex "{filter_parts[0]}" '
                 f"-map 0:v -map [{label}] "
                 f"-c:v libx264 -pix_fmt yuv420p -preset medium -crf 23 -shortest {OUTPUT_VIDEO}")
    else:
        mix_str = "".join(mix_labels)
        filter_parts.append(
            f"{mix_str}amix=inputs={n_audio}:duration=longest:normalize=0[aout]"
        )
        fc  = ";".join(filter_parts)
        cmd = (f"{FFMPEG_BIN} -y {video_part} {inputs_str} "
               f'-filter_complex "{fc}" '
               f"-map 0:v -map [aout] "
               f"-c:v libx264 -pix_fmt yuv420p -preset medium -crf 23 -shortest {OUTPUT_VIDEO}")

    print("\n[ffmpeg]", cmd[:240], "...")
    subprocess.run(cmd, shell=True, check=True)


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_VIDEO), exist_ok=True)

print("=" * 60)
print("  CHESS CHECKMATE MARATHON VIDEO GENERATOR")
print("=" * 60)

intro_file = pick_intro_audio()

# ── 1. Fetch puzzles ──────────────────────────────────────
print(f"\n[1/4] Fetching {NUM_PUZZLES} unique checkmate puzzles...")
puzzles       = fetch_puzzles(NUM_PUZZLES)
total_puzzles = len(puzzles)

if total_puzzles == 0:
    print("✗  No puzzles fetched. Exiting.")
    exit(1)

# ── 2. Verify every puzzle before touching the frames ─────
print(f"\n[2/4] Verifying {total_puzzles} puzzles by playing out all moves...")
verified_puzzles = []

confirmed_mates = 0
non_mates       = 0

for puzzle_data in puzzles:
    try:
        moves = puzzle_data.get("moves", [])
        if isinstance(moves, str):
            moves = moves.split()
        if not moves:
            print(f"  ✗ Puzzle {puzzle_data.get('id', '?')} has no moves — skipping.")
            continue

        fen          = puzzle_data["fen"]
        board        = chess.Board(fen)
        rating       = puzzle_data.get("rating", "N/A")
        solver_color = not board.turn
        side_to_move = "White" if solver_color == chess.WHITE else "Black"

        v = verify_puzzle(fen, moves)

        status_icon = "♚" if v["is_confirmed_mate"] else "~"
        print(f"  {status_icon} ID {puzzle_data.get('id', '?'):>8}  "
              f"rating={rating}  {v['mate_label'] or v['puzzle_type']:>20}  "
              f"{side_to_move} to move")

        if v["is_confirmed_mate"]:
            confirmed_mates += 1
        else:
            non_mates += 1

        verified_puzzles.append((board, moves, rating, side_to_move, v))

    except Exception as e:
        print(f"  ✗ Error verifying puzzle {puzzle_data.get('id', '?')}: {e}")
        continue

print(f"\n  ✅ Confirmed mates : {confirmed_mates}")
print(f"  ⚠  Non-mates       : {non_mates}  (will show as endgame/tactics)")
total_puzzles = len(verified_puzzles)

if total_puzzles == 0:
    print("✗  No valid puzzles after verification. Exiting.")
    exit(1)

# ── 3. Generate frames ────────────────────────────────────
print(f"\n[3/4] Generating frames for {total_puzzles} puzzles...")
frame_count = 0

for idx, (board, moves, rating, side_to_move, verification) in \
        enumerate(verified_puzzles, 1):

    print(f"\n  Puzzle {idx}/{total_puzzles}  "
          f"{verification['mate_label'] or verification['puzzle_type']}  "
          f"({side_to_move} to move)")

    frame_count = save_puzzle_frames(
        board, moves, rating, side_to_move,
        idx, total_puzzles, frame_count, verification,
    )

    if idx < total_puzzles:
        _, _, _, _, next_v = verified_puzzles[idx]
        frame_count = save_transition_frames(
            idx + 1, total_puzzles, frame_count, next_v
        )

    print(f"  ✓ Frames so far: {frame_count}")

# ── 4. Encode ─────────────────────────────────────────────
print(f"\n[4/4] Encoding video — {frame_count} frames...")
encode_video(intro_file=intro_file)

time.sleep(random.randint(5, 10))

# ── 5. Social copy ────────────────────────────────────────
social_msg   = random.choice(SOCIAL_MESSAGES).format(n=total_puzzles)
yt_title_raw = random.choice(YT_TITLES).format(n=total_puzzles)
tags_sample  = " ".join(random.sample(HASHTAGS, 4))
safe_message = f" {social_msg} {tags_sample} . ".encode("ascii", "ignore").decode().strip()
video_url    = f"https://roynek.com/Chess_Sol_Puzzles/auto_post/{OUTPUT_VIDEO}"
puzzle_link  = ""

duration_s   = frame_count / FPS
duration_m   = duration_s / 60

print(f"\n📢  Social copy : {social_msg}")
print(f"    YT title    : {yt_title_raw}")

# ── 6. Facebook ───────────────────────────────────────────
print("\n  → Posting to platforms...")
if POST_TO_FACEBOOK:
    fb_out = send_to_social_media_api(
        platform="facebook", link=puzzle_link, text=safe_message,
        media=video_url, area=FB_AREA, fb_post_to=FB_POST_TO,
    )
    print(f"  Facebook: {fb_out}")
else:
    print("  Facebook posting disabled.")

# ── 7. YouTube ────────────────────────────────────────────
if UPLOAD_TO_YOUTUBE:
    yt_desc = (
        f"{social_msg}\n\n"
        f"{total_puzzles} checkmate puzzles from real games — "
        f"can you spot every forced mate before the timer runs out?\n\n"
        f"Drop your score in the comments!\n\n"
        f"#Chess #Checkmate #ChessPuzzles #ChessTactics #ChessMarathon"
    )
    yt_tags = [
        "chess", "checkmate", "chess puzzles", "chess tactics",
        "mate in 2", "mate in 3", "chess challenge", "grandmaster",
        "brain teaser", "chesssol",
    ]
    send_to_youtube(
        video_path=OUTPUT_VIDEO, title=yt_title_raw,
        description=yt_desc, tags=yt_tags, privacy="public",
    )
else:
    print("  YouTube upload disabled.")

# ── 8. Cleanup ────────────────────────────────────────────
print("\nCleaning up temporary frames...")
for f in os.listdir(TEMP_DIR):
    os.remove(os.path.join(TEMP_DIR, f))
os.rmdir(TEMP_DIR)

print("\n" + "=" * 60)
print("  DONE!")
print("=" * 60)
print(f"  Output          : {OUTPUT_VIDEO}")
print(f"  Board theme     : {SELECTED_THEME['name']}")
print(f"  Puzzles total   : {total_puzzles}")
print(f"  Confirmed mates : {confirmed_mates}")
print(f"  Non-mates       : {non_mates}")
print(f"  Total frames    : {frame_count}")
print(f"  Duration        : {duration_m:.1f} min  ({duration_s:.0f} sec)")
print("=" * 60)