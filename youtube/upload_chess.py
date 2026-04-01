import os
import pickle
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION ---
VIDEO_PATH = "/var/www/html/Chess_Sol_Puzzles/youtube/chess_game.mp4"
CLIENT_SECRETS = "client_secrets.json"
TOKEN_FILE = "token.pickle"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_service():
    creds = None
    # 1. Load saved credentials if they exist
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # 2. If no valid credentials, login manually once
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 3. Save the credentials for next time
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)

    return build("youtube", "v3", credentials=creds)

def upload_video():
    youtube = get_service()

    request_body = {
        "snippet": {
            "title": "Insane Chess Puzzle! #Shorts",
            "description": "Can you solve this? #chess #puzzles #checkmate",
            "tags": ["chess", "puzzles", "gaming"],
            "categoryId": "20" # Gaming is best for Chess growth
        },
        "status": {
            "privacyStatus": "public", 
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(VIDEO_PATH, chunksize=-1, resumable=True)

    print("Initiating upload to YouTube...")
    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    print(f"Upload Complete! Video ID: {response.get('id')}")

if __name__ == "__main__":
    upload_video()