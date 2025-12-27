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


# --- CONFIGURATION ---
API_URL = "https://roynek.com/Chess_Sol_Puzzles/api/puzzle/random-by-rating?min=1000"
FPS = 30
COUNTDOWN_SEC = 4
MOVE_SEC = 1
TEMP_DIR = "frames"
# OUTPUT_VIDEO = "chess_short.mp4"
OUTPUT_VIDEO = "output_video/chess_short.mp4"
FONT_PATH = "./Roboto-Regular.ttf"
BOARD_SIZE = 800

# Audio files
BACKGROUND_MUSIC = "bg_music.mp3"
CLICK_SOUND = "move.mp3"

# Social media messages
MESSAGES = [
    "Can you find the winning move? 🧩 ({side} to move)",
    "Today's daily challenge — {side} to move!",
    "Test your tactics ({rating}) — {side} to move!",
    "What is the best move here? ({side} to play)",
    "Spot the winning sequence! 🔥 ({side})"
]
HASHTAGS = ["#Chess", "#ChessPuzzles", "#Tactics", "#BrainTeaser"]

# --- UTILITY FUNCTIONS ---
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

def send_to_social_media_api(platform, link, text, media=None, area=None):
    api_url = f'https://roynek.com/alltrenders/codes/python_API/social-media/{platform}'
    payload = {
        'link_2_post': link,
        'message': text,
        'media': media,
        'pages_ordered_ids': area,
    }

    headers = {'Content-Type': 'application/json'}
    print(json.dumps(payload, ensure_ascii=False))

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=3000)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print('Social Media Error:', str(e))
        return None

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

    # Rating
    draw.text((20, 20), f"Rating: {rating}", font=font_medium, fill="white")

    # Side to move
    if side_to_move:
        draw.text((20, 60), f"{side_to_move} to move", font=font_medium, fill="white")

    # Countdown timer
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

def save_frames(board, moves, rating, side_to_move):
    frame_count = 0

    # --- Initial position (no timer yet) ---
    for _ in range(FPS):
        im = create_frame_image(
            board,
            rating=rating,
            side_to_move=side_to_move
        )
        im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:04d}.png"))
        frame_count += 1

    # --- First move ---
    first_move = chess.Move.from_uci(moves[0])
    board.push(first_move)

    for _ in range(FPS * MOVE_SEC):
        im = create_frame_image(
            board,
            last_move=first_move,
            rating=rating,
            side_to_move=side_to_move
        )
        im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:04d}.png"))
        frame_count += 1

    # --- Countdown AFTER first move ---
    for sec in range(COUNTDOWN_SEC, 0, -1):
        im = create_frame_image(
            board,
            timer=sec,
            rating=rating,
            side_to_move=side_to_move
        )
        for _ in range(FPS):
            im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:04d}.png"))
            frame_count += 1

    # --- Remaining moves ---
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
            im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:04d}.png"))
            frame_count += 1

    # Final pause
    for _ in range(FPS * 2):
        im = create_frame_image(
            board,
            rating=rating,
            side_to_move=side_to_move
        )
        im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:04d}.png"))
        frame_count += 1

# --- MAIN SCRIPT ---
os.makedirs(TEMP_DIR, exist_ok=True)

print("Fetching puzzle...")
data = requests.get(API_URL).json()
print("Puzzle data:", data)

board = chess.Board(data['fen'])
moves = data['moves']
rating = data['rating']

# side_to_move = "White" if board.turn == chess.WHITE else "Black"
solver_color = not board.turn  # opponent of FEN side
side_to_move = "White" if solver_color == chess.WHITE else "Black"

print("Generating frames...")
save_frames(board, moves, rating, side_to_move)

print("Encoding video...")
cmd = f"""
{FFMPEG_BIN} -y -framerate {FPS} -i {TEMP_DIR}/frame_%04d.png \
-i {BACKGROUND_MUSIC} -i {CLICK_SOUND} \
-filter_complex "[1:a]volume=0.3[a1];[2:a]volume=0.7[a2];[a1][a2]amix=inputs=2:duration=longest[aout]" \
-map 0:v -map "[aout]" -c:v libx264 -pix_fmt yuv420p -shortest {OUTPUT_VIDEO}
"""
subprocess.run(cmd, shell=True, check=True)

# --- SOCIAL POST ---
msg = random.choice(MESSAGES).format(
    rating=rating,
    side=side_to_move
)

tags = " ".join(random.sample(HASHTAGS, 3))
# full_message = f"{msg}\n\n{tags}\n\n@followers"
full_message = f" {msg} {tags} @followers "
safe_message = full_message.replace("\n", " ").strip()
safe_message = full_message.encode("ascii", "ignore").decode()

puzzle_link = f"https://roynek.com/Chess_Sol_Puzzles/public/?puzzle={data['id']}"
video_url = f"https://roynek.com/Chess_Sol_Puzzles/auto_post/{OUTPUT_VIDEO}"

output = send_to_social_media_api(
    platform='facebook',
    link=puzzle_link,
    text=safe_message,
    media=video_url,
    area='6'
)

# 6=chessSol
# 3=Nataya
# 7=Roynek Technologies

print("Facebook: Social API Response:", output)


output_x = send_to_social_media_api(
    platform='x',
    link=puzzle_link,
    text=safe_message,
    media=video_url,
    area='21'
)



print("X: Social API Response:", output_x)


# Cleanup
for f in os.listdir(TEMP_DIR):
    os.remove(os.path.join(TEMP_DIR, f))
os.rmdir(TEMP_DIR)

print("✅ Done. Video generated:", OUTPUT_VIDEO)
