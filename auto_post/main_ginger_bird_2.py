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
import sys

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
API_URL       = "https://roynek.com/Chess_Sol_Puzzles/api/puzzle/random-by-rating?min=1600"
FPS           = 30
COUNTDOWN_SEC = 15          # ⬆ was 10
INTRO_SEC     = 3           # hold the "initial position" before first move
ARROW_SEC     = 2           # ⬆ show arrow BEFORE executing a move
MOVE_SEC      = 2           # ⬆ was 1 – hold after move plays
FINAL_SEC     = 3           # pause at end
TEMP_DIR      = "frames"
OUTPUT_VIDEO  = "output_video/chess_short.mp4"
FONT_PATH     = "./Roboto-Regular.ttf"
BOARD_SIZE    = 800

# Audio
BACKGROUND_MUSIC  = "bg_music.mp3"
CLICK_SOUND       = "move.mp3"
BG_MUSIC_VOLUME   = 0.15    # ⬇ was 0.3  (0 = off, 1 = full)
INCLUDE_BG_MUSIC  = True    # set False to skip background music entirely
TTS_INTRO_FILE    = "tts_intro.mp3"   # generated at runtime

# Social copy
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
    raise FileNotFoundError("FFmpeg not found")

FFMPEG_BIN = detect_ffmpeg()
print("Using FFmpeg:", FFMPEG_BIN)


def send_to_social_media_api(platform, link, text, media=None, area=None,
                              x_comm_id=None, fb_post_to=None):
    api_url = f'https://roynek.com/alltrenders/codes/python_API/social-media/{platform}'
    payload  = {
        'link_2_post': link, 'message': text, 'media': media,
        'pages_ordered_ids': area, 'comm_id': x_comm_id, 'post_to': fb_post_to
    }
    headers  = {'Content-Type': 'application/json'}
    print(json.dumps(payload, ensure_ascii=False))
    try:
        r = requests.post(api_url, json=payload, headers=headers, timeout=3000)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print('Social Media Error:', e)
        return None


# ─────────────────────────────────────────────
#  TTS INTRO GENERATION
# ─────────────────────────────────────────────
INTRO_TEMPLATES = [
    "In {n} moves, can you spot the checkmate?",
    "White has a {n}-move winning combination. Can you see it?",
    "Black has a brilliant {n}-move sequence. Find it!",
    "In just {n} moves, {side} wins. Think you can solve it?",
    "This is a {rating}-rated puzzle. {side} to move — find the best line!",
    "Here's your daily chess challenge. {side} to move in {n} moves!",
    "Sharp tactics ahead! {side} to move. Can you crack it?",
    "Think fast! {side} has a killer {n}-move combo. Spot it!",
]

def build_intro_text(moves, side_to_move, rating):
    n     = (len(moves) + 1) // 2   # moves for the puzzle side
    n_str = ["one","two","three","four","five","six","seven","eight"][min(n,8)-1]
    tpl   = random.choice(INTRO_TEMPLATES)
    return tpl.format(n=n_str, side=side_to_move, rating=rating)

def generate_tts(text, out_file):
    """
    Try several free TTS methods in order of preference:
      1. edge-tts  (Microsoft Neural voices, free, needs internet)
      2. pyttsx3   (offline, robotic but reliable)
      3. espeak    (system, very robotic)
    Writes an MP3/WAV to out_file.
    """
    # --- edge-tts ---
    try:
        import edge_tts, asyncio
        voice    = random.choice(["en-US-GuyNeural", "en-US-JennyNeural",
                                  "en-GB-RyanNeural", "en-AU-NatashaNeural"])
        wav_tmp  = out_file.replace(".mp3", "_tmp.mp3")
        async def _run():
            comm = edge_tts.Communicate(text, voice)
            await comm.save(wav_tmp)
        asyncio.run(_run())
        os.rename(wav_tmp, out_file)
        print(f"[TTS] edge-tts ✓  voice={voice}")
        return True
    except Exception as e:
        print(f"[TTS] edge-tts failed: {e}")

    # --- pyttsx3 ---
    try:
        import pyttsx3, tempfile
        engine  = pyttsx3.init()
        engine.setProperty('rate', 150)
        tmp_wav = out_file.replace(".mp3", "_pyttsx3.wav")
        engine.save_to_file(text, tmp_wav)
        engine.runAndWait()
        # convert wav→mp3 via ffmpeg
        subprocess.run(
            [FFMPEG_BIN, "-y", "-i", tmp_wav, out_file],
            check=True, capture_output=True
        )
        os.remove(tmp_wav)
        print("[TTS] pyttsx3 ✓")
        return True
    except Exception as e:
        print(f"[TTS] pyttsx3 failed: {e}")

    # --- espeak ---
    try:
        wav_tmp = out_file.replace(".mp3", "_espeak.wav")
        subprocess.run(["espeak", "-w", wav_tmp, text], check=True, capture_output=True)
        subprocess.run([FFMPEG_BIN, "-y", "-i", wav_tmp, out_file],
                       check=True, capture_output=True)
        os.remove(wav_tmp)
        print("[TTS] espeak ✓")
        return True
    except Exception as e:
        print(f"[TTS] espeak failed: {e}")

    print("[TTS] All methods failed — video will have no spoken intro.")
    return False


# ─────────────────────────────────────────────
#  DRAWING HELPERS
# ─────────────────────────────────────────────
SQUARE_SIZE = BOARD_SIZE // 8

def square_to_pixel(square, flip=False):
    """Return (cx, cy) pixel center of a chess square."""
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
               color=(255, 170, 0, 210), shaft_w=18, head_size=36):
    """Draw a bold arrow from from_sq → to_sq on a PIL ImageDraw."""
    x1, y1 = square_to_pixel(from_sq, flip)
    x2, y2 = square_to_pixel(to_sq,   flip)

    angle  = math.atan2(y2 - y1, x2 - x1)
    length = math.hypot(x2 - x1, y2 - y1)

    # Shorten end so arrowhead looks right
    tip_x  = x2 - head_size * 0.6 * math.cos(angle)
    tip_y  = y2 - head_size * 0.6 * math.sin(angle)

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

    # Arrowhead (triangle)
    perp_x = math.sin(angle) * head_size
    perp_y = math.cos(angle) * head_size
    head   = [
        (x2,              y2),
        (tip_x + perp_x,  tip_y - perp_y),
        (tip_x - perp_x,  tip_y + perp_y),
    ]
    draw.polygon(head, fill=color)


def create_frame_image(board, last_move=None, arrow_move=None, timer=None,
                       rating=None, side_to_move=None, flip=False):
    """
    Render a single frame.
    arrow_move : chess.Move  – draw a golden arrow (shown BEFORE the move plays)
    """
    svg_data = chess.svg.board(
        board,
        size=BOARD_SIZE,
        lastmove=last_move,
        flipped=flip
    ).encode("UTF-8")

    tmp_png = os.path.join(TEMP_DIR, "tmp_frame.png")
    cairosvg.svg2png(bytestring=svg_data, write_to=tmp_png)

    im   = Image.open(tmp_png).convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")

    # ── Arrow overlay ──────────────────────────────────
    if arrow_move is not None:
        draw_arrow(draw, arrow_move.from_square, arrow_move.to_square, flip=flip)

    # ── Text overlays ─────────────────────────────────
    try:
        font_large  = ImageFont.truetype(FONT_PATH, 60)
        font_medium = ImageFont.truetype(FONT_PATH, 36)
        font_small  = ImageFont.truetype(FONT_PATH, 28)
    except Exception:
        font_large = font_medium = font_small = ImageFont.load_default()

    # Semi-transparent top bar
    bar_h = 80
    bar   = Image.new("RGBA", (BOARD_SIZE, bar_h), (0, 0, 0, 160))
    im.paste(bar, (0, 0), bar)
    draw  = ImageDraw.Draw(im, "RGBA")   # refresh after paste

    draw.text((16, 10),  f"Rating: {rating}",     font=font_small,  fill="white")
    draw.text((16, 42),  f"{side_to_move} to move", font=font_small, fill="#FFD700")

    # Countdown
    if timer is not None:
        txt  = str(timer)
        bbox = draw.textbbox((0, 0), txt, font=font_large)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        cx, cy = (BOARD_SIZE - w) // 2, (BOARD_SIZE - h) // 2

        # shadow
        draw.text((cx + 3, cy + 3), txt, font=font_large, fill=(0, 0, 0, 180))
        draw.text((cx, cy), txt, font=font_large, fill="white")

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

    # 1 ── Intro hold (no timer, no arrow) ─────────────────
    im = create_frame_image(board, rating=rating, side_to_move=side_to_move, flip=flip)
    save_n(im, FPS * INTRO_SEC)

    # Iterate through moves
    for i, move_uci in enumerate(moves):
        move = chess.Move.from_uci(move_uci)

        # 2 ── Arrow preview (BEFORE the move) ─────────────
        im = create_frame_image(board, arrow_move=move, rating=rating,
                                side_to_move=side_to_move, flip=flip)
        save_n(im, FPS * ARROW_SEC)

        # Push the move
        board.push(move)

        # 3 ── Show board after move ────────────────────────
        # After first move → show countdown
        if i == 0:
            for sec in range(COUNTDOWN_SEC, 0, -1):
                im = create_frame_image(board, last_move=move, timer=sec,
                                        rating=rating, side_to_move=side_to_move, flip=flip)
                save_n(im, FPS)
        else:
            im = create_frame_image(board, last_move=move, rating=rating,
                                    side_to_move=side_to_move, flip=flip)
            save_n(im, FPS * MOVE_SEC)

    # 4 ── Final pause ──────────────────────────────────────
    im = create_frame_image(board, rating=rating, side_to_move=side_to_move, flip=flip)
    save_n(im, FPS * FINAL_SEC)

    print(f"[frames] total frames saved: {frame_count}")


# ─────────────────────────────────────────────
#  VIDEO ENCODING
# ─────────────────────────────────────────────
def encode_video(tts_available):
    """Build the ffmpeg command based on which audio tracks exist."""
    video_input = f"-framerate {FPS} -i {TEMP_DIR}/frame_%05d.png"

    # Build audio filter graph
    audio_inputs   = []
    filter_complex = ""

    if tts_available and os.path.exists(TTS_INTRO_FILE):
        audio_inputs.append(f"-i {TTS_INTRO_FILE}")          # [1:a] TTS
    if INCLUDE_BG_MUSIC and os.path.exists(BACKGROUND_MUSIC):
        audio_inputs.append(f"-i {BACKGROUND_MUSIC}")         # [2:a] or [1:a]
    if os.path.exists(CLICK_SOUND):
        audio_inputs.append(f"-i {CLICK_SOUND}")

    n_audio = len(audio_inputs)

    if n_audio == 0:
        # No audio at all
        cmd = (f"{FFMPEG_BIN} -y {video_input} "
               f"-c:v libx264 -pix_fmt yuv420p {OUTPUT_VIDEO}")

    elif n_audio == 1 and tts_available:
        # TTS only
        cmd = (f"{FFMPEG_BIN} -y {video_input} {audio_inputs[0]} "
               f"-map 0:v -map 1:a -c:v libx264 -pix_fmt yuv420p -shortest {OUTPUT_VIDEO}")

    elif INCLUDE_BG_MUSIC and not tts_available:
        # bg music + click
        bg_idx   = 1
        clk_idx  = 2 if os.path.exists(CLICK_SOUND) else None
        a_inputs = " ".join(audio_inputs)
        if clk_idx:
            fc = (f"[{bg_idx}:a]volume={BG_MUSIC_VOLUME}[bg];"
                  f"[{clk_idx}:a]volume=0.7[clk];"
                  f"[bg][clk]amix=inputs=2:duration=longest[aout]")
        else:
            fc = f"[{bg_idx}:a]volume={BG_MUSIC_VOLUME}[aout]"
        cmd = (f"{FFMPEG_BIN} -y {video_input} {a_inputs} "
               f'-filter_complex "{fc}" '
               f"-map 0:v -map [aout] -c:v libx264 -pix_fmt yuv420p -shortest {OUTPUT_VIDEO}")

    else:
        # TTS + bg music + optional click
        idx  = 1
        parts_in  = []
        parts_mix = []

        tts_idx = idx; idx += 1
        parts_in.append(audio_inputs[0])
        parts_mix.append(f"[{tts_idx}:a]volume=1.0[tts]")

        if INCLUDE_BG_MUSIC and os.path.exists(BACKGROUND_MUSIC):
            bg_idx = idx; idx += 1
            parts_in.append(audio_inputs[1])
            parts_mix.append(f"[{bg_idx}:a]volume={BG_MUSIC_VOLUME}[bg]")

        if os.path.exists(CLICK_SOUND):
            clk_idx = idx; idx += 1
            parts_in.append(audio_inputs[-1])
            parts_mix.append(f"[{clk_idx}:a]volume=0.7[clk]")

        labels  = "[tts]" + ("[bg]" if INCLUDE_BG_MUSIC and os.path.exists(BACKGROUND_MUSIC) else "") \
                           + ("[clk]" if os.path.exists(CLICK_SOUND) else "")
        n_mix   = labels.count("[")
        mix_fc  = ";".join(parts_mix) + f";{labels}amix=inputs={n_mix}:duration=longest[aout]"

        a_inputs_str = " ".join(parts_in)
        cmd = (f"{FFMPEG_BIN} -y {video_input} {a_inputs_str} "
               f'-filter_complex "{mix_fc}" '
               f"-map 0:v -map [aout] -c:v libx264 -pix_fmt yuv420p -shortest {OUTPUT_VIDEO}")

    print("[ffmpeg] Running:", cmd[:200], "...")
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
flip         = (solver_color == chess.BLACK)   # flip board so solver is at bottom

# ── TTS intro ──────────────────────────────────────────────
intro_text    = build_intro_text(moves, side_to_move, rating)
print(f"[TTS] Intro text: {intro_text}")
tts_available = generate_tts(intro_text, TTS_INTRO_FILE)

# ── Frames ─────────────────────────────────────────────────
print("Generating frames...")
save_frames(board, moves, rating, side_to_move, flip=flip)

# ── Encode ─────────────────────────────────────────────────
print("Encoding video...")
encode_video(tts_available)

# ── Social copy ────────────────────────────────────────────
msg = random.choice(MESSAGES).format(rating=rating, side=side_to_move)
print(f"\n📢  Social copy: {msg}")

# ── Cleanup ────────────────────────────────────────────────
for f in os.listdir(TEMP_DIR):
    os.remove(os.path.join(TEMP_DIR, f))
os.rmdir(TEMP_DIR)

if tts_available and os.path.exists(TTS_INTRO_FILE):
    os.remove(TTS_INTRO_FILE)

print(f"\n✅  Done — video saved to: {OUTPUT_VIDEO}")
print(f"   Intro spoken: {intro_text}")