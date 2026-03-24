"""
Chess Meme Video Maker — Pro Edition
=====================================
Modes:
  - "combined"    : Memes on top, Joker video on bottom (original style)
  - "memes_only"  : Full-screen meme slideshow with background music
  - "joker_only"  : Just the Joker video, resized to canvas

Features:
  - No duplicate memes within a single video
  - Ken Burns pan/zoom effect on memes (fixed for moviepy compatibility)
  - Background music support (memes_only mode)
  - Configurable split ratio, canvas size, durations
  - Auto-skip already exported videos (crash-safe batch)
  - Social media posting to Facebook and X after export
"""

import os
import json
import random
import numpy as np
import requests
from PIL import Image as PILImage
from moviepy import (
    VideoFileClip,
    ImageClip,
    VideoClip,
    CompositeVideoClip,
    clips_array,
    AudioFileClip,
    concatenate_audioclips,
)

# ─────────────────────────────────────────────
#  CONFIG — Edit everything here
# ─────────────────────────────────────────────

MODE = "combined"  # "combined" | "memes_only" | "joker_only"

# Canvas dimensions (portrait 9:16 by default)
CANVAS_W = 1080
CANVAS_H = 1920

# Split ratio for "combined" mode (0.5 = 50/50, 0.4 = memes get 40%)
SPLIT_RATIO = 0.5

# Paths
VIDEO_PATH    = "merged_joker_trimmed.mp4"
MEME_DIR      = "downloaded_memes"
MUSIC_DIR     = "bg_music"   # Used in memes_only mode

# Output
OUTPUT_DIR    = "output_videos"
OUTPUT_NAME   = "meme_video.mp4"  # Single output filename (used for social URL too)
SKIP_EXISTING = True              # Skip render if file already exists

# Meme display duration range (seconds)
MEME_DURATION_MIN = 5
MEME_DURATION_MAX = 9

# Ken Burns effect: subtle zoom/pan on memes
KEN_BURNS_ENABLED  = True
KEN_BURNS_ZOOM_MIN = 1.0    # Start zoom (1.0 = no zoom)
KEN_BURNS_ZOOM_MAX = 1.08   # Max zoom reached by end of clip

# Video export settings
FPS           = 24
VIDEO_CODEC   = "libx264"
AUDIO_BITRATE = "192k"

# ── Social Media ────────────────────────────────
POST_TO_SOCIAL   = True   # Set False to skip social posting
PUBLIC_BASE_URL  = "https://roynek.com/Chess_Sol_Puzzles/auto_post_legends"
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
    """Return sorted full paths of files with given extensions."""
    if not os.path.isdir(directory):
        return []
    return sorted([
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.lower().endswith(extensions)
    ])


def apply_ken_burns(img_array, duration):
    """
    Given a numpy image array, returns a VideoClip with a Ken Burns
    zoom+pan effect over `duration` seconds.

    Uses VideoClip(make_frame) — the correct moviepy approach for
    frame-by-frame manipulation, avoiding .transform() API issues.
    """
    zoom_start = random.uniform(KEN_BURNS_ZOOM_MIN, KEN_BURNS_ZOOM_MAX)
    zoom_end   = random.uniform(KEN_BURNS_ZOOM_MIN, KEN_BURNS_ZOOM_MAX)
    pan_x      = random.choice([-1, 0, 1])
    pan_y      = random.choice([-1, 0, 1])

    src_h, src_w = img_array.shape[:2]

    def make_frame(t):
        progress = t / duration if duration > 0 else 0
        zoom     = zoom_start + (zoom_end - zoom_start) * progress

        new_w = int(src_w * zoom)
        new_h = int(src_h * zoom)

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


def make_meme_clip(meme_path, start_time, duration, canvas_w, canvas_h):
    """
    Load a meme image, fit it into canvas_w x canvas_h (letterboxed),
    optionally apply Ken Burns, and return a timed clip.
    """
    img = ImageClip(meme_path)

    # Fit inside canvas preserving aspect ratio
    scale  = min(canvas_w / img.w, canvas_h / img.h)
    new_w  = int(img.w * scale)
    new_h  = int(img.h * scale)
    img    = img.resized(width=new_w, height=new_h)

    if KEN_BURNS_ENABLED:
        raw_frame  = img.get_frame(0)
        inner_clip = apply_ken_burns(raw_frame, duration)
    else:
        inner_clip = img

    clip = (
        CompositeVideoClip(
            [inner_clip.with_position("center")],
            size=(canvas_w, canvas_h),
            bg_color=(0, 0, 0),
        )
        .with_start(start_time)
        .with_duration(duration)
    )
    return clip


def build_meme_timeline(memes, duration, canvas_w, canvas_h):
    """
    Build a full meme slideshow covering `duration` seconds.
    Memes play in shuffled order with no back-to-back repeats.
    """
    queue        = memes.copy()
    random.shuffle(queue)
    clips        = []
    current_time = 0.0

    while current_time < duration:
        if not queue:
            queue = memes.copy()
            random.shuffle(queue)

        meme_path = queue.pop()
        meme_dur  = min(
            random.uniform(MEME_DURATION_MIN, MEME_DURATION_MAX),
            duration - current_time,
        )

        clip = make_meme_clip(meme_path, current_time, meme_dur, canvas_w, canvas_h)
        clips.append(clip)
        current_time += meme_dur

    return CompositeVideoClip(clips, size=(canvas_w, canvas_h)).with_duration(duration)


def build_background_music(music_files, duration):
    """
    Shuffle and concatenate music tracks to fill `duration` seconds.
    Returns an audio clip or None if no music is available.
    """
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
    """Build caption and post the exported video to Facebook and X."""
    msg     = random.choice(MESSAGES)
    tags    = " ".join(random.sample(HASHTAGS, 4))
    caption = f"{msg} {tags}".encode("ascii", "ignore").decode().strip()

    video_url = f"{PUBLIC_BASE_URL}/{video_filename}"
    print(f"\n📢  Caption:\n{caption}")
    print(f"🔗  Video URL: {video_url}\n")

    print("📘 Posting to Facebook...")
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

        if MODE == "combined":
            top_h    = int(CANVAS_H * SPLIT_RATIO)
            bot_h    = CANVAS_H - top_h
            joker    = base_joker.resized(width=CANVAS_W, height=bot_h)
            duration = joker.duration

            num_memes     = min(len(all_memes), max(12, int(duration / MEME_DURATION_MIN)))
            memes         = random.sample(all_memes, num_memes)
            meme_timeline = build_meme_timeline(memes, duration, CANVAS_W, top_h)
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
            meme_timeline = build_meme_timeline(memes, duration, CANVAS_W, CANVAS_H)

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

        print(f"\n✅ Video saved: {output_path}")

    # Post to social media
    if POST_TO_SOCIAL:
        post_video(OUTPUT_NAME)
    else:
        print("\n📵 Social posting skipped (POST_TO_SOCIAL = False).")

    print("\n🏁 Done!")


if __name__ == "__main__":
    main()