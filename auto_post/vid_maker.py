import chess
import chess.svg
import cairosvg
import os
import subprocess
import requests

# --- CONFIGURATION ---
API_URL = "https://roynek.com/Chess_Sol_Puzzles/api/puzzle/random-by-rating?min=1000"
FPS = 30
COUNTDOWN_SEC = 4 
MOVE_SEC = 1
TEMP_DIR = "frames"
OUTPUT_VIDEO = "chess_short.mp4"

if not os.path.exists(TEMP_DIR): os.makedirs(TEMP_DIR)

# 1. Fetch Puzzle
print("Fetching puzzle...")
data = requests.get(API_URL).json()
print("data gotten: ", data)
starting_fen = data['fen']
moves = data['moves']  # List: ["a7c5", "b2g2"]
rating = data['rating']

board = chess.Board(starting_fen)
frame_count = 0

def save_frames(duration_sec, highlight_move=None):
    global frame_count
    num_frames = int(duration_sec * FPS)
    # Generate the board image
    svg_data = chess.svg.board(board, size=800, lastmove=highlight_move)
    png_path = f"{TEMP_DIR}/frame_{frame_count:04d}.png"
    cairosvg.svg2png(bytestring=svg_data, write_to=png_path)
    
    for i in range(1, num_frames):
        os.link(png_path, f"{TEMP_DIR}/frame_{frame_count + i:04d}.png")
    frame_count += num_frames

# --- SCENE GENERATION ---

# Scene 1: The Opponent's Move (1 second)
# This makes the video feel dynamic right away
opponent_move = chess.Move.from_uci(moves[0])
board.push(opponent_move)
save_frames(1, highlight_move=opponent_move)

# Scene 2: The Thinking Period (Countdown)
# We stay on the board after the opponent moved
save_frames(COUNTDOWN_SEC, highlight_move=opponent_move)

# Scene 3: The Solution
for move_uci in moves[1:]:
    sol_move = chess.Move.from_uci(move_uci)
    board.push(sol_move)
    save_frames(MOVE_SEC, highlight_move=sol_move)

# Scene 4: Final Pose (2 seconds)
save_frames(2)

# 2. FFmpeg with Overlays
# We'll add the rating and a "Your Turn" message
draw_filters = (
    f"drawtext=text='Rating\\: {rating}':fontcolor=white:fontsize=40:x=40:y=40,"
    f"drawtext=text='FIND THE BEST MOVE':fontcolor=yellow:fontsize=50:x=(w-text_w)/2:y=100:enable='between(t,1,{1+COUNTDOWN_SEC})',"
    f"drawtext=text='%{{eif\\:{COUNTDOWN_SEC}-(t-1)\\:d}}':fontcolor=white:fontsize=120:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,1,{1+COUNTDOWN_SEC})'"
)

cmd = (
    f"ffmpeg -y -framerate {FPS} -i {TEMP_DIR}/frame_%04d.png "
    f"-vf \"{draw_filters}\" -c:v libx264 -pix_fmt yuv420p {OUTPUT_VIDEO}"
)

print("Encoding...")
subprocess.run(cmd, shell=True)

# Cleanup
for f in os.listdir(TEMP_DIR): os.remove(os.path.join(TEMP_DIR, f))
os.rmdir(TEMP_DIR)
print(f"Video Complete: {OUTPUT_VIDEO}")