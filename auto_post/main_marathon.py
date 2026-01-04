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

# ==================================================
# CONFIGURATION (UNCHANGED CORE)
# ==================================================

FPS = 30
COUNTDOWN_SEC = 10
MOVE_SEC = 1
BOARD_SIZE = 800

INITIAL_SEC = 1
FINAL_SEC = 2
BREAK_SEC = 4

TOTAL_PUZZLES = 10
PUZZLE_FETCH_LIMIT = 100

TEMP_DIR = "frames"
OUTPUT_VIDEO = "output_video/chess_1_hour_marathon.mp4"

FONT_PATH = "./Roboto-Regular.ttf"

BACKGROUND_MUSIC = "bg_music.mp3"
CLICK_SOUND = "move.mp3"

MIN_RATING = 1500
MAX_RATING = 3000

NARRATIVES = [
    "endgame",
    "mate",
    "mate in 2",
    "crushing",
    "sacrifice",
    "knight",
    "queen"
]

# ==================================================
# FFMPEG DETECTION (UNCHANGED)
# ==================================================

def detect_ffmpeg():
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin
    local_bin = "./ffmpeg-7.0.2-amd64-static/ffmpeg"
    if os.path.exists(local_bin):
        os.chmod(local_bin, 0o755)
        return local_bin
    raise FileNotFoundError("FFmpeg not found")

FFMPEG_BIN = detect_ffmpeg()
print("Using FFmpeg:", FFMPEG_BIN)

# ==================================================
# PUZZLE FETCHING (NEW, BUT SAFE)
# ==================================================

def fetch_puzzles():
    narrative = random.choice(NARRATIVES)
    url = (
        "https://roynek.com/Chess_Sol_Puzzles/api/puzzles"
        f"?q={narrative}&min={MIN_RATING}&max={MAX_RATING}&limit={PUZZLE_FETCH_LIMIT}"
    )
    print("Fetching puzzles:", url)
    data = requests.get(url, timeout=30).json()
    return random.sample(data["results"], TOTAL_PUZZLES)

# ==================================================
# FRAME CREATION (100% YOUR ORIGINAL LOGIC)
# ==================================================

def create_frame_image(board, last_move=None, timer=None, rating=None, side_to_move=None):
    svg_data = chess.svg.board(
        board,
        size=BOARD_SIZE,
        lastmove=last_move
    ).encode("UTF-8")

    tmp_png = os.path.join(TEMP_DIR, "tmp.png")
    cairosvg.svg2png(bytestring=svg_data, write_to=tmp_png)

    im = Image.open(tmp_png).convert("RGBA")
    draw = ImageDraw.Draw(im)

    font_large = ImageFont.truetype(FONT_PATH, 60)
    font_medium = ImageFont.truetype(FONT_PATH, 36)

    draw.text((20, 20), f"Rating: {rating}", font=font_medium, fill="white")

    if side_to_move:
        draw.text((20, 60), f"{side_to_move} to move", font=font_medium, fill="white")

    if timer is not None:
        bbox = draw.textbbox((0, 0), str(timer), font=font_large)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text(
            ((BOARD_SIZE - w) // 2, (BOARD_SIZE - h) // 2),
            str(timer),
            font=font_large,
            fill="white"
        )

    return im

# ==================================================
# PUZZLE → FRAMES (YOUR LOGIC, UNCHANGED)
# ==================================================

def render_single_puzzle(board, moves, rating, side_to_move, frame_count):
    # Initial position
    for _ in range(FPS * INITIAL_SEC):
        im = create_frame_image(board, rating=rating, side_to_move=side_to_move)
        im.save(f"{TEMP_DIR}/frame_{frame_count:06d}.png")
        frame_count += 1

    # First move (opponent move)
    first_move = chess.Move.from_uci(moves[0])
    board.push(first_move)

    for _ in range(FPS * MOVE_SEC):
        im = create_frame_image(
            board,
            last_move=first_move,
            rating=rating,
            side_to_move=side_to_move
        )
        im.save(f"{TEMP_DIR}/frame_{frame_count:06d}.png")
        frame_count += 1

    # Countdown
    for sec in range(COUNTDOWN_SEC, 0, -1):
        im = create_frame_image(
            board,
            timer=sec,
            rating=rating,
            side_to_move=side_to_move
        )
        for _ in range(FPS):
            im.save(f"{TEMP_DIR}/frame_{frame_count:06d}.png")
            frame_count += 1

    # Remaining solution
    for move_uci in moves[1:]:
        move = chess.Move.from_uci(move_uci)
        board.push(move)

        for _ in range(FPS * MOVE_SEC):
            im = create_frame_image(
                board,
                last_move=move,
                rating=rating,
                side_to_move=side_to_move
            )
            im.save(f"{TEMP_DIR}/frame_{frame_count:06d}.png")
            frame_count += 1

    # Final pause
    for _ in range(FPS * FINAL_SEC):
        im = create_frame_image(board, rating=rating, side_to_move=side_to_move)
        im.save(f"{TEMP_DIR}/frame_{frame_count:06d}.png")
        frame_count += 1

    return frame_count

# ==================================================
# MAIN EXECUTION (NEW LOOP, OLD LOGIC)
# ==================================================

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs("output_video", exist_ok=True)

puzzles = fetch_puzzles()

frame_count = 0

for idx, puzzle in enumerate(puzzles, start=1):
    print(f"♟ Puzzle {idx}/{TOTAL_PUZZLES} | Rating {puzzle['rating']}")

    board = chess.Board(puzzle["fen"])

    # NOTE: this matches your original logic
    solver_color = not board.turn
    side_to_move = "White" if solver_color == chess.WHITE else "Black"

    # IMPORTANT:
    # If your multi-puzzle endpoint does not return moves yet,
    # this assumes your backend adds them (same as random-by-rating)
    moves = puzzle["moves"]

    frame_count = render_single_puzzle(
        board,
        moves,
        puzzle["rating"],
        side_to_move,
        frame_count
    )

    # Break between puzzles
    for _ in range(FPS * BREAK_SEC):
        im = create_frame_image(board, rating=puzzle["rating"], side_to_move=side_to_move)
        im.save(f"{TEMP_DIR}/frame_{frame_count:06d}.png")
        frame_count += 1

# ==================================================
# ENCODE FINAL VIDEO
# ==================================================

print("🎥 Encoding 1-hour video...")

cmd = f"""
{FFMPEG_BIN} -y -framerate {FPS} -i {TEMP_DIR}/frame_%06d.png \
-i {BACKGROUND_MUSIC} -i {CLICK_SOUND} \
-filter_complex "[1:a]volume=0.3[a1];[2:a]volume=0.7[a2];[a1][a2]amix=inputs=2:duration=longest[aout]" \
-map 0:v -map "[aout]" -c:v libx264 -pix_fmt yuv420p -shortest {OUTPUT_VIDEO}
"""

subprocess.run(cmd, shell=True, check=True)

# ==================================================
# CLEANUP
# ==================================================

for f in os.listdir(TEMP_DIR):
    os.remove(os.path.join(TEMP_DIR, f))
os.rmdir(TEMP_DIR)

print("✅ DONE")
print("🎬 Video:", OUTPUT_VIDEO)
print("⏱ Duration ≈", TOTAL_PUZZLES, "minutes")
