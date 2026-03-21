import os
import time
import random
from urllib.parse import quote_plus
from io import BytesIO

import requests
from bs4 import BeautifulSoup
from PIL import Image

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from multiprocessing import Pool, cpu_count


# ================= CONFIG =================
SAVE_PATH = "chess_legends_faces"
IMAGES_PER_PLAYER = 3

# Limit workers (important: Chrome is heavy)
NUMBER_OF_WORKERS = 2
MAX_WORKERS = min(NUMBER_OF_WORKERS, cpu_count())


# ================= PLAYERS =================
# players = [
#     "Magnus Carlsen", "Garry Kasparov", "Bobby Fischer",
#     "Viswanathan Anand", "Vladimir Kramnik", "Hikaru Nakamura",
#     "Fabiano Caruana", "Ding Liren", "Ian Nepomniachtchi",
#     "Levon Aronian", "Anish Giri", "Wesley So",
#     "Alireza Firouzja", "Judit Polgar", "Hou Yifan",
#     "Paul Morphy", "Mikhail Tal", "Tigran Petrosian",
#     "Boris Spassky", "Anatoly Karpov"
# ]
players = [
    "Nodirbek Abdusattorov",
    "Michael Adams",
    "Varuzhan Akobian",
    "Vladimir Akopian",
    "Lev Alburt",
    "Alexander Alekhine",
    "Evgeny Alekseev",
    "Zoltan Almasi",
    "Viswanathan Anand",
    "Adolf Anderssen",
    "Ulf Andersson",
    "Dmitry Andreikin",
    "Levon Aronian",
    "Maurice Ashley",
    "Yuri Averbakh",
    "Zurab Azmaiparashvili",
    "Etienne Bacrot",
    "Evgeny Bareev",
    "Julio Becerra Rivero",
    "Alexander Beliavsky",
    "Joel Benjamin",
    "Pal Benko",
    "Hans Berliner",
    "Ossip Bernstein",
    "Henry Bird",
    "Arthur Bisguier",
    "Joseph Blackburne",
    "Pavel Blatny",
    "Efim Bogoljubow",
    "Isaac Boleslavsky",
    "Viktor Bologan",
    "Mikhail Botvinnik",
    "Gyula Breyer",
    "David Bronstein",
    "Walter Browne",
    "Lazaro Bruzon",
    "Bu Xiangzhi",
    "Robert Byrne",
    "Jose Raul Capablanca",
    "Magnus Carlsen",
    "Fabiano Caruana",
    "Maia Chiburdanidze",
    "Mikhail Chigorin",
    "Larry Christiansen",
    "Nick DeFirmian",
    "Louis de La Bourdonnais",
    "Arnold Denker",
    "Ding Liren",
    "Leinier Dominguez Perez",
    "Alexey Dreev",
    "Jan Krzysztof Duda",
    "Roman Dzindzichashvili",
    "Jaan Ehlvest",
    "Pavel Eljanov",
    "Arjun Erigaisi",
    "Max Euwe",
    "Larry Evans",
    "John Fedorowicz",
    "Reuben Fine",
    "Benjamin Finegold",
    "Alireza Firouzja",
    "Robert James Fischer",
    "Alexander Fishbein",
    "Salo Flohr",
    "Nona Gaprindashvili",
    "Vugar Gashimov",
    "Boris Gelfand",
    "Efim Geller",
    "Kiril Georgiev",
    "Anish Giri",
    "Svetozar Gligoric",
    "Alexander Goldin",
    "Julio Granda Zuniga",
    "Alexander Grischuk",
    "Dommaraju Gukesh",
    "Boris Gulko",
    "Isidor Gunsberg",
    "Dmitry Gurevich",
    "Mikhail Gurevich",
    "Pentala Harikrishna",
    "Vlastimil Hort",
    "Bernhard Horwitz",
    "Hou Yifan",
    "Robert Huebner",
    "Ildar Ibragimov",
    "Miguel Illescas Cordoba",
    "Ernesto Inarkiev",
    "Vassily Ivanchuk",
    "Alexander Ivanov",
    "Igor Ivanov",
    "Borislav Ivkov",
    "Dmitry Jakovenko",
    "David Janowski",
    "Baadur Jobava",
    "Artur Jussupow",
    "Gregory Kaidanov",
    "Gata Kamsky",
    "Sergey Karjakin",
    "Anatoly Karpov",
    "Rustam Kasimdzhanov",
    "Garry Kasparov",
    "Lubomir Kavalek",
    "Paul Keres",
    "Vincent Keymer",
    "Alexander Khalifman",
    "Ratmir Kholmov",
    "Koneru Humpy",
    "Viktor Korchnoi",
    "Anton Korobov",
    "Alexandra Kosteniuk",
    "Alexander Kotov",
    "Vladimir Kramnik",
    "Michal Krasenkow",
    "Irina Krush",
    "Sergey Kudrin",
    "Kateryna Lahno",
    "Bent Larsen",
    "Emanuel Lasker",
    "Joel Lautier",
    "Le Quang Liem",
    "Peter Leko",
    "Grigory Levenfish",
    "Li Chao",
    "Andre Lilienthal",
    "Ljubomir Ljubojevic",
    "Smbat Lputian",
    "George MacKenzie",
    "Vladimir Malakhov",
    "Shakhriyar Mamedyarov",
    "Geza Maroczy",
    "Frank Marshall",
    "Alexander McDonnell",
    "Luke McShane",
    "Henrique Mecking",
    "Vladas Mikenas",
    "Anthony Miles",
    "Vadim Milov",
    "Alexander Morozevich",
    "Paul Morphy",
    "Alexander Motylev",
    "Sergei Movsesian",
    "Mariya Muzychuk",
    "Miguel Najdorf",
    "Evgeny Najer",
    "Hikaru Nakamura",
    "David Navara",
    "Parimarjan Negi",
    "Ian Nepomniachtchi",
    "Ni Hua",
    "Peter Nielsen",
    "Predrag Nikolic",
    "Aron Nimzowitsch",
    "Liviu Dieter Nisipeanu",
    "Igor Novikov",
    "John Nunn",
    "Fridrik Olafsson",
    "Lembit Oll",
    "Alexander Onischuk",
    "Ludek Pachman",
    "Elisabeth Paehtz",
    "Oscar Panno",
    "Louis Paulsen",
    "Tigran Petrosian",
    "Francois Philidor",
    "Harry Pillsbury",
    "Herman Pilnik",
    "Judit Polgar",
    "Sofia Polgar",
    "Zsuzsa Polgar",
    "Lev Polugaevsky",
    "Ruslan Ponomariov",
    "Lajos Portisch",
    "Rameshbabu Praggnanandhaa",
    "Lev Psakhis",
    "Miguel Quinteros",
    "Teimour Radjabov",
    "Richard Rapport",
    "Samuel Reshevsky",
    "Richard Reti",
    "Zoltan Ribli",
    "Michael Rohde",
    "Akiba Rubinstein",
    "Sergei Rublevsky",
    "Friedrich Saemisch",
    "Konstantin Sakaev",
    "Valery Salov",
    "Krishnan Sasikiran",
    "Carl Schlechter",
    "Yasser Seirawan",
    "Gregory Serper",
    "Alexander Shabalov",
    "Leonid Shamkovich",
    "Alexei Shirov",
    "Nigel Short",
    "Yury Shulman",
    "Ilia Smirin",
    "Vasily Smyslov",
    "Wesley So",
    "Ivan Sokolov",
    "Andrew Soltis",
    "Boris Spassky",
    "Jonathan Speelman",
    "Rudolf Spielmann",
    "Gideon Stahlberg",
    "Howard Staunton",
    "Antoaneta Stefanova",
    "Leonid Stein",
    "William Steinitz",
    "Alexey Suetin",
    "Mir Sultan Khan",
    "Emil Sutovsky",
    "Peter Svidler",
    "Laszlo Szabo",
    "Mark Taimanov",
    "Mikhail Tal",
    "Siegbert Tarrasch",
    "Savielly Tartakower",
    "Richard Teichmann",
    "Jan Timman",
    "Sergei Tiviakov",
    "Vladislav Tkachiev",
    "Evgeny Tomashevsky",
    "Veselin Topalov",
    "Carlos Torre Repetto",
    "Wolfgang Uhlmann",
    "Wolfgang Unzicker",
    "Anna Ushenina",
    "Maxime Vachier Lagrave",
    "Rafael Vaganian",
    "Francisco Vallejo Pons",
    "Loek Van Wely",
    "Nikita Vitiugov",
    "Andrei Volokitin",
    "Joshua Waitzkin",
    "Wang Yue",
    "Wang Hao",
    "Wei Yi",
    "Simon Winawer",
    "Radoslaw Wojtaszek",
    "Aleksander Wojtkiewicz",
    "Patrick Wolff",
    "Xie Jun",
    "Xu Yuhua",
    "Ye Jiangchuan",
    "Alex Yermolinsky",
    "Yu Yangyi",
    "Leonid Yudasin",
    "Zhu Chen",
    "Johannes Zukertort",
    "Vadim Zvjaginsev"
]

players = [
"Yu Yangyi",
"Vladislav Tkachiev",
"Evgeny Tomashevsky",
"Zhu Chen",
"Veselin Topalov",
"Johannes Zukertort",
"Carlos Torre Repetto",
"Vadim Zvjaginsev"]

# ================= DRIVER FACTORY =================
def create_driver():
    chrome_options = Options()
    # chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280x800")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Anti-detection tweaks
    # chrome_options.add_argument("--disable-blink-features=AutomationControlled")


    return webdriver.Chrome(options=chrome_options)


# ================= WORKER FUNCTION =================
def download_faces(player_name):
    try:
        driver = create_driver()

        query = f"{player_name} face portrait chess"
        url = f"https://duckduckgo.com/?q={quote_plus(query)}&iax=images&ia=images"

        driver.get(url)
        time.sleep(random.uniform(1.5, 2.5))

        # driver.execute_script("""
        # Object.defineProperty(navigator, 'webdriver', {
        #     get: () => undefined
        # })
        # """)

        # driver.execute_script("""
        # document.querySelectorAll('img').forEach(img => {
        #     if (img.dataset && img.dataset.src) {
        #         img.src = img.dataset.src;
        #     }
        # });
        # """)

        time.sleep(2)

        # Minimal scroll (only once)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(1, 2))

        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()

        images = soup.select('img[src^="//"]')

        os.makedirs(SAVE_PATH, exist_ok=True)

        saved = 0
        for img in images:
            if saved >= IMAGES_PER_PLAYER:
                break

            try:
                src = img.get("src")
                if not src:
                    continue

                if src.startswith("//"):
                    src = "https:" + src

                # Skip junk images
                if any(x in src.lower() for x in ["logo", "icon", "sprite"]):
                    continue

                response = requests.get(src, timeout=5)
                if response.status_code != 200:
                    continue

                image = Image.open(BytesIO(response.content))
                w, h = image.size

                if w < 200 or h < 200:
                    continue

                filename = f"{player_name.replace(' ', '_')}_{saved+1}.jpg"
                filepath = os.path.join(SAVE_PATH, filename)

                #Avoid saving twice
                # if os.path.exists(filepath):
                #     continue

                with open(filepath, "wb") as f:
                    f.write(response.content)

                saved += 1

            except Exception:
                continue

        print(f"[✓] {player_name}: {saved} images")

        # Random delay to reduce blocking risk
        time.sleep(random.uniform(3, 7))

    except Exception as e:
        print(f"[✗] {player_name}: {e}")


# ================= MAIN =================
if __name__ == "__main__":
    print(f"Running with {MAX_WORKERS} workers...\n")

    with Pool(processes=MAX_WORKERS) as pool:
        pool.map(download_faces, players)

    print("\nDone.")