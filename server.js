require('dotenv').config();

const express = require('express');
const cors = require('cors');
const mysql = require('mysql2/promise');

const app = express();
const PORT = 3000;
const MAIN_DIR = '/Chess_Sol_Puzzles';

/* =========================
   CORS CONFIGURATION
   ========================= */
app.use(cors({
  origin: function (origin, callback) {
    if (!origin) return callback(null, true);

    if (
      origin === 'https://roynek.com' ||
      origin.endsWith('.roynek.com') ||
      origin === 'http://localhost:3000' ||
      origin === 'http://localhost'
    ) {
      return callback(null, true);
    }

    return callback(new Error('Not allowed by CORS'));
  },
  methods: ['GET', 'POST', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true
}));

/* =========================
   MIDDLEWARES
   ========================= */
app.use(express.json());
app.use(express.static('public'));

/* =========================
   MYSQL CONNECTION POOL
   ========================= */
const pool = mysql.createPool({
  host: process.env.DB_HOST,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0
});

/* =========================
   PUZZLE COUNT CACHE
   ========================= */
let PUZZLE_COUNT = null;

async function getPuzzleCount() {
  if (PUZZLE_COUNT === null) {
    const [[{ total }]] = await pool.query(
      `SELECT COUNT(*) AS total FROM puzzles`
    );
    PUZZLE_COUNT = total;
    console.log('Cached puzzle count:', PUZZLE_COUNT);
  }
  return PUZZLE_COUNT;
}

/* =========================
   ROUTES
   ========================= */
app.get(MAIN_DIR + '/', (req, res) => {
  res.send('Entrance Point - Hello world');
});

/* =========================
   GET RANDOM PUZZLE (FIXED)
   ========================= */
app.get(MAIN_DIR + '/api/puzzle/random', async (req, res) => {
  try {
    const total = await getPuzzleCount();

    if (!total) {
      return res.status(500).json({ error: 'No puzzles available' });
    }

    const offset = Math.floor(Math.random() * total);

    const [rows] = await pool.query(
      `
      SELECT
        PuzzleId AS id,
        FEN AS fen,
        Moves AS moves,
        Rating AS rating,
        Themes AS themes
      FROM puzzles
      LIMIT 1 OFFSET ?
      `,
      [offset]
    );

    if (!rows.length) {
      return res.status(500).json({ error: 'No puzzles available' });
    }

    const puzzle = rows[0];
    const moves = puzzle.moves.trim().split(' ').filter(Boolean);

    res.json({
      id: puzzle.id,
      fen: puzzle.fen,
      rating: puzzle.rating || 1500,
      themes: puzzle.themes || 'tactical',
      moves,
      totalMoves: moves.length
    });

  } catch (err) {
    console.error('DB Error (random puzzle):', err.message);
    res.status(500).json({ error: 'Database error' });
  }
});

/* =========================
   GET RANDOM PUZZLE BY RATING
   ========================= */
app.get(MAIN_DIR + '/api/puzzle/random-by-rating', async (req, res) => {
  try {
    let { min, max } = req.query;

    min = min ? parseInt(min) : 0;
    max = max ? parseInt(max) : 9999;

    if (isNaN(min) || isNaN(max)) {
      return res.status(400).json({ error: 'Invalid rating range' });
    }

    // 1. Count puzzles in rating range
    const [[{ total }]] = await pool.query(
      `
      SELECT COUNT(*) AS total
      FROM puzzles
      WHERE Rating BETWEEN ? AND ?
      `,
      [min, max]
    );

    if (!total) {
      return res.status(404).json({
        error: 'No puzzles found in this rating range'
      });
    }

    // 2. Random offset
    const offset = Math.floor(Math.random() * total);

    // 3. Fetch random puzzle
    const [rows] = await pool.query(
      `
      SELECT
        PuzzleId AS id,
        FEN AS fen,
        Moves AS moves,
        Rating AS rating,
        Themes AS themes
      FROM puzzles
      WHERE Rating BETWEEN ? AND ?
      LIMIT 1 OFFSET ?
      `,
      [min, max, offset]
    );

    const puzzle = rows[0];
    const moves = puzzle.moves.trim().split(' ').filter(Boolean);

    res.json({
      id: puzzle.id,
      fen: puzzle.fen,
      rating: puzzle.rating || 1500,
      themes: puzzle.themes || 'tactical',
      moves,
      totalMoves: moves.length,
      ratingRange: { min, max }
    });

  } catch (err) {
    console.error('DB Error (random by rating):', err.message);
    res.status(500).json({ error: 'Database error' });
  }
});

/* =========================
   VERIFY MOVE
   ========================= */
app.post(MAIN_DIR + '/api/puzzle/verify', async (req, res) => {
  const { puzzleId, moveIndex, move } = req.body;

  try {
    const [rows] = await pool.query(
      `SELECT Moves FROM puzzles WHERE PuzzleId = ? LIMIT 1`,
      [puzzleId]
    );

    if (!rows.length) {
      return res.status(404).json({ error: 'Puzzle not found' });
    }

    const moves = rows[0].Moves.trim().split(' ').filter(Boolean);
    const expectedMove = moves[moveIndex];
    const isCorrect = move === expectedMove;
    const isComplete = moveIndex >= moves.length - 1;

    res.json({
      correct: isCorrect,
      complete: isComplete && isCorrect,
      expectedMove,
      nextMove:
        isCorrect && moveIndex + 1 < moves.length
          ? moves[moveIndex + 1]
          : null,
      moveNumber: moveIndex + 1,
      totalMoves: moves.length
    });

  } catch (err) {
    console.error('DB Error (verify move):', err.message);
    res.status(500).json({ error: 'Database error' });
  }
});

/* =========================
   GET PUZZLE BY ID
   ========================= */
app.get(MAIN_DIR + '/api/puzzle/:id', async (req, res) => {
  try {
    const [rows] = await pool.query(
      `
      SELECT
        PuzzleId AS id,
        FEN AS fen,
        Moves AS moves,
        Rating AS rating,
        Themes AS themes
      FROM puzzles
      WHERE PuzzleId = ?
      LIMIT 1
      `,
      [req.params.id]
    );

    if (!rows.length) {
      return res.status(404).json({ error: 'Puzzle not found' });
    }

    const puzzle = rows[0];
    const moves = puzzle.moves.trim().split(' ').filter(Boolean);

    res.json({
      id: puzzle.id,
      fen: puzzle.fen,
      rating: puzzle.rating || 1500,
      themes: puzzle.themes || 'tactical',
      moves,
      movesCount: moves.length
    });

  } catch (err) {
    console.error('DB Error (get puzzle by id):', err.message);
    res.status(500).json({ error: 'Database error' });
  }
});



/* =========================
   SERVER
   ========================= */

   
app.listen(PORT, () => {
  console.log(`🚀 Chess Puzzle server running on http://localhost:${PORT}`);
});
