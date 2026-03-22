import os
import random
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, clips_array

# Constants
CANVAS_W, CANVAS_H = 1080, 1920
TOP_H = CANVAS_H // 2
BOTTOM_H = CANVAS_H // 2
NUM_VIDEOS = 20
num_of_memes = 12


# Paths
# video_path = "/home/kenyor/Downloads/joker.mp4"
video_path = "merged_joker_trimmed.mp4"
# meme_dir = "/var/www/html/Chess-Sol/meme_video_maker/downloaded_memes"
# meme_dir = "/home/kenyor/Pictures/arranged_chess/memes"
meme_dir = "downloaded_memes"


# List memes once
all_memes = [
    os.path.join(meme_dir, f)
    for f in os.listdir(meme_dir)
    if f.lower().endswith(('jpg', 'jpeg', 'png'))
]

print(len(all_memes), "memes found in directory.")

# Load Joker video once
base_joker_clip = VideoFileClip(video_path)

for i in range(1, NUM_VIDEOS + 1):
    print(f"🎬 Creating video {i}...")

    # Resize fresh joker clip
    joker_clip = base_joker_clip.resized(height=BOTTOM_H, width=CANVAS_W)

    memes_selected = random.sample(all_memes, min(num_of_memes, len(all_memes)))

    # Generate meme clips timeline
    current_time = 0
    duration = joker_clip.duration
    meme_clips = []

    # while current_time < duration:
    #     meme_path = random.choice(memes_selected)
    #     meme_duration = min(random.uniform(5, 9), duration - current_time)

    #     meme_image = ImageClip(meme_path)

    #     # Compute scale factor to fit within CANVAS_W x TOP_H while preserving aspect ratio
    #     scale_w = CANVAS_W / meme_image.w
    #     scale_h = TOP_H / meme_image.h
    #     scale = min(scale_w, scale_h)

    #     # Resize both width and height proportionally
    #     meme_image = meme_image.resized(height=meme_image.h * scale, width=meme_image.w * scale)

    #     # Place resized meme in black canvas (letterbox/pillarbox effect)
    #     meme_clip = (
    #         CompositeVideoClip(
    #             [meme_image.with_position("center")],
    #             size=(CANVAS_W, TOP_H),
    #             bg_color=(0, 0, 0)
    #         )
    #         .with_start(current_time)
    #         .with_duration(meme_duration)
    #     )

    #     meme_clips.append(meme_clip)
    #     current_time += meme_duration

    # Shuffle selected memes for this video
    memes_queue = memes_selected.copy()
    random.shuffle(memes_queue)

    while current_time < duration:
        if not memes_queue:
            # Re-shuffle if all memes used
            memes_queue = memes_selected.copy()
            random.shuffle(memes_queue)

        meme_path = memes_queue.pop()

        meme_duration = min(random.uniform(5, 9), duration - current_time)

        meme_image = ImageClip(meme_path)

        # Compute scale factor to fit within CANVAS_W x TOP_H while preserving aspect ratio
        scale_w = CANVAS_W / meme_image.w
        scale_h = TOP_H / meme_image.h
        scale = min(scale_w, scale_h)

        # Resize both width and height proportionally
        meme_image = meme_image.resized(height=meme_image.h * scale, width=meme_image.w * scale)

        # Place resized meme in black canvas (letterbox/pillarbox effect)
        meme_clip = (
            CompositeVideoClip(
                [meme_image.with_position("center")],
                size=(CANVAS_W, TOP_H),
                bg_color=(0, 0, 0)
            )
            .with_start(current_time)
            .with_duration(meme_duration)
        )

        meme_clips.append(meme_clip)
        current_time += meme_duration


    # Create meme timeline
    meme_timeline = CompositeVideoClip(meme_clips, size=(CANVAS_W, TOP_H)).with_duration(duration)

    # Stack memes on top, joker at bottom
    final = clips_array([[meme_timeline], [joker_clip]])

    # Export
    output_filename = f"joker_with_chess_memes_{i}.mp4"
    final.write_videofile(output_filename, codec="libx264", fps=24, audio=True)

print("✅ All videos created successfully!")
