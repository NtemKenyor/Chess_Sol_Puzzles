import chess
import chess.svg
import cairosvg
import os
import subprocess
import requests
import json
import random
import shutil

# =========================
# CONFIGURATION
# =========================
API_URL = "https://roynek.com/Chess_Sol_Puzzles/api/puzzle/random-by-rating?min=1000"
FPS = 30
COUNTDOWN_SEC = 4
MOVE_SEC = 1
TEMP_DIR = "frames"
OUTPUT_VIDEO = "chess_short.mp4"

# =========================
# SOCIAL MEDIA DATA
# =========================
MESSAGES = [
    "Can you find the winning move? 🧩",
    "Today's daily challenge is here!",
    "Test your tactics with this {rating} rated puzzle!",
    "What is the best move here?",
    "Spot the winning sequence! 🔥"
]

HASHTAGS = ["#Chess", "#ChessPuzzles", "#Tactics", "#Grandmaster", "#BrainTeaser"]

# =========================
# SOCIAL MEDIA API
# =========================
def send_to_social_media_api(platform, link, text, media=None, area=None):
    api_url = f"https://roynek.com/alltrenders/codes/python_API/social-media/{platform}"
    payload = {
        "link_2_post": link,
        "message": text,
        "media_url": media,
        "pages_ordered_ids": area
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(
            api_url,
            data=json.dumps(payload),
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        return response.text
    except Exception as e:
        print("Social Media Error:", e)
        return None

# =========================
# SVG RENDERING WITH OVERLAY
# =========================
def render_svg_with_overlay(board, highlight_move=None, rating=None, title=None, countdown=None):
    svg = chess.svg.board(
        board,
        size=800,
        lastmove=highlight_move,
        coordinates=True
    )

    overlay = ""

    # Rating (top-left)
    if rating is not None:
        overlay += f"""
        <text x="30" y="50"
              font-size="40"
              fill="white"
              font-family="Arial"
              font-weight="bold">
            Rating: {rating}
        </text>
        """

    # Title (top-center)
    if title:
        overlay += f"""
        <text x="400" y="100"
              text-anchor="middle"
              font-size="50"
              fill="yellow"
              font-family="Arial"
              font-weight="bold">
            {title}
        </text>
        """

    # Countdown (center)
    if countdown is not None:
        overlay += f"""
        <text x="400" y="450"
              text-anchor="middle"
              font-size="140"
              fill="white"
              font-family="Arial"
              font-weight="bold">
            {countdown}
        </text>
        """

    return svg.replace("</svg>", overlay + "</svg>")

# =========================
# FRAME GENERATION
# =========================
frame_count = 0

def save_frames(board, duration_sec, highlight_move=None, title=None, countdown_start=None):
    global frame_count
    num_frames = int(duration_sec * FPS)

    for i in range(num_frames):
        countdown = None
        if countdown_start is not None:
            seconds_left = countdown_start - int(i / FPS)
            countdown = max(seconds_left, 0)

        svg_data = render_svg_with_overlay(
            board,
            highlight_move=highlight_move,
            rating=rating,
            title=title,
            countdown=countdown
        )

        png_path = f"{TEMP_DIR}/frame_{frame_count:04d}.png"
        cairosvg.svg2png(
            bytestring=svg_data.encode("utf-8"),
            write_to=png_path
        )
        frame_count += 1

# =========================
# MAIN PROCESS
# =========================
if os.path.exists(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)
os.makedirs(TEMP_DIR)

print("Fetching puzzle...")
data = requests.get(API_URL).json()
print("data gotten:", data)

puzzle_id = data["id"]
starting_fen = data["fen"]
moves = data["moves"]
rating = data["rating"]

board = chess.Board(starting_fen)

# --- Opponent move ---
opponent_move = chess.Move.from_uci(moves[0])
board.push(opponent_move)

save_frames(board, duration_sec=1, highlight_move=opponent_move)

# --- Countdown scene ---
save_frames(
    board,
    duration_sec=COUNTDOWN_SEC,
    highlight_move=opponent_move,
    title="FIND THE BEST MOVE",
    countdown_start=COUNTDOWN_SEC
)

# --- Solution moves ---
for move_uci in moves[1:]:
    sol_move = chess.Move.from_uci(move_uci)
    board.push(sol_move)
    save_frames(board, duration_sec=MOVE_SEC, highlight_move=sol_move)

# --- End pause ---
save_frames(board, duration_sec=2)

# =========================
# FFmpeg Encoding
# =========================
cmd = (
    f"./ffmpeg -y -framerate {FPS} -i {TEMP_DIR}/frame_%04d.png "
    f"-c:v libx264 -pix_fmt yuv420p {OUTPUT_VIDEO}"
)

print("Encoding video...")
result = subprocess.run(cmd, shell=True)

if result.returncode != 0 or not os.path.exists(OUTPUT_VIDEO):
    raise RuntimeError("FFmpeg failed to generate video")

print("Video ready. Sending to Social Media API...")

# =========================
# POST TO SOCIAL MEDIA
# =========================
random_msg = random.choice(MESSAGES).format(rating=rating)
random_tags = " ".join(random.sample(HASHTAGS, 3))
full_message = f"{random_msg}\n\n{random_tags}\n\n@followers"

puzzle_link = f"https://roynek.com/Chess_Sol_Puzzles/public/?puzzle={puzzle_id}"
video_url = f"https://roynek.com/Chess_Sol_Puzzles/auto_post/{OUTPUT_VIDEO}"

# # Facebook
# social_result = send_to_social_media_api(
#     platform="facebook",
#     link=puzzle_link,
#     text=full_message,
#     media=video_url,
#     area="3"
# )
# print("Facebook API Response:", social_result)

# # X (same endpoint in your system)
# social_result_x = send_to_social_media_api(
#     platform="facebook",
#     link=puzzle_link,
#     text=full_message,
#     media=video_url
# )
# print("X API Response:", social_result_x)

# =========================
# CLEANUP
# =========================
shutil.rmtree(TEMP_DIR)
print(f"Process Complete. Video saved as {OUTPUT_VIDEO}")
