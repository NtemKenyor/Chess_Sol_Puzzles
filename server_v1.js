const express = require('express');
const fs = require('fs');
const path = require('path');
const app = express();
const PORT = 3000;
const MAIN_DIR = '/chess_sol_puzzles';

// Serve static files from public directory
app.use(express.static('public'));
app.use(express.json());

// Parse CSV file
function parseCSV(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.trim().split('\n');
  const puzzles = [];
  
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i];
    const parts = line.split(',');
    
    if (parts.length >= 10) {
      puzzles.push({
        id: parts[1],
        fen: parts[2],
        moves: parts[3].split(' '),
        rating: parseInt(parts[4]),
        popularity: parseInt(parts[6]),
        themes: parts[8],
        gameUrl: parts[9]
      });
    }
  }
  
  return puzzles;
}

// Load puzzles
let puzzles = [];
try {
  puzzles = parseCSV('puzzles.csv');
  console.log(`Loaded ${puzzles.length} puzzles`);
} catch (error) {
  console.error('Error loading puzzles:', error.message);
}

app.get(MAIN_DIR+'/', (req, res) => {
  res.send('Entrace Point - Hello world');
});

// API endpoint to get a random puzzle
app.get('/api/puzzle/random', (req, res) => {
  if (puzzles.length === 0) {
    return res.status(500).json({ error: 'No puzzles available' });
  }
  
  const randomIndex = Math.floor(Math.random() * puzzles.length);
  const puzzle = puzzles[randomIndex];
  
  res.json({
    id: puzzle.id,
    fen: puzzle.fen,
    rating: puzzle.rating,
    themes: puzzle.themes,
    movesCount: puzzle.moves.length
  });
});

// API endpoint to verify a move
app.post('/api/puzzle/verify', (req, res) => {
  const { puzzleId, moveIndex, move } = req.body;
  
  const puzzle = puzzles.find(p => p.id === puzzleId);
  
  if (!puzzle) {
    return res.status(404).json({ error: 'Puzzle not found' });
  }
  
  const expectedMove = puzzle.moves[moveIndex];
  const isCorrect = move === expectedMove;
  const isComplete = moveIndex === puzzle.moves.length - 1;
  
  res.json({
    correct: isCorrect,
    complete: isComplete && isCorrect,
    expectedMove: isCorrect ? expectedMove : null,
    nextMove: isCorrect && !isComplete ? puzzle.moves[moveIndex + 1] : null
  });
});

// API endpoint to get puzzle by ID
app.get('/api/puzzle/:id', (req, res) => {
  const puzzle = puzzles.find(p => p.id === req.params.id);
  
  if (!puzzle) {
    return res.status(404).json({ error: 'Puzzle not found' });
  }
  
  res.json({
    id: puzzle.id,
    fen: puzzle.fen,
    rating: puzzle.rating,
    themes: puzzle.themes,
    movesCount: puzzle.moves.length
  });
});

app.listen(PORT, () => {
  console.log(`Chess Puzzle server running on http://localhost:${PORT}`);
});