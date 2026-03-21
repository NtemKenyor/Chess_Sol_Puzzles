import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.pgnmentor.com/files.html"
ROOT = "https://www.pgnmentor.com/"
OUTPUT_DIR = "pgn_players"
MAX_WORKERS = 4
TIMEOUT = 20

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0"
})

# import os
import time
import random


MIN_VALID_SIZE = 10 * 1024  # 10KB safety threshold



def fetch_page():
    r = session.get(BASE_URL, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def is_player_row(tr):
    tds = tr.find_all("td")
    if len(tds) < 2:
        return False

    text = tds[1].get_text(strip=True)

    # Key pattern: "Name, 1234 games"
    return ("," in text) and ("games" in text.lower())


def extract_player_links(html):
    soup = BeautifulSoup(html, "lxml")
    links = set()

    for tr in soup.find_all("tr"):
        if not is_player_row(tr):
            continue

        a = tr.find("a", href=True)
        if not a:
            continue

        href = a["href"]

        # strict: only players directory
        if not href.startswith("players/") or not href.endswith(".zip"):
            continue

        full_url = urljoin(ROOT, href)
        links.add(full_url)

    return sorted(links)

""" 
def download(url):
    filename = os.path.join(OUTPUT_DIR, url.split("/")[-1])

    if os.path.exists(filename):
        return f"[SKIP] {filename}"

    try:
        with session.get(url, stream=True, timeout=TIMEOUT) as r:
            r.raise_for_status()
            with open(filename, "wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)

        return f"[OK] {filename}"

    except Exception as e:
        return f"[ERR] {url} -> {e}"
 """


def polite_delay(min_delay=0.5, max_delay=2.0):
    """
    Adds a small random delay between requests to avoid
    overwhelming the server and reduce timeouts.
    """
    time.sleep(random.uniform(min_delay, max_delay))

def download(url):
    filename = os.path.join(OUTPUT_DIR, url.split("/")[-1])
    temp_file = filename + ".part"

    try:
        # ---- check if already complete ----
        if os.path.exists(filename):
            if os.path.getsize(filename) > MIN_VALID_SIZE:
                return f"[SKIP] {filename}"
            else:
                # corrupted or too small → delete
                os.remove(filename)

        headers = {}
        mode = "wb"

        # ---- resume support ----
        if os.path.exists(temp_file):
            existing_size = os.path.getsize(temp_file)
            headers["Range"] = f"bytes={existing_size}-"
            mode = "ab"
        else:
            existing_size = 0

        polite_delay()

        with session.get(url, headers=headers, stream=True, timeout=TIMEOUT) as r:
            if r.status_code not in (200, 206):
                raise Exception(f"Bad status: {r.status_code}")

            with open(temp_file, mode) as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)

        # ---- finalize ----
        os.rename(temp_file, filename)

        return f"[OK] {filename}"

    except Exception as e:
        return f"[ERR] {url} -> {e}"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    html = fetch_page()
    links = extract_player_links(html)

    print(f"Players found: {len(links)}")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(download, url) for url in links]

        for f in as_completed(futures):
            print(f.result())


if __name__ == "__main__":
    main()