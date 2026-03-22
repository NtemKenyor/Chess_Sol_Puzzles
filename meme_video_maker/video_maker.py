import os
import random
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, clips_array

# Constants
CANVAS_W, CANVAS_H = 1080, 1920
TOP_H = CANVAS_H // 2
BOTTOM_H = CANVAS_H // 2

# Paths
# meme_dir = "/home/kenyor/Pictures/arranged_chess/memes"
video_path = "/home/kenyor/Downloads/joker.mp4"
meme_dir = "/var/www/html/Chess-Sol/meme_video_maker/downloaded_memes"
# video_path = "/var/www/html/Chess-Sol/meme_video_maker/merged_joker_trimmed.mp4"

# Load Joker video and resize
joker_clip = VideoFileClip(video_path).resized(height=BOTTOM_H, width=CANVAS_W)

# List memes
all_memes = [os.path.join(meme_dir, f) for f in os.listdir(meme_dir) if f.lower().endswith(('jpg', 'jpeg', 'png'))]
memes_selected = random.sample(all_memes, 10)

# Generate meme clips timeline
current_time = 0
duration = joker_clip.duration
meme_clips = []

while current_time < duration:
    meme_path = random.choice(memes_selected)
    meme_duration = min(random.uniform(5, 9), duration - current_time)

    meme_clip = (
        ImageClip(meme_path)
        .resized(height=TOP_H, width=CANVAS_W)
        .with_start(current_time)
        .with_duration(meme_duration)
    )

    meme_clips.append(meme_clip)
    current_time += meme_duration

# Combine meme clips into timeline
meme_timeline = CompositeVideoClip(meme_clips, size=(CANVAS_W, TOP_H)).with_duration(duration)

# Stack memes on top, joker video at bottom
final = clips_array([[meme_timeline], [joker_clip]])

# Export
final.write_videofile("joker_with_chess_memes.mp4", codec="libx264", fps=24, audio=True)
