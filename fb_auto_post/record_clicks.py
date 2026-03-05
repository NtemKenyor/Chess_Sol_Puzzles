import pynput
import json
import time

# List to store all events
recording = []
start_time = time.time()

def on_click(x, y, button, pressed):
    if pressed:
        recording.append({
            "type": "click",
            "x": x,
            "y": y,
            "button": str(button),
            "time": time.time() - start_time
        })

def on_press(key):
    try:
        k = key.char  # alphanumeric key
    except AttributeError:
        k = str(key)  # special key
        
    recording.append({
        "type": "keypress",
        "key": k,
        "time": time.time() - start_time
    })
    
    if key == pynput.keyboard.Key.esc:
        # Stop listener
        with open("script.json", "w") as f:
            json.dump(recording, f)
        return False

# Start listening
print("Recording... Press ESC to stop.")
with pynput.mouse.Listener(on_click=on_click) as m_listener:
    with pynput.keyboard.Listener(on_press=on_press) as k_listener:
        k_listener.join()