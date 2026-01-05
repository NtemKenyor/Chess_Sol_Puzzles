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
FPS = 30
COUNTDOWN_SEC = 10
MOVE_SEC = 1
BREAK_SEC = 3  # Break between puzzles
TEMP_DIR = "frames"
OUTPUT_VIDEO = "output_video/chess_long.mp4"
FONT_PATH = "./Roboto-Regular.ttf"
BOARD_SIZE = 800

# Audio files
BACKGROUND_MUSIC = "bg_music.mp3"
CLICK_SOUND = "move.mp3"

# Puzzle themes to fetch (mix for variety)
PUZZLE_THEMES = [
    {"q": "endgame", "min": 1500, "max": 3000},
    {"q": "mate in 2", "min": 1200, "max": 2500},
    {"q": "mate", "min": 1500, "max": 2800},
    {"theme": "crushing", "min": 1400, "max": 2600},
    {"q": "fork", "min": 1300, "max": 2400},
    {"q": "pin", "min": 1300, "max": 2400},
    {"q": "skewer", "min": 1400, "max": 2500},
]

NUM_PUZZLES = 5 #60

# Social media messages for variety
MESSAGES = [
    "Can you find the winning move? 🧩",
    "Test your tactics!",
    "What's the best move here?",
    "Spot the winning sequence! 🔥",
    "Chess puzzle challenge!"
]

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

def fetch_puzzles(num_puzzles=60):
    """Fetch puzzles from various themes and randomly select the desired number"""
    all_puzzles = []
    
    for theme_config in PUZZLE_THEMES:
        try:
            # Build URL with parameters
            base_url = "https://roynek.com/Chess_Sol_Puzzles/api/puzzles"
            params = theme_config.copy()
            params['limit'] = 100  # Fetch 100 per theme
            
            # Convert params to URL string
            param_str = "&".join([f"{k}={v}" for k, v in params.items()])
            url = f"{base_url}?{param_str}"
            
            print(f"Fetching from: {url}")
            response = requests.get(url, timeout=30)
            data = response.json()
            
            if 'results' in data and len(data['results']) > 0:
                all_puzzles.extend(data['results'])
                print(f"  -> Got {len(data['results'])} puzzles")
        except Exception as e:
            print(f"Error fetching theme {theme_config}: {e}")
            continue
    
    # Shuffle and select random puzzles
    random.shuffle(all_puzzles)
    selected_puzzles = all_puzzles[:num_puzzles]
    
    print(f"\nTotal puzzles collected: {len(all_puzzles)}")
    print(f"Selected for video: {len(selected_puzzles)}")
    
    return selected_puzzles

def create_frame_image(board, last_move=None, timer=None, rating=None, 
                       side_to_move=None, puzzle_num=None, total_puzzles=None,
                       message=None):
    """Create a frame image with the chess board and overlays"""
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
    font_small = ImageFont.truetype(FONT_PATH, 28)

    # Puzzle number
    if puzzle_num and total_puzzles:
        text = f"Puzzle {puzzle_num}/{total_puzzles}"
        draw.text((20, 20), text, font=font_small, fill="yellow")
    
    # Rating
    if rating:
        draw.text((20, 55), f"Rating: {rating}", font=font_medium, fill="white")

    # Side to move
    if side_to_move:
        draw.text((20, 95), f"{side_to_move} to move", font=font_medium, fill="white")
    
    # Message
    if message:
        draw.text((20, 135), message, font=font_small, fill="lightblue")

    # Countdown timer (centered)
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

def create_break_frame(puzzle_num, total_puzzles):
    """Create a simple break frame between puzzles"""
    im = Image.new('RGBA', (BOARD_SIZE, BOARD_SIZE), color=(40, 40, 40, 255))
    draw = ImageDraw.Draw(im)
    
    font_large = ImageFont.truetype(FONT_PATH, 70)
    font_medium = ImageFont.truetype(FONT_PATH, 40)
    
    # "Next Puzzle" text
    text1 = "Next Puzzle"
    bbox1 = draw.textbbox((0, 0), text1, font=font_large)
    w1 = bbox1[2] - bbox1[0]
    draw.text(((BOARD_SIZE - w1) // 2, 300), text1, font=font_large, fill="white")
    
    # Puzzle number
    text2 = f"{puzzle_num + 1}/{total_puzzles}"
    bbox2 = draw.textbbox((0, 0), text2, font=font_medium)
    w2 = bbox2[2] - bbox2[0]
    draw.text(((BOARD_SIZE - w2) // 2, 400), text2, font=font_medium, fill="yellow")
    
    return im

def save_puzzle_frames(board, moves, rating, side_to_move, puzzle_num, 
                       total_puzzles, frame_count, message):
    """Generate all frames for a single puzzle"""
    
    # Convert moves string to list if needed
    if isinstance(moves, str):
        moves = moves.split()
    
    # --- Initial position (2 seconds) ---
    for _ in range(FPS * 2):
        im = create_frame_image(
            board,
            rating=rating,
            side_to_move=side_to_move,
            puzzle_num=puzzle_num,
            total_puzzles=total_puzzles,
            message=message
        )
        im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:06d}.png"))
        frame_count += 1

    # --- First move (the setup move) ---
    first_move = chess.Move.from_uci(moves[0])
    board.push(first_move)

    for _ in range(FPS * MOVE_SEC):
        im = create_frame_image(
            board,
            last_move=first_move,
            rating=rating,
            side_to_move=side_to_move,
            puzzle_num=puzzle_num,
            total_puzzles=total_puzzles,
            message=message
        )
        im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:06d}.png"))
        frame_count += 1

    # --- Countdown AFTER first move ---
    for sec in range(COUNTDOWN_SEC, 0, -1):
        im = create_frame_image(
            board,
            timer=sec,
            rating=rating,
            side_to_move=side_to_move,
            puzzle_num=puzzle_num,
            total_puzzles=total_puzzles,
            message=message
        )
        for _ in range(FPS):
            im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:06d}.png"))
            frame_count += 1

    # --- Remaining moves (solution) ---
    for move_uci in moves[1:]:
        move = chess.Move.from_uci(move_uci)
        board.push(move)
        for _ in range(FPS * MOVE_SEC):
            im = create_frame_image(
                board,
                last_move=move,
                rating=rating,
                side_to_move=side_to_move,
                puzzle_num=puzzle_num,
                total_puzzles=total_puzzles,
                message=message
            )
            im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:06d}.png"))
            frame_count += 1

    # Final pause (2 seconds)
    for _ in range(FPS * 2):
        im = create_frame_image(
            board,
            rating=rating,
            side_to_move=side_to_move,
            puzzle_num=puzzle_num,
            total_puzzles=total_puzzles,
            message="Solution shown!"
        )
        im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:06d}.png"))
        frame_count += 1
    
    return frame_count

def save_break_frames(puzzle_num, total_puzzles, frame_count):
    """Generate break frames between puzzles"""
    break_im = create_break_frame(puzzle_num, total_puzzles)
    for _ in range(FPS * BREAK_SEC):
        break_im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:06d}.png"))
        frame_count += 1
    return frame_count

# --- MAIN SCRIPT ---
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs("output_video", exist_ok=True)

print("=" * 60)
print("LONG CHESS PUZZLE VIDEO GENERATOR")
print("=" * 60)

# Fetch all puzzles
print("\n[1/3] Fetching puzzles...")
puzzles = fetch_puzzles(NUM_PUZZLES)

if len(puzzles) < NUM_PUZZLES:
    print(f"Warning: Only got {len(puzzles)} puzzles, expected {NUM_PUZZLES}")
else:
    print(f"Success: Got {len(puzzles)} puzzles!")

total_puzzles = min(len(puzzles), NUM_PUZZLES)

# Generate all frames
print("\n[2/3] Generating frames for all puzzles...")
frame_count = 0

for idx, puzzle_data in enumerate(puzzles[:total_puzzles], 1):
    print(f"\nProcessing puzzle {idx}/{total_puzzles} (ID: {puzzle_data['id']})")
    
    try:
        board = chess.Board(puzzle_data['fen'])
        moves = puzzle_data['moves']
        
        # Convert moves string to list if needed
        if isinstance(moves, str):
            moves = moves.split()
        
        rating = puzzle_data.get('rating', 'N/A')
        
        # Determine side to move (solver's perspective)
        solver_color = not board.turn
        side_to_move = "White" if solver_color == chess.WHITE else "Black"
        
        # Random message for variety
        message = random.choice(MESSAGES)
        
        # Generate frames for this puzzle
        frame_count = save_puzzle_frames(
            board, moves, rating, side_to_move,
            idx, total_puzzles, frame_count, message
        )
        
        # Add break between puzzles (except after last puzzle)
        if idx < total_puzzles:
            frame_count = save_break_frames(idx, total_puzzles, frame_count)
        
        print(f"  -> Total frames so far: {frame_count}")
        
    except Exception as e:
        print(f"  -> Error processing puzzle {idx}: {e}")
        continue

# Encode video
print(f"\n[3/3] Encoding video with {frame_count} frames...")
print("This may take a while for a 1-hour video...")

cmd = f"""
{FFMPEG_BIN} -y -framerate {FPS} -i {TEMP_DIR}/frame_%06d.png \
-i {BACKGROUND_MUSIC} -i {CLICK_SOUND} \
-filter_complex "[1:a]volume=0.2[a1];[2:a]volume=0.5[a2];[a1][a2]amix=inputs=2:duration=longest[aout]" \
-map 0:v -map "[aout]" -c:v libx264 -pix_fmt yuv420p -preset medium -crf 23 -shortest {OUTPUT_VIDEO}
"""

try:
    subprocess.run(cmd, shell=True, check=True)
    print("\n✅ Video encoding complete!")
except subprocess.CalledProcessError as e:
    print(f"\n❌ FFmpeg error: {e}")

# Cleanup
print("\nCleaning up temporary files...")
for f in os.listdir(TEMP_DIR):
    os.remove(os.path.join(TEMP_DIR, f))
os.rmdir(TEMP_DIR)

# Calculate video duration
duration_seconds = frame_count / FPS
duration_minutes = duration_seconds / 60

print("\n" + "=" * 60)
print("GENERATION COMPLETE!")
print("=" * 60)
print(f"Output file: {OUTPUT_VIDEO}")
print(f"Total puzzles: {total_puzzles}")
print(f"Total frames: {frame_count}")
print(f"Estimated duration: {duration_minutes:.1f} minutes ({duration_seconds:.0f} seconds)")
print("=" * 60)