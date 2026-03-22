from moviepy import VideoFileClip, concatenate_videoclips

# ========================
# PARAMETERS - ADJUST HERE
# ========================
VIDEO_PATHS = [
    "/home/kenyor/Downloads/joker.mp4",  # first video
    "/home/kenyor/Downloads/joker2.mp4"  # second video
]
TRIM_FIRST_VIDEO_TO = 50  # seconds - trim first video to this duration
FINAL_DURATION = 65       # seconds - final output duration
OUTPUT_PATH = "merged_joker_trimmed.mp4"
OUTPUT_FPS = 24  # optional: set FPS

def merge_and_trim(videos, trim_first, final_duration, output_path, fps=24):
    clips = []
    
    # Load first video and trim
    first_clip = VideoFileClip(videos[0])
    if first_clip.duration > trim_first:
        first_clip = first_clip.subclipped(0, trim_first)
    clips.append(first_clip)
    
    # Load remaining videos
    for path in videos[1:]:
        clip = VideoFileClip(path)
        clips.append(clip)
    
    # Concatenate
    merged = concatenate_videoclips(clips, method="compose")
    
    # Final trim if needed
    if merged.duration > final_duration:
        merged = merged.subclipped(0, final_duration)
    
    # Export
    merged.write_videofile(output_path, codec="libx264", fps=fps, audio=True)

if __name__ == "__main__":
    merge_and_trim(VIDEO_PATHS, TRIM_FIRST_VIDEO_TO, FINAL_DURATION, OUTPUT_PATH, OUTPUT_FPS)
