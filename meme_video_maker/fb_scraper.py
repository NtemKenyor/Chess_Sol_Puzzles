# fb_scraper.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import json
import time
import os
import urllib.request

FB_PAGE_URL = "https://web.facebook.com/ChessMemes2371/photos_by"
COOKIES_FILE = "fb_cookies.json"
OUTPUT_DIR = "downloaded_memes"
NUM_IMAGES = 200
SCROLL_PAUSE = 6

def setup_driver():
    chrome_options = Options()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def load_cookies(driver, file_path):
    driver.get("https://www.facebook.com/")
    with open(file_path, 'r') as file:
        cookies = json.load(file)
        for cookie in cookies:
            # Adjust if domain mismatch
            if 'sameSite' in cookie:
                del cookie['sameSite']
            driver.add_cookie(cookie)
    print("Cookies loaded.")

def download_image(url, save_path):
    try:
        urllib.request.urlretrieve(url, save_path)
        print(f"Downloaded {save_path}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")

def scrape_images():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    driver = setup_driver()

    # Load cookies
    load_cookies(driver, COOKIES_FILE)

    # Now go to page
    driver.get(FB_PAGE_URL)
    time.sleep(3)

    image_urls = set()

    while len(image_urls) < NUM_IMAGES:
        images = driver.find_elements("tag name", "img")
        for img in images:
            src = img.get_attribute("src")
            if src and "scontent" in src:
                image_urls.add(src)
                if len(image_urls) >= NUM_IMAGES:
                    break
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)

    driver.quit()

    for i, url in enumerate(image_urls):
        file_path = os.path.join(OUTPUT_DIR, f"meme_{i+1}.jpg")
        download_image(url, file_path)

if __name__ == "__main__":
    scrape_images()
