import os
import chess
import chess.svg
import cairosvg
from PIL import Image, ImageDraw, ImageFont
import subprocess
import requests
import random
import shutil
import json
import math
import datetime

import content_engine as ce

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
FPS           = 30
INTRO_SEC     = 3           # hold initial board before any move
ARROW_SEC     = 2           # show arrow before each move executes
MOVE_SEC      = 2           # hold board after each move
FINAL_SEC     = 3           # pause at the very end
HOOK_SEC      = 2           # attention-grabbing opener, first 2 seconds

TEMP_DIR      = "frames"
OUTPUT_VIDEO  = "output_video/chess_short.mp4"
FONT_PATH     = "./Roboto-Regular.ttf"
BOARD_SIZE    = 800

# ── Intro Audio ───────────────────────────────────────────
INTRO_AUDIO_DIR = "./intro_sounds"

# ── Background & Click Audio (folders = real variety) ─────
BACKGROUND_MUSIC_DIR = "./music_sounds"
CLICK_SOUND_DIR       = "./click_sounds"
BACKGROUND_MUSIC = "bg_music_free.wav"   # fallback if dir absent
CLICK_SOUND      = "move.mp3"            # fallback if dir absent
BG_MUSIC_VOLUME  = 0.15
CLICK_VOLUME     = 0.65
INCLUDE_BG_MUSIC = True

# ── Social copy ───────────────────────────────────────────
MESSAGES = [
    "Can you find the winning move? ({side} to move)",
    "Today's daily challenge — {side} to move!",
    "Test your tactics ({rating}) — {side} to move!",
    "What is the best move here? ({side} to play)",
    "Spot the winning sequence! ({side})",
]
HASHTAGS = ["#ChessTactics", "#ChessStrategy", "#Checkmate", "#Grandmaster",
            "#Chess", "#ChessReels", "#BoardGames", "#ChessSol",
            "#LearnChess", "#ChessTips", "#PuzzleSolving", "#MentalGym",
            "#StrategicThinking", "#SpeedChess"]


# ═══════════════════════════════════════════════════════════
#  PER-VIDEO "RECIPE" — picked once, never repeats back-to-back
# ═══════════════════════════════════════════════════════════
BOARD_THEME     = ce.pick_unique("reels_board_theme", ce.BOARD_THEMES)
FONT_STYLE      = ce.pick_unique("reels_font_style", ce.FONT_STYLES)
ARROW_PAIR      = ce.pick_unique("reels_arrow_pair", ce.ARROW_COLOR_PAIRS)
ZOOM_VARIANT    = ce.pick_unique("reels_zoom", ce.ZOOM_VARIANTS)
COUNTDOWN_STYLE = ce.pick_unique("reels_countdown", ce.COUNTDOWN_STYLES)
HOOK_TEXT       = ce.pick_unique("reels_hook", ce.HOOKS)
CTA_TEXT        = ce.pick_unique("reels_cta", ce.CTAS)
SERIES          = ce.todays_series()

COUNTDOWN_SEC = COUNTDOWN_STYLE["seconds"]
ARROW_COLOR_SOLVER   = ARROW_PAIR["solver"]
ARROW_COLOR_OPPONENT = ARROW_PAIR["opponent"]

# Pull today's series rating band instead of a hardcoded min=1600 — gives
# real difficulty variety across the week (growth-plan point #3/#4)
API_URL = (
    "https://roynek.com/Chess_Sol_Puzzles/api/puzzle/random-by-rating"
    f"?min={SERIES['min']}&max={SERIES['max']}"
)

print("─" * 60)
print("  Recipe for this video:")
print(f"    Board theme : {BOARD_THEME['name']}")
print(f"    Font style  : {FONT_STYLE['name']}")
print(f"    Arrow pair  : {ARROW_PAIR['name']}")
print(f"    Zoom        : {ZOOM_VARIANT['name']}")
print(f"    Countdown   : {COUNTDOWN_STYLE['name']} ({COUNTDOWN_SEC}s)")
print(f"    Hook        : {HOOK_TEXT}")
print(f"    Series      : {SERIES['label']}  ({SERIES['min']}-{SERIES['max']})")
print("─" * 60)


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


def pick_from_dir(folder, fallback_file, supported=(".mp3", ".wav", ".ogg", ".m4a")):
    if os.path.isdir(folder):
        files = [os.path.join(folder, f) for f in os.listdir(folder)
                 if f.lower().endswith(supported)]
        if files:
            return random.choice(files)
    if os.path.exists(fallback_file):
        return fallback_file
    return None


def pick_intro_audio():
    chosen = pick_from_dir(INTRO_AUDIO_DIR, "")
    if chosen:
        print(f"[intro] Selected intro: {os.path.basename(chosen)}")
    else:
        print("[intro] No intro audio found — skipping.")
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
#  DRAWING HELPERS
# ─────────────────────────────────────────────
SQUARE_SIZE = BOARD_SIZE // 8

def square_to_pixel(square):
    col = chess.square_file(square)
    row = 7 - chess.square_rank(square)
    cx  = col * SQUARE_SIZE + SQUARE_SIZE // 2
    cy  = row * SQUARE_SIZE + SQUARE_SIZE // 2
    return cx, cy


def draw_arrow(draw, from_sq, to_sq, color=(255, 170, 0, 220), shaft_w=18, head_size=36):
    x1, y1 = square_to_pixel(from_sq)
    x2, y2 = square_to_pixel(to_sq)

    angle = math.atan2(y2 - y1, x2 - x1)
    tip_x = x2 - head_size * 0.6 * math.cos(angle)
    tip_y = y2 - head_size * 0.6 * math.sin(angle)

    dx = math.sin(angle) * shaft_w / 2
    dy = math.cos(angle) * shaft_w / 2
    shaft = [
        (x1 + dx, y1 - dy), (x1 - dx, y1 + dy),
        (tip_x - dx, tip_y + dy), (tip_x + dx, tip_y - dy),
    ]
    draw.polygon(shaft, fill=color)

    perp_x = math.sin(angle) * head_size
    perp_y = math.cos(angle) * head_size
    head = [
        (x2, y2),
        (tip_x + perp_x, tip_y - perp_y),
        (tip_x - perp_x, tip_y + perp_y),
    ]
    draw.polygon(head, fill=color)


def load_fonts():
    scale = FONT_STYLE["scale"]
    try:
        return (
            ImageFont.truetype(FONT_PATH, int(60 * scale)),
            ImageFont.truetype(FONT_PATH, int(28 * scale)),
        )
    except Exception:
        fallback = ImageFont.load_default()
        return fallback, fallback


def draw_text(draw, xy, text, font, fill):
    stroke = FONT_STYLE.get("stroke", 0)
    if stroke:
        draw.text(xy, text, font=font, fill=fill, stroke_width=stroke, stroke_fill="black")
    else:
        draw.text(xy, text, font=font, fill=fill)


def create_frame_image(board, last_move=None, arrow_move=None, arrow_color=None,
                       timer=None, rating=None, side_to_move=None, badge=None):
    svg_data = chess.svg.board(
        board, size=BOARD_SIZE, lastmove=last_move, flipped=False,
        colors=BOARD_THEME["colors"]
    ).encode("UTF-8")

    tmp_png = os.path.join(TEMP_DIR, "_tmp_frame.png")
    cairosvg.svg2png(bytestring=svg_data, write_to=tmp_png)

    im   = Image.open(tmp_png).convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")

    if arrow_move is not None:
        color = arrow_color if arrow_color else ARROW_COLOR_SOLVER
        draw_arrow(draw, arrow_move.from_square, arrow_move.to_square, color=color)

    font_large, font_small = load_fonts()

    bar = Image.new("RGBA", (BOARD_SIZE, 78), (0, 0, 0, 165))
    im.paste(bar, (0, 0), bar)
    draw = ImageDraw.Draw(im, "RGBA")

    draw_text(draw, (16, 10), f"Rating: {rating}", font_small, "white")
    draw_text(draw, (16, 44), f"{side_to_move} to move", font_small, "#FFD700")

    if badge:
        label, emoji, color = badge
        badge_text = f"{emoji} {label}"
        bbbox = draw.textbbox((0, 0), badge_text, font=font_small)
        bw    = bbbox[2] - bbbox[0]
        draw_text(draw, (BOARD_SIZE - bw - 16, 10), badge_text, font_small, color)

    if timer is not None:
        txt  = str(timer)
        bbox = draw.textbbox((0, 0), txt, font=font_large)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        cx, cy = (BOARD_SIZE - w) // 2, (BOARD_SIZE - h) // 2
        draw.text((cx + 3, cy + 3), txt, font=font_large, fill=(0, 0, 0, 180))
        draw_text(draw, (cx, cy), txt, font_large, "white")

    im = ce.apply_zoom(im, ZOOM_VARIANT["factor"], BOARD_SIZE)
    return im.convert("RGB")


def create_hook_frame(hook_text):
    im   = Image.new("RGBA", (BOARD_SIZE, BOARD_SIZE), (10, 10, 15, 255))
    draw = ImageDraw.Draw(im)
    font_large, font_small = load_fonts()

    draw.rectangle([(0, 0), (BOARD_SIZE, 10)], fill=ARROW_COLOR_SOLVER[:3])
    draw.rectangle([(0, BOARD_SIZE - 10), (BOARD_SIZE, BOARD_SIZE)], fill=ARROW_COLOR_SOLVER[:3])

    words = hook_text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font_large) > BOARD_SIZE - 100:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)

    total_h = len(lines) * 80
    y = (BOARD_SIZE - total_h) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_large)
        w = bbox[2] - bbox[0]
        draw_text(draw, ((BOARD_SIZE - w) // 2, y), line, font_large, "white")
        y += 80

    return im.convert("RGB")


# ─────────────────────────────────────────────
#  FRAME GENERATION
# ─────────────────────────────────────────────
def save_frames(board, moves, rating, side_to_move, badge):
    frame_count = 0

    def save(img):
        nonlocal frame_count
        img.save(os.path.join(TEMP_DIR, f"frame_{frame_count:05d}.png"))
        frame_count += 1

    def save_n(img, n):
        for _ in range(n):
            save(img)

    # 0 ── Hook card ────────────────────────────────────────
    hook_im = create_hook_frame(HOOK_TEXT)
    save_n(hook_im, FPS * HOOK_SEC)

    working_board = board.copy()

    # 1 ── Intro hold ──────────────────────────────────────
    im = create_frame_image(working_board, rating=rating, side_to_move=side_to_move, badge=badge)
    save_n(im, FPS * INTRO_SEC)

    # 2 ── Move loop ───────────────────────────────────────
    for i, move_uci in enumerate(moves):
        move = chess.Move.from_uci(move_uci)
        is_solver_move = (i % 2 == 1)
        arrow_color = ARROW_COLOR_SOLVER if is_solver_move else ARROW_COLOR_OPPONENT

        im = create_frame_image(working_board, arrow_move=move, arrow_color=arrow_color,
                                rating=rating, side_to_move=side_to_move, badge=badge)
        save_n(im, FPS * ARROW_SEC)

        working_board.push(move)

        if i == 0:
            if COUNTDOWN_STYLE["style"] == "hold_then_flash":
                hold_frames = int(FPS * COUNTDOWN_SEC * 0.6)
                im = create_frame_image(working_board, last_move=move,
                                        rating=rating, side_to_move=side_to_move, badge=badge)
                save_n(im, hold_frames)
                for sec in range(5, 0, -1):
                    im = create_frame_image(working_board, last_move=move, timer=sec,
                                            rating=rating, side_to_move=side_to_move, badge=badge)
                    save_n(im, FPS)
            else:
                for sec in range(COUNTDOWN_SEC, 0, -1):
                    im = create_frame_image(working_board, last_move=move, timer=sec,
                                            rating=rating, side_to_move=side_to_move, badge=badge)
                    save_n(im, FPS)
        else:
            im = create_frame_image(working_board, last_move=move,
                                    rating=rating, side_to_move=side_to_move, badge=badge)
            save_n(im, FPS * MOVE_SEC)

    # 3 ── Final pause ─────────────────────────────────────
    im = create_frame_image(working_board, rating=rating, side_to_move=side_to_move, badge=badge)
    save_n(im, FPS * FINAL_SEC)

    print(f"[frames] Total frames saved: {frame_count}")


# ─────────────────────────────────────────────
#  VIDEO ENCODING
# ─────────────────────────────────────────────
def encode_video(intro_file=None, music_file=None, click_file=None):
    video_part = f"-framerate {FPS} -i {TEMP_DIR}/frame_%05d.png"

    has_intro = intro_file is not None and os.path.exists(intro_file)
    has_music = INCLUDE_BG_MUSIC and music_file is not None and os.path.exists(music_file)
    has_click = click_file is not None and os.path.exists(click_file)

    inputs      = []
    filter_parts = []
    mix_labels  = []
    idx         = 1

    if has_intro:
        inputs.append(f"-i {intro_file}")
        filter_parts.append(f"[{idx}:a]volume=1.0[intro]")
        mix_labels.append("[intro]")
        idx += 1

    if has_music:
        inputs.append(f"-stream_loop -1 -i {music_file}")
        filter_parts.append(f"[{idx}:a]volume={BG_MUSIC_VOLUME}[bg]")
        mix_labels.append("[bg]")
        idx += 1

    if has_click:
        inputs.append(f"-i {click_file}")
        filter_parts.append(f"[{idx}:a]volume={CLICK_VOLUME}[clk]")
        mix_labels.append("[clk]")
        idx += 1

    inputs_str = " ".join(inputs)
    n_audio    = len(mix_labels)

    if n_audio == 0:
        cmd = (
            f"{FFMPEG_BIN} -y {video_part} "
            f"-c:v libx264 -pix_fmt yuv420p {OUTPUT_VIDEO}"
        )
    elif n_audio == 1:
        single_label = mix_labels[0].strip("[]")
        cmd = (
            f"{FFMPEG_BIN} -y {video_part} {inputs_str} "
            f'-filter_complex "{filter_parts[0]}" '
            f"-map 0:v -map [{single_label}] "
            f"-c:v libx264 -pix_fmt yuv420p -shortest {OUTPUT_VIDEO}"
        )
    else:
        mix_str = "".join(mix_labels)
        filter_parts.append(
            f"{mix_str}amix=inputs={n_audio}:duration=longest:normalize=0[aout]"
        )
        fc = ";".join(filter_parts)
        cmd = (
            f"{FFMPEG_BIN} -y {video_part} {inputs_str} "
            f'-filter_complex "{fc}" '
            f"-map 0:v -map [aout] "
            f"-c:v libx264 -pix_fmt yuv420p -shortest {OUTPUT_VIDEO}"
        )

    print("[ffmpeg]", cmd[:220], "...")
    subprocess.run(cmd, shell=True, check=True)


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_VIDEO), exist_ok=True)

print("Fetching puzzle...")
data = requests.get(API_URL).json()
print("Puzzle data:", data)

board  = chess.Board(data['fen'])
moves  = data['moves']
rating = data['rating']
badge  = ce.get_difficulty_badge(rating)

solver_color = not board.turn
side_to_move = "White" if solver_color == chess.WHITE else "Black"

intro_file = pick_intro_audio()
music_file = pick_from_dir(BACKGROUND_MUSIC_DIR, BACKGROUND_MUSIC)
click_file = pick_from_dir(CLICK_SOUND_DIR, CLICK_SOUND)

print("Generating frames...")
save_frames(board, moves, rating, side_to_move, badge)

print("Encoding video...")
encode_video(intro_file=intro_file, music_file=music_file, click_file=click_file)

# ── Social copy (no random countries/cities — see content_engine.py) ──
base_msg = random.choice(MESSAGES).format(rating=rating, side=side_to_move)
safe_message = ce.build_caption(
    base_msg, series_label=SERIES["label"], cta=CTA_TEXT,
    hashtags=HASHTAGS, max_tags=4
)

puzzle_link = ""
video_url = f"https://roynek.com/Chess_Sol_Puzzles/auto_post/{OUTPUT_VIDEO}"

# # Randomized delay so uploads don't all land at the exact same minute
# ce.random_pre_post_delay(min_sec=30, max_sec=600)

# output = send_to_social_media_api(
#     platform='facebook',
#     link=puzzle_link,
#     text=safe_message,
#     media=video_url,
#     area='6',
#     fb_post_to="reels"
# )
# print("Facebook: Social API Response:", output)

# # ── A/B test logging ──────────────────────────────────────
# ce.log_analytics({
#     "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
#     "video_type": "reels",
#     "board_theme": BOARD_THEME["name"],
#     "font_style": FONT_STYLE["name"],
#     "arrow_pair": ARROW_PAIR["name"],
#     "zoom": ZOOM_VARIANT["name"],
#     "countdown_style": COUNTDOWN_STYLE["name"],
#     "countdown_sec": COUNTDOWN_SEC,
#     "hook": HOOK_TEXT,
#     "message": base_msg,
#     "cta": CTA_TEXT,
#     "series_label": SERIES["label"],
#     "puzzle_ids": str(data.get("id", "")),
#     "ratings": str(rating),
#     "difficulty_labels": badge[0],
#     "hashtags": safe_message,
#     "output_video": OUTPUT_VIDEO,
#     "api_response": (output or "")[:200],
# })

# # ── Cleanup ────────────────────────────────────────────────
# for f in os.listdir(TEMP_DIR):
#     os.remove(os.path.join(TEMP_DIR, f))
# os.rmdir(TEMP_DIR)

# print(f"\n✅  Done — video saved to: {OUTPUT_VIDEO}")
