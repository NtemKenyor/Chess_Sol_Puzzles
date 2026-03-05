import pyautogui
import json
import time

# Load the recorded actions
with open("script.json", "r") as f:
    actions = json.load(f)

print("Starting playback in 5 seconds... Switch to Chrome now!")
time.sleep(5)

last_time = 0
for action in actions:
    # Wait for the correct timing between actions
    time.sleep(action["time"] - last_time)
    last_time = action["time"]

    if action["type"] == "click":
        pyautogui.click(action["x"], action["y"])
    
    elif action["type"] == "keypress":
        if action["key"] == "Key.esc": # Don't press Esc during playback
            continue
        # Handle special keys or simple typing
        key = action["key"].replace("Key.", "")
        pyautogui.press(key)

print("Playback finished.")