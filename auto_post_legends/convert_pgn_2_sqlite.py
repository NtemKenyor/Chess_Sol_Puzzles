import os
import sqlite3
import hashlib
import chess.pgn

INPUT_DIR = "legendary_games"
DB_FILE = "legend_games.db"


# ---------------------------
# DB SETUP
# ---------------------------
def init_db(conn):
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        event TEXT,
        site TEXT,
        date TEXT,
        round TEXT,

        white TEXT,
        black TEXT,
        result TEXT,

        white_elo TEXT,
        black_elo TEXT,

        eco TEXT,

        moves TEXT,
        final_fen TEXT,

        termination_type TEXT,

        legend TEXT,

        game_hash TEXT UNIQUE
    )
    """)

    # Indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_legend ON games(legend)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_result ON games(result)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_termination ON games(termination_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_eco ON games(eco)")

    conn.commit()


# ---------------------------
# HASHING (DEDUP KEY)
# ---------------------------
def compute_game_hash(headers, moves_str):
    base = "|".join([
        headers.get("White", ""),
        headers.get("Black", ""),
        headers.get("Date", ""),
        moves_str
    ])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


# ---------------------------
# MOVE EXTRACTION
# ---------------------------
def extract_moves_and_board(game):
    board = game.board()
    moves = []

    for move in game.mainline_moves():
        moves.append(board.san(move))
        board.push(move)

    return " ".join(moves), board


# ---------------------------
# TERMINATION LOGIC (YOUR RULE)
# ---------------------------
def get_termination_type(board, result):
    if board.is_checkmate():
        return "checkmate"

    if result in ["1-0", "0-1"]:
        return "resignation"

    return "draw_or_other"


# ---------------------------
# INSERT (DEDUP SAFE)
# ---------------------------
def insert_game(conn, data):
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR IGNORE INTO games (
        event, site, date, round,
        white, black, result,
        white_elo, black_elo,
        eco,
        moves, final_fen,
        termination_type,
        legend,
        game_hash
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("Event"),
        data.get("Site"),
        data.get("Date"),
        data.get("Round"),
        data.get("White"),
        data.get("Black"),
        data.get("Result"),
        data.get("WhiteElo"),
        data.get("BlackElo"),
        data.get("ECO"),
        data["Moves"],
        data["FinalFEN"],
        data["TerminationType"],
        data["Legend"],
        data["GameHash"]
    ))

    conn.commit()


# ---------------------------
# PROCESS FILE
# ---------------------------
def process_pgn_file(conn, filepath, legend_name):
    inserted = 0

    with open(filepath, encoding="utf-8", errors="ignore") as f:
        while True:
            game = chess.pgn.read_game(f)
            if game is None:
                break

            headers = dict(game.headers)

            # Moves + final board
            moves_str, final_board = extract_moves_and_board(game)

            result = headers.get("Result", "*")

            termination = get_termination_type(final_board, result)

            # Dedup hash
            game_hash = compute_game_hash(headers, moves_str)

            data = {
                **headers,
                "Moves": moves_str,
                "FinalFEN": final_board.fen(),
                "TerminationType": termination,
                "Legend": legend_name,
                "GameHash": game_hash
            }

            before = conn.total_changes
            insert_game(conn, data)
            after = conn.total_changes

            if after > before:
                inserted += 1

    return inserted


# ---------------------------
# MAIN PIPELINE
# ---------------------------
def main():
    conn = sqlite3.connect(DB_FILE)

    # Performance tuning (safe + faster bulk inserts)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")

    init_db(conn)

    total_inserted = 0

    for filename in os.listdir(INPUT_DIR):
        if filename.endswith(".pgn"):
            filepath = os.path.join(INPUT_DIR, filename)
            legend_name = filename.replace(".pgn", "")

            print(f"[INFO] Processing {filename}")

            inserted = process_pgn_file(conn, filepath, legend_name)

            print(f"   → Inserted {inserted} new games")
            total_inserted += inserted

    conn.close()

    print(f"\n✅ Done. Total new games inserted: {total_inserted}")
    print(f"📦 Database: {DB_FILE}")


if __name__ == "__main__":
    main()