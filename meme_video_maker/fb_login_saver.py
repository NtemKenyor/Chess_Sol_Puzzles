# fb_login_saver.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import json
import time

COOKIES_FILE = "fb_cookies.json"
timer_limit = 120

def save_cookies(driver, file_path):
    with open(file_path, 'w') as file:
        json.dump(driver.get_cookies(), file)
    print(f"Cookies saved to {file_path}")

def login_and_save_cookies():
    chrome_options = Options()
    # Remove headless so you can interact
    driver = webdriver.Chrome(options=chrome_options)

    print("Opening Facebook... Please log in manually.")
    driver.get("https://www.facebook.com/")
    
    # Give you time to login manually
    time.sleep(timer_limit)  # adjust as needed

    # Save cookies
    save_cookies(driver, COOKIES_FILE)

    driver.quit()

if __name__ == "__main__":
    login_and_save_cookies()
