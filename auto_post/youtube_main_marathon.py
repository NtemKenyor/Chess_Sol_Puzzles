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

# ═══════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════
NUM_PUZZLES   = 3          # how many puzzles to include in the video
FPS           = 30
COUNTDOWN_SEC = 20          # thinking time per puzzle
INTRO_SEC     = 3           # hold initial board before any move
ARROW_SEC     = 2           # show arrow before each move executes
MOVE_SEC      = 2           # hold board after each move plays
FINAL_SEC     = 3           # pause at end of each puzzle
BREAK_SEC     = 4           # transition screen between puzzles

TEMP_DIR      = "frames"
OUTPUT_VIDEO  = "output_video/chess_long.mp4"
FONT_PATH     = "./Roboto-Regular.ttf"
BOARD_SIZE    = 800

# ── Intro Audio ───────────────────────────────────────────
# Folder with YOUR recorded intro files. Picked once, at the very start.
# Supported: .mp3  .wav  .ogg  .m4a
# INTRO_AUDIO_DIR = "./intro_sounds"
# INTRO_AUDIO_DIR = "./intro_sounds"
ls = ["./intro_sounds", "/intro_fake"] # intro_fake does not exist. I am using it to skip intro audios..
INTRO_AUDIO_DIR = random.choice(ls)    # ← point this at your folder


# ── Background & Click Audio ──────────────────────────────
# Use royalty-free / CC0 files. Good sources:
#   Music  → https://pixabay.com/music/
#   Clicks → https://freesound.org  (filter CC0)
# BACKGROUND_MUSIC = "bg_music.mp3"
BACKGROUND_MUSIC = ""
CLICK_SOUND      = "move.mp3"
BG_MUSIC_VOLUME  = 0.12    # very subtle (0.0 – 1.0)
CLICK_VOLUME     = 0.65
INCLUDE_BG_MUSIC = True    # set False for a silent video

# ── Arrow Colors ──────────────────────────────────────────
# Even move index (0, 2, 4…) = opponent  → warning orange
# Odd  move index (1, 3, 5…) = solver    → gold
ARROW_COLOR_SOLVER   = (255, 215,   0, 230)   # gold    #FFD700
ARROW_COLOR_OPPONENT = (255,  87,  34, 210)   # orange  #FF5722

# ── Puzzle Themes ─────────────────────────────────────────
# Each entry is fetched separately; results are pooled and de-duplicated.
PUZZLE_THEMES = [
    # {"addon": "CHECKMATE", "min": 1800, "max": 4500, "random": "true" },
    {"q": "endgame",   "min": 1800, "max": 3000},
    {"q": "mate in 2", "min": 1500, "max": 4500},
    {"q": "mate",      "min": 1700, "max": 4800},
    {"theme": "crushing", "min": 1700, "max": 4600},
    {"q": "fork",      "min": 1400, "max": 3400},
    {"q": "pin",       "min": 1500, "max": 3400},
    
]

# ── On-board Messages (shown per puzzle) ─────────────────
PUZZLE_MESSAGES = [
    "Only a GrandMaster can get this right!",
    "Can you find the winning move?",
    "Test your tactics!",
    "Inspired from Grandmaster games",
    "What's the best move here?",
    "Spot the winning sequence!",
    "The most complex chess puzzles!",
    "Chess Puzzle Challenge!",
    "How fast can you solve this?",
    "Think like a champion ♟",
]

# ── Social Copy ───────────────────────────────────────────
SOCIAL_MESSAGES = [
    "Can you solve all {n} puzzles? 🧩 Drop your score below!",
    "{n} chess puzzles in one video — how many can you get?",
    "Marathon chess challenge 🔥 — {n} puzzles, can you ace them all?",
    "Train like a GM — {n} tactical puzzles back to back!",
]
# HASHTAGS = ["#Chess", "#ChessPuzzles", "#Tactics", "#BrainTeaser", "#ChessMarathon"]
HASHTAGS = ["#ChessTactics", "#ChessStrategy", "#Checkmate", "#Grandmaster", "#Chess", "#ChessReels", "#BoardGames", "#ChessPunks", "#ChessSol", "#Checkmate", "#LearnChess", "#ChessMasterclass", "#ChessTips", "#PuzzleSolving", "#MentalGym", "#StrategicThinking", "#SpeedChess"]



# ═══════════════════════════════════════════════════════════
#  UTILITIES
# ═══════════════════════════════════════════════════════════
def detect_ffmpeg():
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin
    local_bin = "./ffmpeg-7.0.2-amd64-static/ffmpeg"
    if os.path.exists(local_bin):
        os.chmod(local_bin, 0o755)
        return local_bin
    raise FileNotFoundError(
        "FFmpeg not found. Install via: sudo apt install ffmpeg"
    )

FFMPEG_BIN = detect_ffmpeg()
print("Using FFmpeg:", FFMPEG_BIN)


def pick_intro_audio():
    """Pick one of your recorded intro files at random. Returns None if unavailable."""
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
        print(f"[intro] No audio files in '{INTRO_AUDIO_DIR}' — skipping intro audio.")
        return None
    chosen = random.choice(files)
    print(f"[intro] Selected: {os.path.basename(chosen)}")
    return chosen


# def fetch_puzzles(target_count):
#     """
#     Fetch puzzles from all PUZZLE_THEMES, de-duplicate by puzzle ID,
#     and return exactly target_count unique puzzles (or as many as available).
#     Retries themes if pool is too small to fill the target.
#     """
#     seen_ids   = set()
#     unique     = []
#     max_rounds = 3   # retry rounds if we don't have enough

#     for round_num in range(max_rounds):
#         if len(unique) >= target_count:
#             break

#         print(f"\n[fetch] Round {round_num + 1} — need {target_count - len(unique)} more puzzles")

#         for theme_cfg in PUZZLE_THEMES:
#             if len(unique) >= target_count:
#                 break
#             try:
#                 params    = {**theme_cfg, "limit": 100}
#                 param_str = "&".join(f"{k}={v}" for k, v in params.items())
#                 url       = f"https://roynek.com/Chess_Sol_Puzzles/api/puzzles?{param_str}"
#                 print(f"  Fetching: {url}")
#                 resp = requests.get(url, timeout=30)
#                 data = resp.json()

#                 results = data.get("results", [])
#                 before  = len(unique)

#                 for p in results:
#                     pid = p.get("id")
#                     if pid and pid not in seen_ids:
#                         seen_ids.add(pid)
#                         unique.append(p)

#                 added = len(unique) - before
#                 print(f"  → +{added} new  (pool: {len(unique)}/{target_count})")

#             except Exception as e:
#                 print(f"  ✗ Error fetching theme {theme_cfg}: {e}")

#     random.shuffle(unique)
#     selected = unique[:target_count]

#     print(f"\n[fetch] Total unique puzzles collected : {len(unique)}")
#     print(f"[fetch] Selected for this video        : {len(selected)}")

#     if len(selected) < target_count:
#         print(f"[fetch] ⚠  Only {len(selected)} unique puzzles available — video will be shorter.")

#     return selected


def fetch_puzzles(target_count):
    """
    Fetch puzzles using random offset strategy,
    de-duplicate by puzzle ID.
    """

    seen_ids = set()
    unique = []

    max_rounds = 3

    for round_num in range(max_rounds):
        if len(unique) >= target_count:
            break

        print(f"\n[fetch] Round {round_num + 1} — need {target_count - len(unique)}")

        for theme_cfg in PUZZLE_THEMES:
            if len(unique) >= target_count:
                break

            try:
                params = {
                    **theme_cfg,
                    "limit": 100,        # match backend cap
                    "random": "true"
                }

                url = "https://roynek.com/Chess_Sol_Puzzles/api/puzzles"
                print(f"  Fetching: {params}")

                resp = requests.get(url, params=params, timeout=30)
                data = resp.json()

                results = data.get("results", [])
                random.shuffle(results)   # 🔥 improves entropy per batch

                before = len(unique)

                for p in results:
                    pid = p.get("id")
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        unique.append(p)

                added = len(unique) - before
                print(f"  → +{added} new (pool: {len(unique)}/{target_count})")

            except Exception as e:
                print(f"  ✗ Error fetching theme {theme_cfg}: {e}")

    # Final shuffle before selection
    random.shuffle(unique)
    selected = unique[:target_count]

    print(f"\n[fetch] Total unique puzzles collected: {len(unique)}")
    print(f"[fetch] Selected for this video: {len(selected)}")

    if len(selected) < target_count:
        print(f"[fetch] ⚠ Only {len(selected)} puzzles available")

    return selected


def send_to_social_media_api(platform, link, text, media=None, area=None,
                              x_comm_id=None, fb_post_to=None):
    api_url = f"https://roynek.com/alltrenders/codes/python_API/social-media/{platform}"
    payload = {
        "link_2_post": link, "message": text, "media": media,
        "pages_ordered_ids": area, "comm_id": x_comm_id, "post_to": fb_post_to
    }
    headers = {"Content-Type": "application/json"}
    print(json.dumps(payload, ensure_ascii=False))
    try:
        r = requests.post(api_url, json=payload, headers=headers, timeout=3000)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print("Social Media Error:", e)
        return None


# ═══════════════════════════════════════════════════════════
#  DRAWING HELPERS  (standard board view — White at bottom)
# ═══════════════════════════════════════════════════════════
SQUARE_SIZE = BOARD_SIZE // 8

def square_to_pixel(square):
    """
    Return (cx, cy) pixel centre for a chess square.
    Standard view: White at bottom.
      file 0 (a) → left    file 7 (h) → right
      rank 0     → bottom  rank 7     → top
    """
    col = chess.square_file(square)       # 0=a … 7=h
    row = 7 - chess.square_rank(square)   # rank 8 → row 0 (top), rank 1 → row 7 (bottom)
    cx  = col * SQUARE_SIZE + SQUARE_SIZE // 2
    cy  = row * SQUARE_SIZE + SQUARE_SIZE // 2
    return cx, cy


def draw_arrow(draw, from_sq, to_sq, color=(255, 170, 0, 220), shaft_w=18, head_size=36):
    """Bold directional arrow from_sq → to_sq. Always standard orientation."""
    x1, y1 = square_to_pixel(from_sq)
    x2, y2 = square_to_pixel(to_sq)

    angle = math.atan2(y2 - y1, x2 - x1)
    tip_x = x2 - head_size * 0.6 * math.cos(angle)
    tip_y = y2 - head_size * 0.6 * math.sin(angle)

    dx = math.sin(angle) * shaft_w / 2
    dy = math.cos(angle) * shaft_w / 2
    shaft = [
        (x1 + dx, y1 - dy), (x1 - dx, y1 + dy),
        (tip_x - dx, tip_y + dy), (tip_x + dx, tip_y - dy),
    ]
    draw.polygon(shaft, fill=color)

    perp_x = math.sin(angle) * head_size
    perp_y = math.cos(angle) * head_size
    head = [
        (x2, y2),
        (tip_x + perp_x, tip_y - perp_y),
        (tip_x - perp_x, tip_y + perp_y),
    ]
    draw.polygon(head, fill=color)


def load_fonts():
    try:
        return (
            ImageFont.truetype(FONT_PATH, 60),   # large  (countdown)
            ImageFont.truetype(FONT_PATH, 30),   # medium (rating / side)
            ImageFont.truetype(FONT_PATH, 24),   # small  (puzzle number / message)
        )
    except Exception:
        fallback = ImageFont.load_default()
        return fallback, fallback, fallback


def create_frame_image(board, last_move=None, arrow_move=None, arrow_color=None,
                       timer=None, rating=None, side_to_move=None,
                       puzzle_num=None, total_puzzles=None, message=None):
    """
    Render one video frame.
    arrow_move  : chess.Move  — arrow shown BEFORE the move executes
    arrow_color : RGBA tuple  — gold (solver) or orange (opponent)
    timer       : int         — countdown shown centre-board
    """
    svg_data = chess.svg.board(
        board, size=BOARD_SIZE, lastmove=last_move, flipped=False
    ).encode("UTF-8")

    tmp_png = os.path.join(TEMP_DIR, "_tmp_frame.png")
    cairosvg.svg2png(bytestring=svg_data, write_to=tmp_png)

    im   = Image.open(tmp_png).convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")

    # ── Arrow overlay ──────────────────────────────────────
    if arrow_move is not None:
        col = arrow_color if arrow_color else ARROW_COLOR_SOLVER
        draw_arrow(draw, arrow_move.from_square, arrow_move.to_square, color=col)

    font_lg, font_md, font_sm = load_fonts()

    # ── Top info bar ───────────────────────────────────────
    bar_h = 95
    bar   = Image.new("RGBA", (BOARD_SIZE, bar_h), (0, 0, 0, 170))
    im.paste(bar, (0, 0), bar)
    draw  = ImageDraw.Draw(im, "RGBA")

    # Puzzle counter  (top-right)
    if puzzle_num and total_puzzles:
        puz_text = f"Puzzle {puzzle_num}/{total_puzzles}"
        pbbox    = draw.textbbox((0, 0), puz_text, font=font_sm)
        pw       = pbbox[2] - pbbox[0]
        draw.text((BOARD_SIZE - pw - 14, 10), puz_text, font=font_sm, fill="#AAAAAA")

    # Rating + side  (top-left)
    draw.text((14, 10), f"Rating: {rating}",       font=font_sm, fill="white")
    draw.text((14, 40), f"{side_to_move} to move", font=font_md, fill="#FFD700")

    # Message  (bottom bar)
    if message:
        msg_bar = Image.new("RGBA", (BOARD_SIZE, 42), (0, 0, 0, 150))
        im.paste(msg_bar, (0, BOARD_SIZE - 42), msg_bar)
        draw    = ImageDraw.Draw(im, "RGBA")
        mbbox   = draw.textbbox((0, 0), message, font=font_sm)
        mw      = mbbox[2] - mbbox[0]
        draw.text(((BOARD_SIZE - mw) // 2, BOARD_SIZE - 36),
                  message, font=font_sm, fill="lightblue")

    # ── Countdown ──────────────────────────────────────────
    if timer is not None:
        txt  = str(timer)
        bbox = draw.textbbox((0, 0), txt, font=font_lg)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        cx   = (BOARD_SIZE - w) // 2
        cy   = (BOARD_SIZE - h) // 2
        draw.text((cx + 3, cy + 3), txt, font=font_lg, fill=(0, 0, 0, 180))
        draw.text((cx,     cy),     txt, font=font_lg, fill="white")

    return im.convert("RGB")


def create_transition_frame(next_puzzle_num, total_puzzles, theme_label=""):
    """Dark transition card shown between puzzles."""
    im   = Image.new("RGBA", (BOARD_SIZE, BOARD_SIZE), (20, 20, 30, 255))
    draw = ImageDraw.Draw(im)

    font_lg, font_md, font_sm = load_fonts()

    # Decorative top accent bar
    draw.rectangle([(0, 0), (BOARD_SIZE, 8)], fill="#FFD700")
    draw.rectangle([(0, BOARD_SIZE - 8), (BOARD_SIZE, BOARD_SIZE)], fill="#FFD700")

    # "Next Puzzle" heading
    heading = "Next Puzzle"
    hbbox   = draw.textbbox((0, 0), heading, font=font_lg)
    hw      = hbbox[2] - hbbox[0]
    draw.text(((BOARD_SIZE - hw) // 2, 270), heading, font=font_lg, fill="white")

    # Puzzle number
    num_txt = f"{next_puzzle_num} / {total_puzzles}"
    nbbox   = draw.textbbox((0, 0), num_txt, font=font_md)
    nw      = nbbox[2] - nbbox[0]
    draw.text(((BOARD_SIZE - nw) // 2, 360), num_txt, font=font_md, fill="#FFD700")

    # Theme label (optional)
    if theme_label:
        tbbox = draw.textbbox((0, 0), theme_label, font=font_sm)
        tw    = tbbox[2] - tbbox[0]
        draw.text(((BOARD_SIZE - tw) // 2, 420), theme_label, font=font_sm, fill="#AAAAAA")

    # Random motivational line
    tips = [
        "Stay focused  ♟",
        "Think before you move",
        "Tactics win games  ⚡",
        "Find the best continuation",
        "A GrandMaster would nail this",
    ]
    tip   = random.choice(tips)
    tbbox = draw.textbbox((0, 0), tip, font=font_sm)
    tw    = tbbox[2] - tbbox[0]
    draw.text(((BOARD_SIZE - tw) // 2, 490), tip, font=font_sm, fill="#888888")

    return im.convert("RGB")


# ═══════════════════════════════════════════════════════════
#  FRAME GENERATION
# ═══════════════════════════════════════════════════════════
def save_puzzle_frames(board, moves, rating, side_to_move,
                       puzzle_num, total_puzzles, frame_count, message):
    """
    Generate all frames for one puzzle and append to the frame sequence.
    Returns updated frame_count.

    Arrow color rule:
      index 0, 2, 4… → opponent move → ORANGE
      index 1, 3, 5… → solver  move  → GOLD
    """
    def save(img):
        nonlocal frame_count
        img.save(os.path.join(TEMP_DIR, f"frame_{frame_count:06d}.png"))
        frame_count += 1

    def save_n(img, n):
        for _ in range(n):
            save(img)

    working = board.copy()

    common = dict(rating=rating, side_to_move=side_to_move,
                  puzzle_num=puzzle_num, total_puzzles=total_puzzles,
                  message=message)

    # 1 ── Intro hold ──────────────────────────────────────
    im = create_frame_image(working, **common)
    save_n(im, FPS * INTRO_SEC)

    # 2 ── Move loop ───────────────────────────────────────
    for i, move_uci in enumerate(moves):
        move        = chess.Move.from_uci(move_uci)
        is_solver   = (i % 2 == 1)
        arrow_color = ARROW_COLOR_SOLVER if is_solver else ARROW_COLOR_OPPONENT

        # Arrow preview
        im = create_frame_image(working, arrow_move=move,
                                arrow_color=arrow_color, **common)
        save_n(im, FPS * ARROW_SEC)

        working.push(move)

        if i == 0:
            # Opponent's first move → full countdown
            for sec in range(COUNTDOWN_SEC, 0, -1):
                im = create_frame_image(working, last_move=move,
                                        timer=sec, **common)
                save_n(im, FPS)
        else:
            # Solution moves → brief hold
            sol_common = {**common, "message": "Solution!"}
            im = create_frame_image(working, last_move=move, **sol_common)
            save_n(im, FPS * MOVE_SEC)

    # 3 ── Final pause ─────────────────────────────────────
    final_common = {**common, "message": "✓ Puzzle complete!"}
    im = create_frame_image(working, **final_common)
    save_n(im, FPS * FINAL_SEC)

    return frame_count


def save_transition_frames(next_puzzle_num, total_puzzles, frame_count, theme_label=""):
    """Render the between-puzzle transition card. Returns updated frame_count."""
    im = create_transition_frame(next_puzzle_num, total_puzzles, theme_label)
    for _ in range(FPS * BREAK_SEC):
        im.save(os.path.join(TEMP_DIR, f"frame_{frame_count:06d}.png"))
        frame_count += 1
    return frame_count


# ═══════════════════════════════════════════════════════════
#  VIDEO ENCODING
# ═══════════════════════════════════════════════════════════
def encode_video(intro_file=None):
    """
    Combine frames + intro voice (once, at start) + looped bg music + click.
    Uses -stream_loop -1 on the music so it never runs out on long videos.
    """
    video_part = f"-framerate {FPS} -i {TEMP_DIR}/frame_%06d.png"

    has_intro = intro_file is not None and os.path.exists(intro_file)
    has_music = INCLUDE_BG_MUSIC and os.path.exists(BACKGROUND_MUSIC)
    has_click = os.path.exists(CLICK_SOUND)

    inputs       = []
    filter_parts = []
    mix_labels   = []
    idx          = 1

    if has_intro:
        inputs.append(f"-i {intro_file}")
        filter_parts.append(f"[{idx}:a]volume=1.0[intro]")
        mix_labels.append("[intro]")
        idx += 1

    if has_music:
        # -stream_loop -1 keeps the music looping for the full video length
        inputs.append(f"-stream_loop -1 -i {BACKGROUND_MUSIC}")
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
        cmd = (
            f"{FFMPEG_BIN} -y {video_part} "
            f"-c:v libx264 -pix_fmt yuv420p -preset medium -crf 23 {OUTPUT_VIDEO}"
        )
    elif n_audio == 1:
        label = mix_labels[0].strip("[]")
        cmd   = (
            f"{FFMPEG_BIN} -y {video_part} {inputs_str} "
            f'-filter_complex "{filter_parts[0]}" '
            f"-map 0:v -map [{label}] "
            f"-c:v libx264 -pix_fmt yuv420p -preset medium -crf 23 -shortest {OUTPUT_VIDEO}"
        )
    else:
        mix_str = "".join(mix_labels)
        filter_parts.append(
            f"{mix_str}amix=inputs={n_audio}:duration=longest:normalize=0[aout]"
        )
        fc  = ";".join(filter_parts)
        cmd = (
            f"{FFMPEG_BIN} -y {video_part} {inputs_str} "
            f'-filter_complex "{fc}" '
            f"-map 0:v -map [aout] "
            f"-c:v libx264 -pix_fmt yuv420p -preset medium -crf 23 -shortest {OUTPUT_VIDEO}"
        )

    print("\n[ffmpeg]", cmd[:240], "...")
    subprocess.run(cmd, shell=True, check=True)



import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# ─────────────────────────────────────────────
#  YOUTUBE UPLOAD
# ─────────────────────────────────────────────
YT_CLIENT_SECRETS = "secrets/client_secrets.json"
YT_TOKEN_FILE     = "secrets/token.pickle"
YT_SCOPES         = ["https://www.googleapis.com/auth/youtube.upload"]

def get_youtube_service():
    creds = None
    if os.path.exists(YT_TOKEN_FILE):
        with open(YT_TOKEN_FILE, 'rb') as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(YT_CLIENT_SECRETS, YT_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(YT_TOKEN_FILE, 'wb') as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


def send_to_youtube(video_path, title, description, tags=None,
                    privacy="public", made_for_kids=False):
    """
    Upload a local MP4 to YouTube.

    Args:
        video_path    : path to the .mp4 file
        title         : video title (include #Shorts for Shorts)
        description   : caption / description shown on YouTube
        tags          : list of tag strings
        privacy       : "public" | "unlisted" | "private"
        made_for_kids : set True only if content is explicitly for children

    Returns:
        YouTube video ID string on success, None on failure.
    """
    if not os.path.exists(video_path):
        print(f"[youtube] ✗ File not found: {video_path}")
        return None

    try:
        youtube = get_youtube_service()

        body = {
            "snippet": {
                "title":       title[:100],        # YouTube hard limit: 100 chars
                "description": description[:5000],  # YouTube hard limit: 5000 chars
                "tags":        tags or [],
                "categoryId":  "20",               # Gaming — best category for chess
            },
            "status": {
                "privacyStatus":           privacy,
                "selfDeclaredMadeForKids": made_for_kids,
            },
        }

        media   = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        print(f"[youtube] Uploading: {video_path}")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[youtube] {int(status.progress() * 100)}% uploaded...")

        video_id = response.get("id")
        print(f"[youtube] ✅ Done — https://youtube.com/watch?v={video_id}")
        return video_id

    except Exception as e:
        print(f"[youtube] ✗ Upload failed: {e}")
        return None




# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_VIDEO), exist_ok=True)

print("=" * 60)
print("  CHESS MARATHON VIDEO GENERATOR")
print("=" * 60)

# ── 1. Intro audio (picked once for the whole video) ──────
intro_file = pick_intro_audio()

# ── 2. Fetch puzzles ──────────────────────────────────────
print(f"\n[1/3] Fetching {NUM_PUZZLES} unique puzzles...")
puzzles       = fetch_puzzles(NUM_PUZZLES)
total_puzzles = len(puzzles)

if total_puzzles == 0:
    print("✗  No puzzles fetched. Exiting.")
    exit(1)

# ── 3. Generate frames ────────────────────────────────────
print(f"\n[2/3] Generating frames for {total_puzzles} puzzles...")
frame_count = 0

for idx, puzzle_data in enumerate(puzzles, 1):
    pid = puzzle_data.get("id", "?")
    print(f"\n  Puzzle {idx}/{total_puzzles}  (ID: {pid})")

    try:
        board = chess.Board(puzzle_data["fen"])
        moves = puzzle_data["moves"]

        if isinstance(moves, str):
            moves = moves.split()

        if not moves:
            print("  ✗ No moves — skipping.")
            continue

        rating       = puzzle_data.get("rating", "N/A")
        solver_color = not board.turn
        side_to_move = "White" if solver_color == chess.WHITE else "Black"
        message      = random.choice(PUZZLE_MESSAGES)

        # Derive a short theme label from whichever config matched (best-effort)
        theme_label = puzzle_data.get("themes", "") or puzzle_data.get("q", "")
        if isinstance(theme_label, list):
            theme_label = ", ".join(theme_label[:2])

        frame_count = save_puzzle_frames(
            board, moves, rating, side_to_move,
            idx, total_puzzles, frame_count, message
        )

        # Transition card between puzzles (not after the last one)
        if idx < total_puzzles:
            frame_count = save_transition_frames(
                idx + 1, total_puzzles, frame_count, theme_label
            )

        print(f"  ✓ frames so far: {frame_count}")

    except Exception as e:
        print(f"  ✗ Error on puzzle {idx}: {e}")
        continue

# ── 4. Encode ─────────────────────────────────────────────
print(f"\n[3/3] Encoding video — {frame_count} frames...")
print("      (This may take a while for long videos)")
encode_video(intro_file=intro_file)

# ── 5. Social copy ────────────────────────────────────────
social_msg = random.choice(SOCIAL_MESSAGES).format(n=total_puzzles)
tags       = " ".join(random.sample(HASHTAGS, min(4, len(HASHTAGS))))
print(f"\n📢  Social copy: {social_msg}\n    {tags}")


tags = " ".join(random.sample(HASHTAGS, 3))
# full_message = f"{msg}\n\n{tags}\n\n@followers"
full_message = f" {social_msg} {tags} . "
safe_message = full_message.replace("\n", " ").strip()
safe_message = full_message.encode("ascii", "ignore").decode()

# puzzle_link = f"https://roynek.com/Chess_Sol_Puzzles/public/?puzzle={data['id']}"
# puzzle_link = f"https://roynek.com/Chess_Sol_Puzzles/public/"
puzzle_link = ""

video_url = f"https://roynek.com/Chess_Sol_Puzzles/auto_post/{OUTPUT_VIDEO}"

# output = send_to_social_media_api(
#     platform='facebook',
#     link=puzzle_link,
#     text=safe_message,
#     media=video_url,
#     area='6',
#     fb_post_to="reels"
# )

# print("Facebook: Social API Response:", output)

# Uncomment to auto-post:
# video_url = f"https://roynek.com/Chess_Sol_Puzzles/auto_post/{OUTPUT_VIDEO}"
# send_to_social_media_api('facebook', '', social_msg, video_url, area='6', fb_post_to='reels')



# ── YouTube ────────────────────────────────────────────────
duration_m = (frame_count / FPS) / 60
yt_title   = f"{total_puzzles} Chess Puzzles in a Row — Can You Solve Them All?"
yt_desc    = (
    f"{social_msg}\n\n"
    f"{total_puzzles} tactical puzzles back to back.\n"
    f"Drop your score in the comments — how many did you get?\n\n"
    f"Timestamps are auto-generated.\n\n"
    f"#Chess #ChessPuzzles #ChessTactics #Tactics #BrainTeaser"
)
yt_tags = ["chess", "chess puzzles", "chess tactics", "checkmate",
           "brain teaser", "chess marathon", "chesssol", "grandmaster"]

send_to_youtube(
    video_path = OUTPUT_VIDEO,
    title      = yt_title,
    description= yt_desc,
    tags       = yt_tags,
    privacy    = "public",
)


# ── 6. Cleanup ────────────────────────────────────────────
print("\nCleaning up temporary frames...")
for f in os.listdir(TEMP_DIR):
    os.remove(os.path.join(TEMP_DIR, f))
os.rmdir(TEMP_DIR)

duration_s  = frame_count / FPS
duration_m  = duration_s / 60

print("\n" + "=" * 60)
print("  DONE!")
print("=" * 60)
print(f"  Output       : {OUTPUT_VIDEO}")
print(f"  Puzzles      : {total_puzzles}")
print(f"  Total frames : {frame_count}")
print(f"  Duration     : {duration_m:.1f} min  ({duration_s:.0f} sec)")
print("=" * 60)