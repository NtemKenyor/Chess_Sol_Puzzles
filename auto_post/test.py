import os
import chess
import chess.svg
import cairosvg
from PIL import Image, ImageDraw, ImageFont
import subprocess
import requests
import json
import random
import shutil

# --- CONFIGURATION ---
API_URL = "https://roynek.com/Chess_Sol_Puzzles/api/puzzle/random-by-rating?min=1000"
FPS = 30
COUNTDOWN_SEC = 4
MOVE_SEC = 1
TEMP_DIR = "frames"
OUTPUT_VIDEO = "chess_short.mp4"
FONT_PATH = "./Roboto-Regular.ttf"
BOARD_SIZE = 800

# Audio files
BACKGROUND_MUSIC = "bg_music.mp3"
CLICK_SOUND = "move.mp3"

# Social media messages
MESSAGES = [
    "Can you find the winning move? 🧩",
    "Today's daily challenge is here!",
    "Test your tactics with this {rating} rated puzzle!",
    "What is the best move here?",
    "Spot the winning sequence! 🔥"
]
HASHTAGS = ["#Chess", "#ChessPuzzles", "#Tactics", "#Grandmaster", "#BrainTeaser"]

# --- UTILITY FUNCTIONS ---
def detect_ffmpeg():
    """Try system ffmpeg, otherwise local static binary"""
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin
    local_bin = "./ffmpeg-7.0.2-amd64-static/ffmpeg"
    if os.path.exists(local_bin):
        os.chmod(local_bin, 0o755)
        return local_bin
    raise FileNotFoundError("FFmpeg not found. Install system ffmpeg or place static binary.")

FFMPEG_BIN = detect_ffmpeg()
print("Using FFmpeg:", FFMPEG_BIN)

def send_to_social_media_api(platform, link, text, media=None, area=None):
    api_url = f'https://roynek.com/alltrenders/codes/python_API/social-media/{platform}'
    payload = {
        'link_2_post': link,
        'message': text,
        'media_url': media,
        'pages_ordered_ids': area,
    }
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print('Social Media Error:', str(e))
        return None

def create_frame_image(board, last_move=None, timer=None, rating=None):
    """Generate a single PIL image frame with board, move highlight, rating, and timer"""
    svg_data = chess.svg.board(board, size=BOARD_SIZE, lastmove=last_move).encode("UTF-8")
    tmp_png = os.path.join(TEMP_DIR, "tmp.png")
    cairosvg.svg2png(bytestring=svg_data, write_to=tmp_png)

    im = Image.open(tmp_png).convert("RGBA")
    draw = ImageDraw.Draw(im)

    font_large = ImageFont.truetype(FONT_PATH, 60)
    font_medium = ImageFont.truetype(FONT_PATH, 40)

    if rating:
        draw.text((20, 20), f"Rating: {rating}", font=font_medium, fill=(255,255,255,255))
    
    if timer is not None:
        bbox = draw.textbbox((0,0), str(timer), font=font_large)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text(((BOARD_SIZE-w)//2, (BOARD_SIZE-h)//2), str(timer), font=font_large, fill=(255,255,255,255))
    
    return im

def save_frames(board, moves, rating):
    """Generate all frames including countdown and moves"""
    frame_count = 0
    
    # Countdown
    for sec in range(COUNTDOWN_SEC, 0, -1):
        im = create_frame_image(board, last_move=None, timer=sec, rating=rating)
        for _ in range(FPS):
            im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:04d}.png"))
            frame_count += 1

    # Moves
    for move_uci in moves:
        move = chess.Move.from_uci(move_uci)
        board.push(move)
        for _ in range(FPS * MOVE_SEC):
            im = create_frame_image(board, last_move=move, timer=None, rating=rating)
            im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:04d}.png"))
            frame_count += 1

    # Pause final 2 sec
    for _ in range(FPS * 2):
        im = create_frame_image(board, last_move=None, timer=None, rating=rating)
        im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:04d}.png"))
        frame_count += 1

# --- MAIN SCRIPT ---
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Fetch puzzle
print("Fetching puzzle...")
data = requests.get(API_URL).json()
print("Puzzle data:", data)

board = chess.Board(data['fen'])
moves = data['moves']
rating = data['rating']

# Generate frames
print("Generating frames...")
save_frames(board, moves, rating)

# Encode video
cmd = f"""
{FFMPEG_BIN} -y -framerate {FPS} -i {TEMP_DIR}/frame_%04d.png -i {BACKGROUND_MUSIC} -i {CLICK_SOUND} \
-filter_complex "[1:a]volume=0.3[a1];[2:a]volume=0.7[a2];[a1][a2]amix=inputs=2:duration=longest[aout]" \
-map 0:v -map "[aout]" -c:v libx264 -pix_fmt yuv420p -shortest {OUTPUT_VIDEO}
"""
print("Encoding video...")
subprocess.run(cmd, shell=True, check=True)

# Post to social media
random_msg = random.choice(MESSAGES).format(rating=rating)
random_tags = " ".join(random.sample(HASHTAGS, 3))
full_message = f"{random_msg}\n\n{random_tags}\n\n@followers"

puzzle_link = f"https://roynek.com/Chess_Sol_Puzzles/public/?puzzle={data['id']}"
video_url = f"https://roynek.com/Chess_Sol_Puzzles/auto_post/{OUTPUT_VIDEO}"

# social_result = send_to_social_media_api(
#     platform='facebook',
#     link=puzzle_link,
#     text=full_message,
#     media=video_url,
#     area='3'
# )
# print("Facebook Response:", social_result)

# Cleanup
for f in os.listdir(TEMP_DIR):
    os.remove(os.path.join(TEMP_DIR, f))
os.rmdir(TEMP_DIR)

print(f"Process complete. Video saved as {OUTPUT_VIDEO}")
