"""
Chess Meme Video Maker — Pro Edition
=====================================
Modes:
  - "combined"    : Memes on top, Joker video on bottom
  - "memes_only"  : Full-screen meme slideshow with background music
  - "joker_only"  : Just the Joker video, resized to canvas

Server-safe approach:
  - Temp meme clips are written by piping raw frames directly to ffmpeg
    via subprocess — no MoviePy writer involved, no corrupt mp4s
  - Final assembly uses ffmpeg concat demuxer (also subprocess) for
    zero-RAM concatenation
  - MoviePy is only used for reading the joker video and its audio
"""

import os
import json
import random
import shutil
import subprocess
import numpy as np
import requests
from PIL import Image as PILImage, ImageDraw, ImageFont
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    ImageClip,
    concatenate_audioclips,
)

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────

MODE        = "combined"   # "combined" | "memes_only" | "joker_only"
CANVAS_W    = 1080
CANVAS_H    = 1920
SPLIT_RATIO = 0.5          # memes get top half, joker gets bottom half

VIDEO_PATH = "merged_joker_trimmed.mp4"
MEME_DIR   = "downloaded_memes"
MUSIC_DIR  = "bg_music"

OUTPUT_DIR    = "output_videos"
OUTPUT_NAME   = "meme_video.mp4"
TEMP_DIR      = "temp_clips"
SKIP_EXISTING = False

MEME_DURATION_MIN = 5
MEME_DURATION_MAX = 9

KEN_BURNS_ENABLED  = True
KEN_BURNS_ZOOM_MIN = 1.0
KEN_BURNS_ZOOM_MAX = 1.05   # Modest zoom — lighter on CPU

ENGAGEMENT_OVERLAY_ENABLED = True
ENGAGEMENT_TEXTS = [
    "Like if you felt this! 👍",
    "Share with your chess buddy! 🔁",
    "Tag someone who needs this! ♟️",
    "Like & share for more! 😂",
    "Double tap if you agree! ❤️",
    "Share this with a chess player! 🔥",
    "Tag your opponent! 👇",
    "Comment your reaction! 💬",
]

FPS           = 24
VIDEO_CODEC   = "libx264"
CRF           = "23"        # ffmpeg quality: lower = better, 18-28 is typical
AUDIO_BITRATE = "192k"
FFMPEG_PRESET = "fast"      # ultrafast/superfast/veryfast/fast/medium

POST_TO_SOCIAL    = True
DELETE_AFTER_POST = False
PUBLIC_BASE_URL   = "https://roynek.com/Chess_Sol_Puzzles/meme_video_maker/output_videos"
GAME_LINK         = "https://roynek.com/Chess_Sol_Puzzles/public/"
FACEBOOK_AREA_ID  = "6"
X_AREA_ID         = "21"

MESSAGES = [
    "Chess memes hitting different today! Tag a chess friend who needs this!",
    "When you finally understand the Sicilian... Drop a chess piece if you play!",
    "Chess players will relate to every single one of these!",
    "The struggle is real. Chess memes to brighten your day!",
    "Only chess players will understand the pain!",
]
HASHTAGS = [
    "#chess", "#chessmemes", "#chesshumor", "#chesstok",
    "#chessplayer", "#chesslover", "#funnyChess", "#chesscommunity",
    "#learnchess", "#chesspuzzle",
]

# ─────────────────────────────────────────────
#  UTILITIES
# ─────────────────────────────────────────────

def list_files(directory, extensions):
    if not os.path.isdir(directory):
        return []
    return sorted([
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.lower().endswith(extensions)
    ])


# def find_ffmpeg():
#     """Return path to ffmpeg binary, trying common cPanel locations."""
#     for candidate in ["ffmpeg", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg",
#                       "/opt/cpanel/ea-php81/root/usr/bin/ffmpeg"]:
#         try:
#             result = subprocess.run(
#                 [candidate, "-version"],
#                 capture_output=True, text=True
#             )
#             if result.returncode == 0:
#                 return candidate
#         except FileNotFoundError:
#             continue
#     raise RuntimeError("ffmpeg not found. Install it or check PATH.")


# FFMPEG = find_ffmpeg()
# print(f"✅ Using ffmpeg: {FFMPEG}")

# import os

FFMPEG = os.path.abspath(os.path.join(os.path.dirname(__file__), "../ffmpeg"))
print(f"✅ Using ffmpeg: {FFMPEG}")

def get_font(size):
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ─────────────────────────────────────────────
#  IMAGE PROCESSING
# ─────────────────────────────────────────────

def add_engagement_overlay(img_array, text, canvas_w, canvas_h):
    pil     = PILImage.fromarray(img_array).convert("RGBA")
    overlay = PILImage.new("RGBA", pil.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    font    = get_font(max(32, canvas_w // 24))

    bbox    = draw.textbbox((0, 0), text, font=font)
    tw, th  = bbox[2] - bbox[0], bbox[3] - bbox[1]
    padding = max(16, canvas_w // 40)
    bar_h   = th + padding * 2
    bar_y   = canvas_h - bar_h - int(canvas_h * 0.035)

    draw.rectangle([(0, bar_y), (canvas_w, bar_y + bar_h)], fill=(0, 0, 0, 175))
    tx, ty = (canvas_w - tw) // 2, bar_y + padding
    draw.text((tx + 2, ty + 2), text, font=font, fill=(0, 0, 0, 160))    # shadow
    draw.text((tx, ty),         text, font=font, fill=(255, 255, 255, 255))

    return np.array(PILImage.alpha_composite(pil, overlay).convert("RGB"))


def load_meme_as_canvas(meme_path, canvas_w, canvas_h):
    """
    Load meme, letterbox onto black canvas, add engagement overlay.
    Returns numpy array (H, W, 3) uint8.
    """
    img   = ImageClip(meme_path)
    scale = min(canvas_w / img.w, canvas_h / img.h)
    new_w = int(img.w * scale)
    new_h = int(img.h * scale)
    img   = img.resized(width=new_w, height=new_h)
    raw   = img.get_frame(0)

    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    y_off  = (canvas_h - new_h) // 2
    x_off  = (canvas_w - new_w) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = raw

    if ENGAGEMENT_OVERLAY_ENABLED:
        canvas = add_engagement_overlay(canvas, random.choice(ENGAGEMENT_TEXTS), canvas_w, canvas_h)

    return canvas


# ─────────────────────────────────────────────
#  FFMPEG-BASED CLIP WRITER
# ─────────────────────────────────────────────

def write_clip_via_ffmpeg(frames_iter, total_frames, out_path, fps, canvas_w, canvas_h):
    """
    Pipe raw RGB frames directly into ffmpeg. This is the most reliable
    way to produce valid mp4 files on restricted servers — no MoviePy
    writer involved at all.
    """
    cmd = [
        FFMPEG, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{canvas_w}x{canvas_h}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "pipe:0",
        "-vcodec", VIDEO_CODEC,
        "-pix_fmt", "yuv420p",
        "-preset", FFMPEG_PRESET,
        "-crf", CRF,
        "-movflags", "+faststart",
        out_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        for frame in frames_iter:
            proc.stdin.write(frame.astype(np.uint8).tobytes())
        proc.stdin.close()
        proc.wait()
    except Exception as e:
        proc.kill()
        raise RuntimeError(f"ffmpeg pipe failed: {e}")

    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg exited with code {proc.returncode} for {out_path}")

    # Verify output is not empty
    if not os.path.isfile(out_path) or os.path.getsize(out_path) < 10_000:
        raise RuntimeError(f"Output file missing or too small: {out_path}")


def generate_ken_burns_frames(img_array, duration, fps):
    """
    Generator that yields numpy frames for a Ken Burns zoom+pan effect.
    All PIL resizes happen one frame at a time — minimal RAM usage.
    """
    zoom_start   = random.uniform(KEN_BURNS_ZOOM_MIN, KEN_BURNS_ZOOM_MAX)
    zoom_end     = random.uniform(KEN_BURNS_ZOOM_MIN, KEN_BURNS_ZOOM_MAX)
    pan_x        = random.choice([-1, 0, 1])
    pan_y        = random.choice([-1, 0, 1])
    src_h, src_w = img_array.shape[:2]
    total_frames = int(duration * fps)

    for i in range(total_frames):
        progress = i / total_frames if total_frames > 1 else 0
        zoom     = zoom_start + (zoom_end - zoom_start) * progress
        new_w    = max(src_w, int(src_w * zoom))
        new_h    = max(src_h, int(src_h * zoom))

        pil   = PILImage.fromarray(img_array).resize((new_w, new_h), PILImage.BILINEAR)
        frame = np.array(pil)

        max_x    = new_w - src_w
        max_y    = new_h - src_h
        offset_x = int((max_x / 2) + pan_x * (max_x / 2) * progress)
        offset_y = int((max_y / 2) + pan_y * (max_y / 2) * progress)
        offset_x = max(0, min(offset_x, max_x))
        offset_y = max(0, min(offset_y, max_y))

        yield frame[offset_y:offset_y + src_h, offset_x:offset_x + src_w]


def generate_static_frames(img_array, duration, fps):
    """Generator that yields the same frame repeatedly (no Ken Burns)."""
    total_frames = int(duration * fps)
    for _ in range(total_frames):
        yield img_array


def render_meme_clip(meme_path, duration, canvas_w, canvas_h, out_path):
    """
    Full pipeline: load → letterbox → overlay → Ken Burns → ffmpeg pipe.
    Raises on failure so caller can handle/retry.
    """
    canvas       = load_meme_as_canvas(meme_path, canvas_w, canvas_h)
    total_frames = int(duration * FPS)

    if KEN_BURNS_ENABLED:
        frames = generate_ken_burns_frames(canvas, duration, FPS)
    else:
        frames = generate_static_frames(canvas, duration, FPS)

    write_clip_via_ffmpeg(frames, total_frames, out_path, FPS, canvas_w, canvas_h)
    print(f"    ✔ Written: {os.path.basename(out_path)} ({os.path.getsize(out_path) // 1024} KB)")


# ─────────────────────────────────────────────
#  MEME TIMELINE BUILDER
# ─────────────────────────────────────────────

def build_meme_timeline_ffmpeg(memes, duration, canvas_w, canvas_h):
    """
    Render each meme to a temp clip via ffmpeg pipe, then concatenate
    them all using ffmpeg's concat demuxer. Returns path to final
    silent meme mp4.
    """
    os.makedirs(TEMP_DIR, exist_ok=True)

    # Wipe leftover temp files
    for f in os.listdir(TEMP_DIR):
        if f.endswith(".mp4") or f == "concat_list.txt":
            os.remove(os.path.join(TEMP_DIR, f))

    queue = memes.copy()
    random.shuffle(queue)

    segments     = []
    current_time = 0.0
    index        = 0

    while current_time < duration:
        if not queue:
            queue = memes.copy()
            random.shuffle(queue)

        meme_path = queue.pop()
        meme_dur  = min(
            random.uniform(MEME_DURATION_MIN, MEME_DURATION_MAX),
            duration - current_time,
        )
        if meme_dur < 1.0:
            break

        out_path = os.path.join(TEMP_DIR, f"meme_{index:04d}.mp4")
        print(f"  🖼️  Clip {index + 1}: {os.path.basename(meme_path)} ({meme_dur:.1f}s)")

        try:
            render_meme_clip(meme_path, meme_dur, canvas_w, canvas_h, out_path)
            segments.append(out_path)
        except Exception as e:
            print(f"    ⚠️  Failed, retrying without Ken Burns: {e}")
            try:
                global KEN_BURNS_ENABLED
                _orig = KEN_BURNS_ENABLED
                KEN_BURNS_ENABLED = False
                render_meme_clip(meme_path, meme_dur, canvas_w, canvas_h, out_path)
                KEN_BURNS_ENABLED = _orig
                segments.append(out_path)
            except Exception as e2:
                print(f"    ❌ Skipping clip after retry failure: {e2}")

        current_time += meme_dur
        index        += 1

    if not segments:
        raise RuntimeError("No meme clips rendered successfully.")

    # Write ffmpeg concat list
    concat_list = os.path.join(TEMP_DIR, "concat_list.txt")
    with open(concat_list, "w") as f:
        for seg in segments:
            abs_path = os.path.abspath(seg)
            f.write(f"file '{abs_path}'\n")

    # Concatenate with ffmpeg (stream copy — no re-encode, instant)
    meme_concat = os.path.join(TEMP_DIR, "meme_concat.mp4")
    print(f"\n  🔗 Concatenating {len(segments)} clips with ffmpeg...")
    result = subprocess.run([
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list,
        "-c", "copy",
        meme_concat,
    ], capture_output=True, text=True)

    if result.returncode != 0 or not os.path.isfile(meme_concat):
        raise RuntimeError(f"ffmpeg concat failed:\n{result.stderr}")

    print(f"  ✅ Meme track ready: {meme_concat} ({os.path.getsize(meme_concat) // 1024} KB)")
    return meme_concat


# ─────────────────────────────────────────────
#  FINAL ASSEMBLY
# ─────────────────────────────────────────────

def stack_videos_ffmpeg(meme_path, joker_path, audio_path, out_path, top_h, bot_h):
    """
    Stack meme clip (top) and joker clip (bottom) using ffmpeg filter_complex.
    Mixes in joker audio. Pure ffmpeg — no MoviePy involved.
    """
    # Pad meme to exact top_h, joker to exact bot_h, then vstack
    filter_complex = (
        f"[0:v]scale={CANVAS_W}:{top_h},setsar=1[top];"
        f"[1:v]scale={CANVAS_W}:{bot_h},setsar=1[bot];"
        f"[top][bot]vstack=inputs=2[v]"
    )
    cmd = [
        FFMPEG, "-y",
        "-i", meme_path,
        "-i", joker_path,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "1:a",           # audio from joker
        "-vcodec", VIDEO_CODEC,
        "-pix_fmt", "yuv420p",
        "-preset", FFMPEG_PRESET,
        "-crf", CRF,
        "-acodec", "aac",
        "-b:a", AUDIO_BITRATE,
        "-movflags", "+faststart",
        "-shortest",
        out_path,
    ]
    print("\n  🎞️  Stacking meme + joker with ffmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg stack failed:\n{result.stderr[-2000:]}")


def build_memes_only_ffmpeg(meme_path, music_path, out_path):
    """
    Combine silent meme slideshow with background music track.
    """
    if music_path:
        cmd = [
            FFMPEG, "-y",
            "-i", meme_path,
            "-stream_loop", "-1", "-i", music_path,
            "-map", "0:v",
            "-map", "1:a",
            "-vcodec", "copy",
            "-acodec", "aac",
            "-b:a", AUDIO_BITRATE,
            "-shortest",
            "-movflags", "+faststart",
            out_path,
        ]
    else:
        cmd = [FFMPEG, "-y", "-i", meme_path, "-vcodec", "copy", out_path]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg memes_only failed:\n{result.stderr[-2000:]}")


def get_video_duration(path):
    """Use ffprobe to get duration in seconds."""
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ], capture_output=True, text=True)
    return float(result.stdout.strip())


def resize_video_ffmpeg(in_path, out_path, width, height):
    """Resize a video to exact dimensions with ffmpeg."""
    cmd = [
        FFMPEG, "-y", "-i", in_path,
        "-vf", f"scale={width}:{height},setsar=1",
        "-vcodec", VIDEO_CODEC,
        "-pix_fmt", "yuv420p",
        "-preset", FFMPEG_PRESET,
        "-crf", CRF,
        "-acodec", "aac",
        "-b:a", AUDIO_BITRATE,
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg resize failed:\n{result.stderr[-2000:]}")


def cleanup_temp():
    if os.path.isdir(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        print(f"  🧹 Temp clips removed: {TEMP_DIR}")


# ─────────────────────────────────────────────
#  SOCIAL MEDIA
# ─────────────────────────────────────────────

def send_to_social_media_api(platform, link, text, media=None, area=None,
                              x_comm_id=None, fb_post_to=None):
    api_url = f"https://roynek.com/alltrenders/codes/python_API/social-media/{platform}"
    payload = {
        "link_2_post":       link,
        "message":           text,
        "media":             media,
        "pages_ordered_ids": area,
        "comm_id":           x_comm_id,
        "post_to":           fb_post_to,
    }
    headers = {"Content-Type": "application/json"}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    try:
        r = requests.post(api_url, json=payload, headers=headers, timeout=3000)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"  ❌ Social Media Error ({platform}):", e)
        return None


def post_video(video_filename):
    msg       = random.choice(MESSAGES)
    tags      = " ".join(random.sample(HASHTAGS, 4))
    caption   = f"{msg} {tags}".encode("ascii", "ignore").decode().strip()
    video_url = f"{PUBLIC_BASE_URL}/{video_filename}"

    print(f"\n📢  Caption:\n{caption}")
    print(f"🔗  Video URL: {video_url}\n")

    print("📘 Posting to Facebook Reels...")
    fb = send_to_social_media_api(
        platform="facebook", link=GAME_LINK, text=caption,
        media=video_url, area=FACEBOOK_AREA_ID, fb_post_to="reels",
    )
    print("Facebook response:", fb)

    print("\n🐦 Posting to X...")
    x = send_to_social_media_api(
        platform="x", link=GAME_LINK, text=caption,
        media=video_url, area=X_AREA_ID,
    )
    print("X response:", x)


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_memes   = list_files(MEME_DIR,  ("jpg", "jpeg", "png"))
    music_files = list_files(MUSIC_DIR, ("mp3", "wav", "ogg", "m4a"))

    print(f"🖼️  {len(all_memes)} memes found.")
    print(f"🎵  {len(music_files)} music tracks found.")
    print(f"🎬  Mode: {MODE.upper()}\n")

    if not all_memes and MODE in ("combined", "memes_only"):
        print("❌ No memes found. Check MEME_DIR.")
        return

    output_path = os.path.join(OUTPUT_DIR, OUTPUT_NAME)

    if SKIP_EXISTING and os.path.isfile(output_path):
        print(f"⏭️  Skipping render — file exists: {output_path}")
    else:
        print(f"🎬 Rendering → {output_path}\n")
        try:
            if MODE == "combined":
                top_h = int(CANVAS_H * SPLIT_RATIO)
                bot_h = CANVAS_H - top_h

                if not os.path.isfile(VIDEO_PATH):
                    raise FileNotFoundError(f"Video not found: {VIDEO_PATH}")

                duration  = get_video_duration(VIDEO_PATH)
                print(f"  📹 Joker video duration: {duration:.1f}s")

                # Resize joker to bottom panel dimensions
                joker_resized = os.path.join(TEMP_DIR, "joker_resized.mp4")
                os.makedirs(TEMP_DIR, exist_ok=True)
                print(f"  📐 Resizing joker to {CANVAS_W}x{bot_h}...")
                resize_video_ffmpeg(VIDEO_PATH, joker_resized, CANVAS_W, bot_h)

                num_memes  = min(len(all_memes), max(12, int(duration / MEME_DURATION_MIN)))
                memes      = random.sample(all_memes, num_memes)
                meme_track = build_meme_timeline_ffmpeg(memes, duration, CANVAS_W, top_h)

                stack_videos_ffmpeg(meme_track, joker_resized, None, output_path, top_h, bot_h)

            elif MODE == "memes_only":
                music_path = random.choice(music_files) if music_files else None
                duration   = get_video_duration(music_path) if music_path else 60.0

                num_memes  = min(len(all_memes), max(8, int(duration / MEME_DURATION_MIN)))
                memes      = random.sample(all_memes, num_memes)
                meme_track = build_meme_timeline_ffmpeg(memes, duration, CANVAS_W, CANVAS_H)

                build_memes_only_ffmpeg(meme_track, music_path, output_path)

            elif MODE == "joker_only":
                if not os.path.isfile(VIDEO_PATH):
                    raise FileNotFoundError(f"Video not found: {VIDEO_PATH}")
                resize_video_ffmpeg(VIDEO_PATH, output_path, CANVAS_W, CANVAS_H)

            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"\n✅ Video saved: {output_path} ({size_mb:.1f} MB)")

        finally:
            cleanup_temp()

    # if POST_TO_SOCIAL:
    #     post_video(OUTPUT_NAME)
    #     if DELETE_AFTER_POST:
    #         if os.path.isfile(output_path):
    #             os.remove(output_path)
    #             print(f"  🗑️  Deleted: {output_path}")
    # else:
    #     print("\n📵 Social posting skipped (POST_TO_SOCIAL = False).")

    print("\n🏁 Done!")


if __name__ == "__main__":
    main()