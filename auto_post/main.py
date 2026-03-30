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
COUNTDOWN_SEC = 15          # thinking countdown after first move
INTRO_SEC     = 3           # hold initial board before any move
ARROW_SEC     = 2           # show arrow before each move executes
MOVE_SEC      = 2           # hold board after each move
FINAL_SEC     = 3           # pause at the very end

TEMP_DIR      = "frames"
OUTPUT_VIDEO  = "output_video/chess_short.mp4"
FONT_PATH     = "./Roboto-Regular.ttf"
BOARD_SIZE    = 800

# ── Intro Audio ───────────────────────────────────────────
# Folder containing YOUR recorded intro files (.mp3 or .wav).
# The script picks one at random each run.
# Supported formats: .mp3  .wav  .ogg  .m4a
ls = ["./intro_sounds", "/intro_fake"] # intro_fake does not exist. I am using it to skip intro audios..
INTRO_AUDIO_DIR = random.choice(ls)    # ← point this at your folder

# ── Background & Click Audio ──────────────────────────────
# BACKGROUND_MUSIC = "bg_music.mp3"
BACKGROUND_MUSIC = "bg_music_free.wav"
CLICK_SOUND      = "move.mp3"
BG_MUSIC_VOLUME  = 0.15   # very subtle (0.0 – 1.0)
CLICK_VOLUME     = 0.65
INCLUDE_BG_MUSIC = True   # set False for no background music

# ── Arrow Colors ──────────────────────────────────────────
# SOLVER  = the side the viewer is challenged to play for  → bright/positive
# OPPONENT = the side that replies                          → warning/muted
#
# Format: (R, G, B, Alpha)  — Alpha 0=transparent 255=solid
#
ARROW_COLOR_SOLVER   = (255, 215,   0, 230)   # gold          #FFD700
ARROW_COLOR_OPPONENT = (255,  87,  34, 210)   # deep orange   #FF5722
#
# Swap suggestions:
#   Gold solver    → (255, 215,   0, 230)
#   Red opponent   → (229,  57,  53, 210)
#   Blue solver    → (  0, 176, 255, 230)

# ── Social copy ───────────────────────────────────────────
MESSAGES = [
    "Can you find the winning move? 🧩 ({side} to move)",
    "Today's daily challenge — {side} to move!",
    "Test your tactics ({rating}) — {side} to move!",
    "What is the best move here? ({side} to play)",
    "Spot the winning sequence! 🔥 ({side})"
]
# HASHTAGS = ["#Chess", "#ChessPuzzles", "#Tactics", "#BrainTeaser", "checkmate", "#chess"]
HASHTAGS = ["#ChessTactics", "#ChessStrategy", "#Checkmate", "#Grandmaster", "#Chess", "#ChessReels", "#BoardGames", "#ChessPunks", "#ChessSol", "#Checkmate", "#LearnChess", "#ChessMasterclass", "#ChessTips", "#PuzzleSolving", "#MentalGym", "#StrategicThinking", "#SpeedChess"]

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
    """
    Return a path to one of your recorded intro files, chosen at random.
    Returns None if the folder is missing or empty.
    """
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
        print(f"[intro] No audio files found in '{INTRO_AUDIO_DIR}' — skipping intro audio.")
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
#  DRAWING HELPERS
# ─────────────────────────────────────────────
SQUARE_SIZE = BOARD_SIZE // 8

def square_to_pixel(square):
    """
    Return (cx, cy) pixel centre of a chess square — STANDARD view always.
    White at bottom: rank 1 (index 0) is at the bottom of the image.
      file 0 (a) → left,  file 7 (h) → right
      rank 0     → bottom (row 7 in screen coords), rank 7 → top (row 0)
    """
    col = chess.square_file(square)      # 0=a … 7=h
    row = 7 - chess.square_rank(square)  # rank8 → screen row 0, rank1 → screen row 7
    cx  = col * SQUARE_SIZE + SQUARE_SIZE // 2
    cy  = row * SQUARE_SIZE + SQUARE_SIZE // 2
    return cx, cy


def draw_arrow(draw, from_sq, to_sq,
               color=(255, 170, 0, 220), shaft_w=18, head_size=36):
    """
    Draw a bold directional arrow from_sq → to_sq on an RGBA ImageDraw.
    Always uses standard board orientation (White at bottom).
    Works correctly for both White and Black pieces at any board position.
    """
    x1, y1 = square_to_pixel(from_sq)
    x2, y2 = square_to_pixel(to_sq)

    angle = math.atan2(y2 - y1, x2 - x1)
    tip_x = x2 - head_size * 0.6 * math.cos(angle)
    tip_y = y2 - head_size * 0.6 * math.sin(angle)

    # Shaft
    dx = math.sin(angle) * shaft_w / 2
    dy = math.cos(angle) * shaft_w / 2
    shaft = [
        (x1 + dx, y1 - dy),
        (x1 - dx, y1 + dy),
        (tip_x - dx, tip_y + dy),
        (tip_x + dx, tip_y - dy),
    ]
    draw.polygon(shaft, fill=color)

    # Arrowhead
    perp_x = math.sin(angle) * head_size
    perp_y = math.cos(angle) * head_size
    head = [
        (x2,             y2),
        (tip_x + perp_x, tip_y - perp_y),
        (tip_x - perp_x, tip_y + perp_y),
    ]
    draw.polygon(head, fill=color)


def create_frame_image(board, last_move=None, arrow_move=None, arrow_color=None,
                       timer=None, rating=None, side_to_move=None):
    """
    Render one video frame as a PIL RGB Image.

    arrow_move  : chess.Move  – golden/orange arrow shown BEFORE the move executes
    arrow_color : RGBA tuple  – color for this specific arrow
    timer       : int         – countdown number shown in the board centre
    Board is always rendered in standard orientation (White at bottom).
    """
    svg_data = chess.svg.board(
        board,
        size=BOARD_SIZE,
        lastmove=last_move,
        flipped=False          # always standard view
    ).encode("UTF-8")

    tmp_png = os.path.join(TEMP_DIR, "_tmp_frame.png")
    cairosvg.svg2png(bytestring=svg_data, write_to=tmp_png)

    im   = Image.open(tmp_png).convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")

    # ── Arrow overlay ──────────────────────────────────────
    if arrow_move is not None:
        color = arrow_color if arrow_color else ARROW_COLOR_SOLVER
        draw_arrow(draw, arrow_move.from_square, arrow_move.to_square, color=color)

    # ── Fonts ──────────────────────────────────────────────
    try:
        font_large = ImageFont.truetype(FONT_PATH, 60)
        font_small = ImageFont.truetype(FONT_PATH, 28)
    except Exception:
        font_large = font_small = ImageFont.load_default()

    # ── Top info bar ───────────────────────────────────────
    bar = Image.new("RGBA", (BOARD_SIZE, 78), (0, 0, 0, 165))
    im.paste(bar, (0, 0), bar)
    draw = ImageDraw.Draw(im, "RGBA")

    draw.text((16, 10), f"Rating: {rating}",       font=font_small, fill="white")
    draw.text((16, 44), f"{side_to_move} to move", font=font_small, fill="#FFD700")

    # ── Countdown ──────────────────────────────────────────
    if timer is not None:
        txt  = str(timer)
        bbox = draw.textbbox((0, 0), txt, font=font_large)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        cx, cy = (BOARD_SIZE - w) // 2, (BOARD_SIZE - h) // 2
        draw.text((cx + 3, cy + 3), txt, font=font_large, fill=(0, 0, 0, 180))
        draw.text((cx, cy),          txt, font=font_large, fill="white")

    return im.convert("RGB")


# ─────────────────────────────────────────────
#  FRAME GENERATION
# ─────────────────────────────────────────────
def save_frames(board, moves, rating, side_to_move):
    """
    Generate all frames.

    Arrow color logic (based on move list structure):
      Index 0       → opponent's move (sets the scene)  → ORANGE
      Index 1, 3, 5 → solver's moves                    → GOLD
      Index 2, 4, 6 → opponent's replies                → ORANGE

    Board is always standard view — no flipping needed.
    """
    frame_count = 0

    def save(img):
        nonlocal frame_count
        img.save(os.path.join(TEMP_DIR, f"frame_{frame_count:05d}.png"))
        frame_count += 1

    def save_n(img, n):
        for _ in range(n):
            save(img)

    working_board = board.copy()

    # 1 ── Intro hold ──────────────────────────────────────
    im = create_frame_image(working_board, rating=rating, side_to_move=side_to_move)
    save_n(im, FPS * INTRO_SEC)

    # 2 ── Move loop ───────────────────────────────────────
    for i, move_uci in enumerate(moves):
        move = chess.Move.from_uci(move_uci)

        # Even index (0, 2, 4…) = opponent | Odd index (1, 3, 5…) = solver
        is_solver_move = (i % 2 == 1)
        arrow_color    = ARROW_COLOR_SOLVER if is_solver_move else ARROW_COLOR_OPPONENT

        # Arrow preview BEFORE the move executes
        im = create_frame_image(working_board, arrow_move=move,
                                arrow_color=arrow_color,
                                rating=rating, side_to_move=side_to_move)
        save_n(im, FPS * ARROW_SEC)

        working_board.push(move)

        if i == 0:
            # After opponent's first move → full countdown for the viewer to think
            for sec in range(COUNTDOWN_SEC, 0, -1):
                im = create_frame_image(working_board, last_move=move, timer=sec,
                                        rating=rating, side_to_move=side_to_move)
                save_n(im, FPS)
        else:
            # Solution moves → brief hold so viewer can follow
            im = create_frame_image(working_board, last_move=move,
                                    rating=rating, side_to_move=side_to_move)
            save_n(im, FPS * MOVE_SEC)

    # 3 ── Final pause ─────────────────────────────────────
    im = create_frame_image(working_board, rating=rating, side_to_move=side_to_move)
    save_n(im, FPS * FINAL_SEC)

    print(f"[frames] Total frames saved: {frame_count}")


# ─────────────────────────────────────────────
#  VIDEO ENCODING
# ─────────────────────────────────────────────
def encode_video(intro_file=None):
    """
    Build the final MP4 by combining:
      - frames (always)
      - your personal intro audio (if found)
      - background music (if enabled)
      - click sound (if file exists)

    The intro audio plays from the very start at full volume.
    Background music runs underneath throughout at BG_MUSIC_VOLUME.
    """
    video_part = f"-framerate {FPS} -i {TEMP_DIR}/frame_%05d.png"

    has_intro = intro_file is not None and os.path.exists(intro_file)
    has_music = INCLUDE_BG_MUSIC and os.path.exists(BACKGROUND_MUSIC)
    has_click = os.path.exists(CLICK_SOUND)

    # Build input list and filter graph dynamically
    inputs      = []
    filter_parts = []
    mix_labels  = []
    idx         = 1   # video is [0], audio inputs start at [1]

    if has_intro:
        inputs.append(f"-i {intro_file}")
        filter_parts.append(f"[{idx}:a]volume=1.0[intro]")
        mix_labels.append("[intro]")
        idx += 1

    if has_music:
        inputs.append(f"-i {BACKGROUND_MUSIC}")
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
        # No audio at all — silent video
        cmd = (
            f"{FFMPEG_BIN} -y {video_part} "
            f"-c:v libx264 -pix_fmt yuv420p {OUTPUT_VIDEO}"
        )
    elif n_audio == 1:
        # Single audio stream — no amix needed
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
data   = requests.get(API_URL).json()
print("Puzzle data:", data)

board  = chess.Board(data['fen'])
moves  = data['moves']
rating = data['rating']

# solver_color = the side the viewer is challenged to play
solver_color = not board.turn                                    # opponent of FEN side
side_to_move = "White" if solver_color == chess.WHITE else "Black"
# No board flipping — always standard view (White at bottom)

# Pick one of your recorded intros at random
intro_file = pick_intro_audio()

print("Generating frames...")
save_frames(board, moves, rating, side_to_move)

print("Encoding video...")
encode_video(intro_file=intro_file)

# ── Social copy ────────────────────────────────────────────
msg = random.choice(MESSAGES).format(rating=rating, side=side_to_move)
print(f"\n📢  Social copy ready: {msg}")

# Uncomment to auto-post:
# puzzle_link = f"https://roynek.com/Chess_Sol_Puzzles/public/?puzzle={data['id']}"
# video_url   = f"https://roynek.com/Chess_Sol_Puzzles/auto_post/{OUTPUT_VIDEO}"
# send_to_social_media_api('facebook', puzzle_link, msg, video_url, area='6', fb_post_to='reels')



tags = " ".join(random.sample(HASHTAGS, 3))
# full_message = f"{msg}\n\n{tags}\n\n@followers"
full_message = f" {msg} {tags} . "
safe_message = full_message.replace("\n", " ").strip()
safe_message = full_message.encode("ascii", "ignore").decode()

# puzzle_link = f"https://roynek.com/Chess_Sol_Puzzles/public/?puzzle={data['id']}"
puzzle_link = ""
video_url = f"https://roynek.com/Chess_Sol_Puzzles/auto_post/{OUTPUT_VIDEO}"

output = send_to_social_media_api(
    platform='facebook',
    link=puzzle_link,
    text=safe_message,
    media=video_url,
    area='6',
    fb_post_to="reels"
)

print("Facebook: Social API Response:", output)

# # 6=chessSol
# # 3=Nataya
# # 7=Roynek Technologies



# chess_comm = "1578034816620310528"

output_x = send_to_social_media_api(
    platform='x',
    link=puzzle_link,
    text=safe_message,
    media=video_url,
    area='21',
    # x_comm_id=chess_comm,
    # fb_post_to="reels"
)
print("X: Social API Response:", output_x)





# ── Cleanup ────────────────────────────────────────────────
for f in os.listdir(TEMP_DIR):
    os.remove(os.path.join(TEMP_DIR, f))
os.rmdir(TEMP_DIR)

print(f"\n✅  Done — video saved to: {OUTPUT_VIDEO}")