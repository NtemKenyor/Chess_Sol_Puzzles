// const express = require('express');
// const fs = require('fs');
// const path = require('path');
// const app = express();
// const PORT = 3000;

// app.use(express.json());
// app.use(express.static('.'));

// // Parse CSV file with streaming to avoid memory issues
// function parseCSV(filePath) {
//   try {
//     const content = fs.readFileSync(filePath, 'utf-8');
//     const lines = content.split('\n');
//     const puzzles = [];
    
//     // Skip header line
//     for (let i = 1; i < lines.length && i < 1000; i++) { // Limit to first 1000 puzzles
//       const line = lines[i].trim();
//       if (!line) continue;
      
//       // Split by comma, but handle commas in URLs
//       const match = line.match(/^(\d+),([^,]+),([^,]+),([^,]+),(\d+),(\d+),(\d+),(\d+),([^,]*),([^,]*),?(.*)$/);
      
//       if (match) {
//         puzzles.push({
//           id: match[2],
//           fen: match[3],
//           moves: match[4].trim().split(' '),
//           rating: parseInt(match[5]) || 0,
//           popularity: parseInt(match[7]) || 0,
//           themes: match[9] || '',
//           gameUrl: match[10] || ''
//         });
//       }
//     }
    
//     return puzzles;
//   } catch (error) {
//     console.error('CSV parsing error:', error.message);
//     return [];
//   }
// }

// // Load puzzles
// let puzzles = [];
// try {
//   puzzles = parseCSV('puzzles_part_1.csv');
//   console.log(`✓ Loaded ${puzzles.length} puzzles successfully`);
// } catch (error) {
//   console.error('Error loading puzzles:', error.message);
// }

// // API endpoint to get a random puzzle
// app.get('/api/puzzle/random', (req, res) => {
//   if (puzzles.length === 0) {
//     return res.status(500).json({ error: 'No puzzles available' });
//   }
  
//   const randomIndex = Math.floor(Math.random() * puzzles.length);
//   const puzzle = puzzles[randomIndex];
  
//   res.json({
//     id: puzzle.id,
//     fen: puzzle.fen,
//     rating: puzzle.rating,
//     themes: puzzle.themes,
//     moves: puzzle.moves, // Send all moves
//     movesCount: puzzle.moves.length
//   });
// });

// // API endpoint to verify a move
// app.post('/api/puzzle/verify', (req, res) => {
//   const { puzzleId, moveIndex, move } = req.body;
  
//   const puzzle = puzzles.find(p => p.id === puzzleId);
  
//   if (!puzzle) {
//     return res.status(404).json({ error: 'Puzzle not found' });
//   }
  
//   const expectedMove = puzzle.moves[moveIndex];
//   const isCorrect = move === expectedMove;
//   const isComplete = moveIndex === puzzle.moves.length - 1;
  
//   res.json({
//     correct: isCorrect,
//     complete: isComplete && isCorrect,
//     expectedMove: expectedMove,
//     nextMove: isCorrect && !isComplete ? puzzle.moves[moveIndex + 1] : null,
//     totalMoves: puzzle.moves.length,
//     currentMove: moveIndex + 1
//   });
// });

// app.listen(PORT, () => {
//   console.log(`✓ Chess Puzzle server running on http://localhost:${PORT}`);
//   if (puzzles.length === 0) {
//     console.log('⚠ WARNING: No puzzles loaded. Check puzzles_part_1.csv file.');
//   }
// });


const express = require('express');
const fs = require('fs');
const path = require('path');
const app = express();
const PORT = 3000;
const MAIN_DIR = '/chess_sol_puzzles';


app.use(express.json());
app.use(express.static('public'));

// Parse CSV file with better memory handling
function parseCSV(filePath) {
    console.log('Parsing CSV file:', filePath);

  try {
    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.split('\n');
    const puzzles = [];
    
    // Skip header line
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      
      // Split by comma, but be careful with commas in URLs
      const match = line.match(/^(\d+),([^,]+),([^,]+),([^,]+),(\d+),(\d+),(\d+),(\d+),([^,]*),([^,]*),?(.*)$/);
      
      if (match) {
        puzzles.push({
          id: match[2],
          fen: match[3],
          moves: match[4].trim().split(' ').filter(m => m.length > 0),
          rating: parseInt(match[5]) || 1500,
          popularity: parseInt(match[7]) || 0,
          themes: match[9] || 'tactical',
          gameUrl: match[10] || ''
        });
      }
    }
    
    return puzzles;
  } catch (error) {
    console.error('CSV Parse Error:', error.message);
    return [];
  }
}

// Load puzzles
let puzzles = [];
const csvPath = path.join(__dirname, 'puzzles_part_1.csv');

if (fs.existsSync(csvPath)) {
  puzzles = parseCSV(csvPath);
  console.log(`✓ Loaded ${puzzles.length} puzzles successfully`);
} else {
  console.error('✗ puzzles_part_1.csv not found in:', __dirname);
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
    moves: puzzle.moves,
    totalMoves: puzzle.moves.length
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
  const isComplete = moveIndex >= puzzle.moves.length - 1;
  
  res.json({
    correct: isCorrect,
    complete: isComplete && isCorrect,
    expectedMove: expectedMove,
    nextMove: isCorrect && moveIndex + 1 < puzzle.moves.length ? puzzle.moves[moveIndex + 1] : null,
    moveNumber: moveIndex + 1,
    totalMoves: puzzle.moves.length
  });
});

app.listen(PORT, () => {
  console.log(`\n🚀 Chess Puzzle server running on http://localhost:${PORT}\n`);
});