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

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
API_URL       = "https://roynek.com/Chess_Sol_Puzzles/api/puzzle/random-by-rating?min=1600"
FPS           = 30
COUNTDOWN_SEC = 15          # seconds for the thinking countdown
INTRO_SEC     = 3           # hold initial position before first move
ARROW_SEC     = 2           # show arrow before each move plays
MOVE_SEC      = 2           # hold board after each move plays
FINAL_SEC     = 3           # pause at end

TEMP_DIR      = "frames"
OUTPUT_VIDEO  = "output_video/chess_short.mp4"
FONT_PATH     = "./Roboto-Regular.ttf"
BOARD_SIZE    = 800

# ── Audio ─────────────────────────────────────
# Use royalty-free / CC0 licensed audio files only.
# Good free sources:
#   Music  → https://pixabay.com/music/  (free for commercial use)
#             https://freemusicarchive.org (check licence per track)
#   Clicks → https://freesound.org        (filter by CC0)
BACKGROUND_MUSIC = "bg_music.mp3"   # soft ambient / lo-fi track
CLICK_SOUND      = "move.mp3"       # short piece-move click
BG_MUSIC_VOLUME  = 0.12             # very subtle — won't compete with anything (0.0–1.0)
CLICK_VOLUME     = 0.65             # audible but not harsh
INCLUDE_BG_MUSIC = True             # set False for a fully silent video

# ── Social copy ───────────────────────────────
MESSAGES = [
    "Can you find the winning move? 🧩 ({side} to move)",
    "Today's daily challenge — {side} to move!",
    "Test your tactics ({rating}) — {side} to move!",
    "What is the best move here? ({side} to play)",
    "Spot the winning sequence! 🔥 ({side})"
]
HASHTAGS = ["#Chess", "#ChessPuzzles", "#Tactics", "#BrainTeaser"]


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

def square_to_pixel(square, flip=False):
    """Return (cx, cy) pixel centre of a chess square."""
    col = chess.square_file(square)
    row = chess.square_rank(square)
    if flip:
        col = 7 - col
        row = 7 - row
    else:
        row = 7 - row
    cx = col * SQUARE_SIZE + SQUARE_SIZE // 2
    cy = row * SQUARE_SIZE + SQUARE_SIZE // 2
    return cx, cy


def draw_arrow(draw, from_sq, to_sq, flip=False,
               color=(255, 170, 0, 220), shaft_w=18, head_size=36):
    """Draw a bold golden arrow from_sq → to_sq on a PIL ImageDraw (RGBA mode)."""
    x1, y1 = square_to_pixel(from_sq, flip)
    x2, y2 = square_to_pixel(to_sq,   flip)

    angle = math.atan2(y2 - y1, x2 - x1)

    # Shorten tip so the arrowhead sits neatly inside the target square
    tip_x = x2 - head_size * 0.6 * math.cos(angle)
    tip_y = y2 - head_size * 0.6 * math.sin(angle)

    # Shaft (parallelogram)
    dx = math.sin(angle) * shaft_w / 2
    dy = math.cos(angle) * shaft_w / 2
    shaft = [
        (x1 + dx, y1 - dy),
        (x1 - dx, y1 + dy),
        (tip_x - dx, tip_y + dy),
        (tip_x + dx, tip_y - dy),
    ]
    draw.polygon(shaft, fill=color)

    # Arrowhead (triangle)
    perp_x = math.sin(angle) * head_size
    perp_y = math.cos(angle) * head_size
    head = [
        (x2,             y2),
        (tip_x + perp_x, tip_y - perp_y),
        (tip_x - perp_x, tip_y + perp_y),
    ]
    draw.polygon(head, fill=color)


def create_frame_image(board, last_move=None, arrow_move=None,
                       timer=None, rating=None, side_to_move=None, flip=False):
    """
    Render one video frame as a PIL RGB Image.

    arrow_move : chess.Move  – golden arrow shown BEFORE the move executes
    timer      : int         – countdown number shown in the centre of the board
    """
    svg_data = chess.svg.board(
        board,
        size=BOARD_SIZE,
        lastmove=last_move,
        flipped=flip
    ).encode("UTF-8")

    tmp_png = os.path.join(TEMP_DIR, "_tmp_frame.png")
    cairosvg.svg2png(bytestring=svg_data, write_to=tmp_png)

    im   = Image.open(tmp_png).convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")

    # ── Arrow overlay ──────────────────────────────────────
    if arrow_move is not None:
        draw_arrow(draw, arrow_move.from_square, arrow_move.to_square, flip=flip)

    # ── Fonts ──────────────────────────────────────────────
    try:
        font_large = ImageFont.truetype(FONT_PATH, 60)
        font_small = ImageFont.truetype(FONT_PATH, 28)
    except Exception:
        font_large = font_small = ImageFont.load_default()

    # ── Semi-transparent top info bar ─────────────────────
    bar = Image.new("RGBA", (BOARD_SIZE, 78), (0, 0, 0, 165))
    im.paste(bar, (0, 0), bar)
    draw = ImageDraw.Draw(im, "RGBA")   # refresh draw handle after paste

    draw.text((16, 10), f"Rating: {rating}",       font=font_small, fill="white")
    draw.text((16, 44), f"{side_to_move} to move", font=font_small, fill="#FFD700")

    # ── Countdown ──────────────────────────────────────────
    if timer is not None:
        txt  = str(timer)
        bbox = draw.textbbox((0, 0), txt, font=font_large)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        cx   = (BOARD_SIZE - w) // 2
        cy   = (BOARD_SIZE - h) // 2
        draw.text((cx + 3, cy + 3), txt, font=font_large, fill=(0, 0, 0, 180))  # shadow
        draw.text((cx, cy),          txt, font=font_large, fill="white")

    return im.convert("RGB")


# ─────────────────────────────────────────────
#  FRAME GENERATION
# ─────────────────────────────────────────────
def save_frames(board, moves, rating, side_to_move, flip=False):
    frame_count = 0

    def save(img):
        nonlocal frame_count
        img.save(os.path.join(TEMP_DIR, f"frame_{frame_count:05d}.png"))
        frame_count += 1

    def save_n(img, n):
        for _ in range(n):
            save(img)

    # 1 ── Intro hold (clean board, no arrow, no timer) ────
    im = create_frame_image(board, rating=rating, side_to_move=side_to_move, flip=flip)
    save_n(im, FPS * INTRO_SEC)

    # 2 ── Move loop ───────────────────────────────────────
    for i, move_uci in enumerate(moves):
        move = chess.Move.from_uci(move_uci)

        # Arrow preview BEFORE the move executes
        im = create_frame_image(board, arrow_move=move, rating=rating,
                                side_to_move=side_to_move, flip=flip)
        save_n(im, FPS * ARROW_SEC)

        board.push(move)

        if i == 0:
            # After the puzzle's first move → show the full countdown
            for sec in range(COUNTDOWN_SEC, 0, -1):
                im = create_frame_image(board, last_move=move, timer=sec,
                                        rating=rating, side_to_move=side_to_move, flip=flip)
                save_n(im, FPS)
        else:
            # Solution moves → brief hold so viewer can follow
            im = create_frame_image(board, last_move=move, rating=rating,
                                    side_to_move=side_to_move, flip=flip)
            save_n(im, FPS * MOVE_SEC)

    # 3 ── Final pause ─────────────────────────────────────
    im = create_frame_image(board, rating=rating, side_to_move=side_to_move, flip=flip)
    save_n(im, FPS * FINAL_SEC)

    print(f"[frames] Total frames saved: {frame_count}")


# ─────────────────────────────────────────────
#  VIDEO ENCODING
# ─────────────────────────────────────────────
def encode_video():
    """Combine frames + optional background music + click sound into final MP4."""
    video_part = f"-framerate {FPS} -i {TEMP_DIR}/frame_%05d.png"

    has_music = INCLUDE_BG_MUSIC and os.path.exists(BACKGROUND_MUSIC)
    has_click = os.path.exists(CLICK_SOUND)

    if not has_music and not has_click:
        # Silent video
        cmd = (
            f"{FFMPEG_BIN} -y {video_part} "
            f"-c:v libx264 -pix_fmt yuv420p {OUTPUT_VIDEO}"
        )

    elif has_music and has_click:
        cmd = (
            f"{FFMPEG_BIN} -y {video_part} "
            f"-i {BACKGROUND_MUSIC} -i {CLICK_SOUND} "
            f'-filter_complex "'
            f"[1:a]volume={BG_MUSIC_VOLUME}[bg];"
            f"[2:a]volume={CLICK_VOLUME}[clk];"
            f"[bg][clk]amix=inputs=2:duration=longest[aout]"
            f'" '
            f"-map 0:v -map [aout] -c:v libx264 -pix_fmt yuv420p -shortest {OUTPUT_VIDEO}"
        )

    elif has_music:
        cmd = (
            f"{FFMPEG_BIN} -y {video_part} "
            f"-i {BACKGROUND_MUSIC} "
            f'-filter_complex "[1:a]volume={BG_MUSIC_VOLUME}[aout]" '
            f"-map 0:v -map [aout] -c:v libx264 -pix_fmt yuv420p -shortest {OUTPUT_VIDEO}"
        )

    else:
        # Click sound only
        cmd = (
            f"{FFMPEG_BIN} -y {video_part} "
            f"-i {CLICK_SOUND} "
            f'-filter_complex "[1:a]volume={CLICK_VOLUME}[aout]" '
            f"-map 0:v -map [aout] -c:v libx264 -pix_fmt yuv420p -shortest {OUTPUT_VIDEO}"
        )

    print("[ffmpeg]", cmd[:200], "...")
    subprocess.run(cmd, shell=True, check=True)


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_VIDEO), exist_ok=True)

print("Fetching puzzle...")
data   = requests.get(API_URL).json()
print("Puzzle data:", data)

board  = chess.Board(data['fen'])
moves  = data['moves']
rating = data['rating']

solver_color = not board.turn
side_to_move = "White" if solver_color == chess.WHITE else "Black"
flip         = (solver_color == chess.BLACK)   # solver's pieces always at the bottom

print("Generating frames...")
save_frames(board, moves, rating, side_to_move, flip=flip)

print("Encoding video...")
encode_video()

# ── Social copy ────────────────────────────────────────────
msg = random.choice(MESSAGES).format(rating=rating, side=side_to_move)
print(f"\n📢  Social copy ready: {msg}")

# Uncomment below to post automatically:
# puzzle_link = f"https://roynek.com/Chess_Sol_Puzzles/public/?puzzle={data['id']}"
# video_url   = f"https://roynek.com/Chess_Sol_Puzzles/auto_post/{OUTPUT_VIDEO}"
# send_to_social_media_api('facebook', puzzle_link, msg, video_url, area='6', fb_post_to='reels')

# ── Cleanup ────────────────────────────────────────────────
for f in os.listdir(TEMP_DIR):
    os.remove(os.path.join(TEMP_DIR, f))
os.rmdir(TEMP_DIR)

print(f"\n✅  Done — video saved to: {OUTPUT_VIDEO}")