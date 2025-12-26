import chess
import chess.svg
import cairosvg
import os
import subprocess
import requests
import json
import random

# --- CONFIGURATION ---
API_URL = "https://roynek.com/Chess_Sol_Puzzles/api/puzzle/random-by-rating?min=1000"
FPS = 30
COUNTDOWN_SEC = 4 
MOVE_SEC = 1
TEMP_DIR = "frames"
OUTPUT_VIDEO = "chess_short.mp4" # This will overwrite every time it runs

# --- SOCIAL MEDIA DATA ---
MESSAGES = [
    "Can you find the winning move? 🧩",
    "Today's daily challenge is here!",
    "Test your tactics with this {rating} rated puzzle!",
    "What is the best move here?",
    "Spot the winning sequence! 🔥"
]
HASHTAGS = ["#Chess", "#ChessPuzzles", "#Tactics", "#Grandmaster", "#BrainTeaser"]

def send_to_social_media_api(platform, link, text, media=None, area=None):
    api_url = 'https://roynek.com/alltrenders/codes/python_API/social-media/' + platform
    payload = {
        'link_2_post': link,
        'message': text,
        'media_url': media,
        'pages_ordered_ids': area,
    }
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(api_url, data=json.dumps(payload), headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print('Social Media Error:', str(e))
        return None

if not os.path.exists(TEMP_DIR): os.makedirs(TEMP_DIR)

# 1. Fetch Puzzle
print("Fetching puzzle...")
data = requests.get(API_URL).json()
print("data gotten: ", data)
puzzle_id = data['id']
starting_fen = data['fen']
moves = data['moves']
rating = data['rating']

board = chess.Board(starting_fen)
frame_count = 0

def save_frames(duration_sec, highlight_move=None):
    global frame_count
    num_frames = int(duration_sec * FPS)
    svg_data = chess.svg.board(board, size=800, lastmove=highlight_move)
    png_path = f"{TEMP_DIR}/frame_{frame_count:04d}.png"
    cairosvg.svg2png(bytestring=svg_data, write_to=png_path)
    for i in range(1, num_frames):
        os.link(png_path, f"{TEMP_DIR}/frame_{frame_count + i:04d}.png")
    frame_count += num_frames

# --- SCENE GENERATION ---
opponent_move = chess.Move.from_uci(moves[0])
board.push(opponent_move)
save_frames(1, highlight_move=opponent_move)
save_frames(COUNTDOWN_SEC, highlight_move=opponent_move)

for move_uci in moves[1:]:
    sol_move = chess.Move.from_uci(move_uci)
    board.push(sol_move)
    save_frames(MOVE_SEC, highlight_move=sol_move)

save_frames(2)

# 2. FFmpeg Encoding
draw_filters = (
    f"drawtext=text='Rating\\: {rating}':fontcolor=white:fontsize=40:x=40:y=40,"
    f"drawtext=text='FIND THE BEST MOVE':fontcolor=yellow:fontsize=50:x=(w-text_w)/2:y=100:enable='between(t,1,{1+COUNTDOWN_SEC})',"
    f"drawtext=text='%{{eif\\:{COUNTDOWN_SEC}-(t-1)\\:d}}':fontcolor=white:fontsize=120:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,1,{1+COUNTDOWN_SEC})'"
)

# cmd = (
#     f"ffmpeg -y -framerate {FPS} -i {TEMP_DIR}/frame_%04d.png "
#     f"-vf \"{draw_filters}\" -c:v libx264 -pix_fmt yuv420p {OUTPUT_VIDEO}"
# )

# Change this line in your script:
# cmd = (
#     f"./ffmpeg -y -framerate {FPS} -i {TEMP_DIR}/frame_%04d.png "
#     f"-vf \"{draw_filters}\" -c:v libx264 -pix_fmt yuv420p {OUTPUT_VIDEO}"
# )

# Fixing Cpanel font issues
cmd = (
    f"./ffmpeg -y -framerate {FPS} -i {TEMP_DIR}/frame_%04d.png "
    f"-c:v libx264 -pix_fmt yuv420p {OUTPUT_VIDEO}"
)



print("Encoding video...")
subprocess.run(cmd, shell=True)

# 3. Post to Social Media (Only after video is complete)
print("Video ready. Sending to Social Media API...")

# Construct Message
random_msg = random.choice(MESSAGES).format(rating=rating)
random_tags = " ".join(random.sample(HASHTAGS, 3))
full_message = f"{random_msg}\n\n{random_tags}\n\n@followers"

# Construct URLs
puzzle_link = f"https://roynek.com/Chess_Sol_Puzzles/public/?puzzle={puzzle_id}"
video_url = f"https://roynek.com/Chess_Sol_Puzzles/auto_post/{OUTPUT_VIDEO}"

#facebook
social_result = send_to_social_media_api(
    platform='facebook',
    link=puzzle_link,
    text=full_message,
    media=video_url,
    area='3'
)
print("Social API Response:", social_result)

#X
social_result_X = send_to_social_media_api(
    platform='facebook',
    link=puzzle_link,
    text=full_message,
    media=video_url,
    # area='3'
)
print("Social API Response:", social_result_X)


# Cleanup
for f in os.listdir(TEMP_DIR): os.remove(os.path.join(TEMP_DIR, f))
os.rmdir(TEMP_DIR)
print(f"Process Complete. Video saved as {OUTPUT_VIDEO}")