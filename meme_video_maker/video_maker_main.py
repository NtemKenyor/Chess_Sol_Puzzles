"""
Chess Meme Video Maker — Pro Edition
=====================================
Modes:
  - "combined"    : Memes on top, Joker video on bottom
  - "memes_only"  : Full-screen meme slideshow with background music
  - "joker_only"  : Just the Joker video, resized to canvas

Memory-safe for low-RAM servers:
  - Each meme clip is pre-rendered to a temp file on disk
  - Final assembly reads from disk, not RAM
  - Temp files are cleaned up automatically
"""

import os
import json
import random
import shutil
import tempfile
import subprocess
import numpy as np
import requests
from PIL import Image as PILImage, ImageDraw, ImageFont
from moviepy import (
    VideoFileClip,
    ImageClip,
    VideoClip,
    CompositeVideoClip,
    clips_array,
    AudioFileClip,
    concatenate_audioclips,
    concatenate_videoclips,
)

# ─────────────────────────────────────────────
#  CONFIG — Edit everything here
# ─────────────────────────────────────────────

MODE = "combined"  # "combined" | "memes_only" | "joker_only"

CANVAS_W    = 1080
CANVAS_H    = 1920
SPLIT_RATIO = 0.5   # 0.5 = 50/50 top/bottom in combined mode

VIDEO_PATH = "merged_joker_trimmed.mp4"
MEME_DIR   = "downloaded_memes"
MUSIC_DIR  = "bg_music"

OUTPUT_DIR    = "output_videos"
OUTPUT_NAME   = "meme_video.mp4"
SKIP_EXISTING = False   # Set True to skip render if file already exists

MEME_DURATION_MIN = 5
MEME_DURATION_MAX = 9

KEN_BURNS_ENABLED  = True
KEN_BURNS_ZOOM_MIN = 1.0
KEN_BURNS_ZOOM_MAX = 1.06   # Kept low to reduce per-frame work

# Engagement overlay — shown on meme panel
ENGAGEMENT_OVERLAY_ENABLED = True
ENGAGEMENT_TEXTS = [
    "👍 Like if you felt this!",
    "🔁 Share with your chess buddy!",
    "♟️ Tag someone who needs this!",
    "😂 Like & share for more!",
    "❤️ Double tap if you agree!",
    "🔥 Share this with a chess player!",
    "👇 Tag your opponent!",
    "💬 Comment your reaction!",
]

FPS           = 24
VIDEO_CODEC   = "libx264"
AUDIO_BITRATE = "192k"

# ── Social Media ────────────────────────────────
POST_TO_SOCIAL   = True
PUBLIC_BASE_URL  = "https://roynek.com/Chess_Sol_Puzzles/meme_video_maker/output_videos"
GAME_LINK        = "https://roynek.com/Chess_Sol_Puzzles/public/"
FACEBOOK_AREA_ID = "6"
X_AREA_ID        = "21"

MESSAGES = [
    "😂 Chess memes hitting different today! Tag a chess friend who needs this!",
    "♟️ When you finally understand the Sicilian... 😅 Drop a ♟️ if you play chess!",
    "😂 Chess players will relate to every single one of these!",
    "♟️ The struggle is real. Chess memes to brighten your day!",
    "😂 Only chess players will understand the pain 😭♟️",
]

HASHTAGS = [
    "#chess", "#chessmemes", "#chesshumor", "#chesstok",
    "#chessplayer", "#chesslover", "#funnyChess", "#chesscommunity",
    "#learnchess", "#chesspuzzle",
]

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def list_files(directory, extensions):
    if not os.path.isdir(directory):
        return []
    return sorted([
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.lower().endswith(extensions)
    ])


def add_engagement_overlay(img_array, text, canvas_w, canvas_h):
    """
    Burn an engagement text label onto the bottom of a numpy image array.
    Uses a semi-transparent dark pill/bar so it's readable on any meme.
    """
    pil = PILImage.fromarray(img_array).convert("RGBA")

    # Draw layer
    overlay = PILImage.new("RGBA", pil.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    # Try to load a bold font, fall back gracefully
    font_size = max(28, canvas_w // 28)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    # Measure text
    bbox    = draw.textbbox((0, 0), text, font=font)
    tw, th  = bbox[2] - bbox[0], bbox[3] - bbox[1]
    padding = font_size // 2
    bar_h   = th + padding * 2
    bar_y   = canvas_h - bar_h - int(canvas_h * 0.04)  # 4% from bottom

    # Semi-transparent dark background bar
    draw.rectangle(
        [(0, bar_y), (canvas_w, bar_y + bar_h)],
        fill=(0, 0, 0, 170)
    )

    # Centered white text
    tx = (canvas_w - tw) // 2
    ty = bar_y + padding
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, 255))

    # Merge back
    combined = PILImage.alpha_composite(pil, overlay).convert("RGB")
    return np.array(combined)


def apply_ken_burns(img_array, duration):
    """
    Returns a VideoClip with Ken Burns zoom+pan over `duration` seconds.
    Built with VideoClip(make_frame) to avoid .transform() memory issues.
    """
    zoom_start = random.uniform(KEN_BURNS_ZOOM_MIN, KEN_BURNS_ZOOM_MAX)
    zoom_end   = random.uniform(KEN_BURNS_ZOOM_MIN, KEN_BURNS_ZOOM_MAX)
    pan_x      = random.choice([-1, 0, 1])
    pan_y      = random.choice([-1, 0, 1])
    src_h, src_w = img_array.shape[:2]

    def make_frame(t):
        progress = t / duration if duration > 0 else 0
        zoom     = zoom_start + (zoom_end - zoom_start) * progress
        new_w    = int(src_w * zoom)
        new_h    = int(src_h * zoom)

        pil   = PILImage.fromarray(img_array).resize((new_w, new_h), PILImage.LANCZOS)
        frame = np.array(pil)

        max_x    = max(new_w - src_w, 0)
        max_y    = max(new_h - src_h, 0)
        offset_x = int((max_x / 2) + pan_x * (max_x / 2) * progress)
        offset_y = int((max_y / 2) + pan_y * (max_y / 2) * progress)
        offset_x = max(0, min(offset_x, max_x))
        offset_y = max(0, min(offset_y, max_y))

        return frame[offset_y:offset_y + src_h, offset_x:offset_x + src_w]

    return VideoClip(make_frame, duration=duration)


# def render_single_meme_to_file(meme_path, duration, canvas_w, canvas_h, tmp_dir, index):
#     """
#     Render one meme clip (with Ken Burns + optional overlay) to a temp .mp4 file.
#     This is the key memory fix: each clip is written to disk independently,
#     so RAM usage stays flat regardless of total video length.
#     """
#     img = ImageClip(meme_path)

#     # Fit inside canvas preserving aspect ratio
#     scale = min(canvas_w / img.w, canvas_h / img.h)
#     new_w = int(img.w * scale)
#     new_h = int(img.h * scale)
#     img   = img.resized(width=new_w, height=new_h)
#     raw   = img.get_frame(0)

#     # Letterbox onto black canvas
#     canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
#     y_off  = (canvas_h - new_h) // 2
#     x_off  = (canvas_w - new_w) // 2
#     canvas[y_off:y_off + new_h, x_off:x_off + new_w] = raw
#     framed = canvas

#     # Engagement overlay
#     if ENGAGEMENT_OVERLAY_ENABLED:
#         text   = random.choice(ENGAGEMENT_TEXTS)
#         framed = add_engagement_overlay(framed, text, canvas_w, canvas_h)

#     if KEN_BURNS_ENABLED:
#         clip = apply_ken_burns(framed, duration)
#     else:
#         clip = ImageClip(framed).with_duration(duration)

#     tmp_path = os.path.join(tmp_dir, f"meme_{index:04d}.mp4")
#     clip.write_videofile(
#         tmp_path,
#         codec=VIDEO_CODEC,
#         fps=FPS,
#         audio=False,
#         logger=None,   # Suppress per-clip noise
#     )
#     return tmp_path

def render_single_meme_to_file(meme_path, duration, canvas_w, canvas_h, tmp_dir, index):
    img = ImageClip(meme_path)

    # 1. Fit inside canvas preserving aspect ratio
    scale = min(canvas_w / img.w, canvas_h / img.h)
    new_w = int(img.w * scale)
    new_h = int(img.h * scale)
    img   = img.resized(width=new_w, height=new_h)
    raw   = img.get_frame(0)

    # 2. Letterbox onto black canvas
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    
    # CALCULATE OFFSETS SAFELY
    y_off  = (canvas_h - raw.shape[0]) // 2
    x_off  = (canvas_w - raw.shape[1]) // 2
    
    # 3. Use the actual shape of 'raw' to avoid broadcast errors
    canvas[y_off:y_off + raw.shape[0], x_off:x_off + raw.shape[1]] = raw
    
    # 4. FINAL SAFETY CHECK: Force the framed image to the exact canvas size
    # This prevents the 1078 vs 1080 error
    framed = np.array(PILImage.fromarray(canvas).resize((canvas_w, canvas_h)))

    # Engagement overlay
    if ENGAGEMENT_OVERLAY_ENABLED:
        text   = random.choice(ENGAGEMENT_TEXTS)
        framed = add_engagement_overlay(framed, text, canvas_w, canvas_h)

    if KEN_BURNS_ENABLED:
        clip = apply_ken_burns(framed, duration)
    else:
        clip = ImageClip(framed).with_duration(duration)

    tmp_path = os.path.join(tmp_dir, f"meme_{index:04d}.mp4")
    clip.write_videofile(
        tmp_path,
        codec=VIDEO_CODEC,
        fps=FPS,
        audio=False,
        logger=None,
    )
    return tmp_path

def build_meme_timeline_disk(memes, duration, canvas_w, canvas_h):
    """
    Build a meme slideshow by rendering each clip to disk first,
    then concatenating. Keeps RAM usage low on constrained servers.
    Returns a VideoClip ready to composite.
    """
    tmp_dir = tempfile.mkdtemp(prefix="chess_memes_")
    print(f"  🗂️  Temp dir: {tmp_dir}")

    queue = memes.copy()
    random.shuffle(queue)

    segments     = []   # (tmp_file_path, duration)
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

        print(f"  🖼️  Clip {index + 1}: {os.path.basename(meme_path)} ({meme_dur:.1f}s)")
        tmp_path = render_single_meme_to_file(
            meme_path, meme_dur, canvas_w, canvas_h, tmp_dir, index
        )
        segments.append(tmp_path)
        current_time += meme_dur
        index        += 1

    # Concatenate all rendered clips
    print(f"\n  🔗 Concatenating {len(segments)} meme clips...")
    clips    = [VideoFileClip(p) for p in segments]
    timeline = concatenate_videoclips(clips)

    # Store tmp_dir reference so we can clean up after export
    timeline._chess_tmp_dir = tmp_dir
    timeline._chess_tmp_clips = clips
    return timeline


def cleanup_timeline(timeline):
    """Close clips and remove temp dir after export."""
    for c in getattr(timeline, "_chess_tmp_clips", []):
        try:
            c.close()
        except Exception:
            pass
    tmp_dir = getattr(timeline, "_chess_tmp_dir", None)
    if tmp_dir and os.path.isdir(tmp_dir):
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"  🧹 Cleaned up temp dir: {tmp_dir}")


def build_background_music(music_files, duration):
    if not music_files:
        print("  ⚠️  No music files found. Exporting without audio.")
        return None

    audio_clips = []
    total       = 0.0
    shuffled    = music_files.copy()
    random.shuffle(shuffled)
    idx = 0

    while total < duration:
        track     = AudioFileClip(shuffled[idx % len(shuffled)])
        idx      += 1
        remaining = duration - total
        if track.duration > remaining:
            track = track.subclipped(0, remaining)
        audio_clips.append(track)
        total += track.duration

    return concatenate_audioclips(audio_clips)


def cleanup_output():
    """Delete the exported video from OUTPUT_DIR after posting."""
    target = os.path.join(OUTPUT_DIR, OUTPUT_NAME)
    if os.path.isfile(target):
        os.remove(target)
        print(f"  🗑️  Deleted output video: {target}")


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
    msg     = random.choice(MESSAGES)
    tags    = " ".join(random.sample(HASHTAGS, 4))
    caption = f"{msg} {tags}".encode("ascii", "ignore").decode().strip()

    video_url = f"{PUBLIC_BASE_URL}/{video_filename}"
    print(f"\n📢  Caption:\n{caption}")
    print(f"🔗  Video URL: {video_url}\n")

    print("📘 Posting to Facebook Reels...")
    fb_resp = send_to_social_media_api(
        platform="facebook",
        link=GAME_LINK,
        text=caption,
        media=video_url,
        area=FACEBOOK_AREA_ID,
        fb_post_to="reels",
    )
    print("Facebook response:", fb_resp)

    print("\n🐦 Posting to X...")
    x_resp = send_to_social_media_api(
        platform="x",
        link=GAME_LINK,
        text=caption,
        media=video_url,
        area=X_AREA_ID,
    )
    print("X response:", x_resp)


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

    base_joker = None
    if MODE in ("combined", "joker_only"):
        if not os.path.isfile(VIDEO_PATH):
            print(f"❌ Video not found: {VIDEO_PATH}")
            return
        print("📂 Loading base video...")
        base_joker = VideoFileClip(VIDEO_PATH)

    output_path = os.path.join(OUTPUT_DIR, OUTPUT_NAME)

    if SKIP_EXISTING and os.path.isfile(output_path):
        print(f"⏭️  Video already exists: {output_path}. Skipping render.")
    else:
        print(f"🎬 Rendering → {output_path}\n")
        meme_timeline = None

        try:
            if MODE == "combined":
                top_h    = int(CANVAS_H * SPLIT_RATIO)
                bot_h    = CANVAS_H - top_h
                joker    = base_joker.resized(width=CANVAS_W, height=bot_h)
                duration = joker.duration

                num_memes     = min(len(all_memes), max(12, int(duration / MEME_DURATION_MIN)))
                memes         = random.sample(all_memes, num_memes)
                meme_timeline = build_meme_timeline_disk(memes, duration, CANVAS_W, top_h)
                final         = clips_array([[meme_timeline], [joker]])
                final.write_videofile(
                    output_path, codec=VIDEO_CODEC, fps=FPS,
                    audio=True, audio_bitrate=AUDIO_BITRATE,
                )

            elif MODE == "memes_only":
                if music_files:
                    probe    = AudioFileClip(random.choice(music_files))
                    duration = probe.duration
                    probe.close()
                else:
                    duration = 60.0

                num_memes     = min(len(all_memes), max(8, int(duration / MEME_DURATION_MIN)))
                memes         = random.sample(all_memes, num_memes)
                meme_timeline = build_meme_timeline_disk(memes, duration, CANVAS_W, CANVAS_H)

                music = build_background_music(music_files, duration)
                if music:
                    meme_timeline = meme_timeline.with_audio(music)

                meme_timeline.write_videofile(
                    output_path, codec=VIDEO_CODEC, fps=FPS,
                    audio=bool(music), audio_bitrate=AUDIO_BITRATE,
                )

            elif MODE == "joker_only":
                joker = base_joker.resized(width=CANVAS_W, height=CANVAS_H)
                joker.write_videofile(
                    output_path, codec=VIDEO_CODEC, fps=FPS,
                    audio=True, audio_bitrate=AUDIO_BITRATE,
                )

        finally:
            # Always clean up temp clips, even if export fails
            if meme_timeline is not None:
                cleanup_timeline(meme_timeline)

        print(f"\n✅ Video saved: {output_path}")

    # ── Post to social media ────────────────────────────────
    # if POST_TO_SOCIAL:
    #     post_video(OUTPUT_NAME)
    #     # Uncomment to delete video from server after posting:
    #     # cleanup_output()
    # else:
    #     print("\n📵 Social posting skipped (POST_TO_SOCIAL = False).")

    print("\n🏁 Done!")


if __name__ == "__main__":
    main()