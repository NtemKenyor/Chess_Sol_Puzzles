// Main application logic
const game = new ChessGame();
let currentPuzzle = null;
let currentMoveIndex = 0;
let selectedSquare = null;
let timer = null;
let timeLeft = 120;
let lastMoveSquares = [];

// Initialize the application
async function init() {
    setupEventListeners();
    await loadNewPuzzle();
}

// Setup event listeners
function setupEventListeners() {
    document.getElementById('newPuzzle').addEventListener('click', loadNewPuzzle);
    document.getElementById('hint').addEventListener('click', showHint);
    document.getElementById('reset').addEventListener('click', resetPuzzle);
    document.getElementById('modalClose').addEventListener('click', closeModal);
}

// Load a new puzzle
async function loadNewPuzzle() {
    try {
        const response = await fetch('/api/puzzle/random');
        const puzzle = await response.json();
        
        currentPuzzle = puzzle;
        currentMoveIndex = 0;
        selectedSquare = null;
        lastMoveSquares = [];
        
        game.parseFEN(puzzle.fen);
        
        // Update UI
        document.getElementById('rating').textContent = puzzle.rating;
        document.getElementById('themes').textContent = puzzle.themes || 'Various';
        document.getElementById('turn-indicator').textContent = 
            game.isWhiteTurn ? 'White to move - Find the best move!' : 'Black to move - Find the best move!';
        
        renderBoard();
        hideFeedback();
        startTimer();
        
        // Make the first move (opponent's move)
        if (currentMoveIndex === 0 && puzzle.movesCount > 0) {
            setTimeout(() => makeOpponentMove(), 500);
        }
    } catch (error) {
        showFeedback('Error loading puzzle. Please try again.', 'error');
    }
}

// Make opponent's move
async function makeOpponentMove() {
    if (!currentPuzzle) return;
    
    const response = await fetch('/api/puzzle/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            puzzleId: currentPuzzle.id,
            moveIndex: currentMoveIndex,
            move: 'get_expected'
        })
    });
    
    const result = await response.json();
    const move = result.expectedMove;
    
    if (move) {
        const from = move.substring(0, 2);
        const to = move.substring(2, 4);
        
        lastMoveSquares = [from, to];
        game.makeMove(from, to);
        renderBoard();
        currentMoveIndex++;
        
        document.getElementById('turn-indicator').textContent = 
            game.isWhiteTurn ? 'Your turn - Find the best move!' : 'Your turn - Find the best move!';
    }
}

// Render the chess board
function renderBoard() {
    const board = document.getElementById('chessboard');
    board.innerHTML = '';
    
    for (let row = 0; row < 8; row++) {
        for (let col = 0; col < 8; col++) {
            const square = document.createElement('div');
            square.className = 'square';
            square.className += (row + col) % 2 === 0 ? ' light' : ' dark';
            square.dataset.row = row;
            square.dataset.col = col;
            
            const algebraic = game.coordsToAlgebraic(row, col);
            square.dataset.square = algebraic;
            
            // Highlight last move
            if (lastMoveSquares.includes(algebraic)) {
                square.classList.add('last-move');
            }
            
            const piece = game.getPiece(row, col);
            if (piece) {
                const pieceElement = document.createElement('span');
                pieceElement.className = 'piece';
                pieceElement.textContent = game.getPieceUnicode(piece);
                square.appendChild(pieceElement);
            }
            
            square.addEventListener('click', handleSquareClick);
            board.appendChild(square);
        }
    }
}

// Handle square click
async function handleSquareClick(event) {
    const square = event.currentTarget;
    const row = parseInt(square.dataset.row);
    const col = parseInt(square.dataset.col);
    const algebraic = square.dataset.square;
    
    if (selectedSquare) {
        // Try to make a move
        const from = selectedSquare;
        const to = algebraic;
        
        if (from !== to) {
            await attemptMove(from, to);
        }
        
        // Clear selection
        document.querySelectorAll('.square').forEach(s => {
            s.classList.remove('selected', 'highlight');
        });
        selectedSquare = null;
    } else {
        // Select a piece
        const piece = game.getPiece(row, col);
        if (piece && game.isWhitePiece(piece) === game.isWhiteTurn) {
            selectedSquare = algebraic;
            square.classList.add('selected');
            
            // Highlight possible moves
            const moves = game.getPossibleMoves(row, col);
            moves.forEach(move => {
                const targetSquare = document.querySelector(
                    `[data-square="${game.coordsToAlgebraic(move.row, move.col)}"]`
                );
                if (targetSquare) {
                    targetSquare.classList.add('highlight');
                }
            });
        }
    }
}

// Attempt to make a move
async function attemptMove(from, to) {
    const move = from + to;
    
    try {
        const response = await fetch('/api/puzzle/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                puzzleId: currentPuzzle.id,
                moveIndex: currentMoveIndex,
                move: move
            })
        });
        
        const result = await response.json();
        
        if (result.correct) {
            // Make the move
            lastMoveSquares = [from, to];
            game.makeMove(from, to);
            renderBoard();
            currentMoveIndex++;
            
            showFeedback('Correct! Great move! ✓', 'success');
            
            if (result.complete) {
                // Puzzle solved!
                stopTimer();
                setTimeout(() => {
                    showModal('Congratulations! 🎉', 'You solved the puzzle! Ready for another challenge?');
                }, 1000);
            } else if (result.nextMove) {
                // Make opponent's next move
                setTimeout(async () => {
                    const nextFrom = result.nextMove.substring(0, 2);
                    const nextTo = result.nextMove.substring(2, 4);
                    lastMoveSquares = [nextFrom, nextTo];
                    game.makeMove(nextFrom, nextTo);
                    renderBoard();
                    currentMoveIndex++;
                    hideFeedback();
                }, 1000);
            }
        } else {
            showFeedback('Incorrect move! Try again. ✗', 'error');
        }
    } catch (error) {
        showFeedback('Error verifying move. Please try again.', 'error');
    }
}

// Show feedback
function showFeedback(message, type) {
    const feedback = document.getElementById('feedback');
    feedback.textContent = message;
    feedback.className = `feedback ${type}`;
    feedback.classList.remove('hidden');
}

// Hide feedback
function hideFeedback() {
    const feedback = document.getElementById('feedback');
    feedback.classList.add('hidden');
}

// Show modal
function showModal(title, message) {
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalMessage').textContent = message;
    document.getElementById('modal').classList.remove('hidden');
}

// Close modal
function closeModal() {
    document.getElementById('modal').classList.add('hidden');
    loadNewPuzzle();
}

// Start timer
function startTimer() {
    stopTimer();
    timeLeft = 120;
    updateTimerDisplay();
    
    timer = setInterval(() => {
        timeLeft--;
        updateTimerDisplay();
        
        if (timeLeft <= 0) {
            stopTimer();
            showModal('Time\'s Up! ⏰', 'Better luck next time! Want to try another puzzle?');
        }
    }, 1000);
}

// Stop timer
function stopTimer() {
    if (timer) {
        clearInterval(timer);
        timer = null;
    }
}

// Update timer display
function updateTimerDisplay() {
    const minutes = Math.floor(timeLeft / 60);
    const seconds = timeLeft % 60;
    document.getElementById('timer').textContent = 
        `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

// Show hint
function showHint() {
    showFeedback('Hint: Look for tactical patterns like pins, forks, or discovered attacks!', 'success');
    setTimeout(hideFeedback, 3000);
}

// Reset puzzle
function resetPuzzle() {
    if (currentPuzzle) {
        currentMoveIndex = 0;
        selectedSquare = null;
        lastMoveSquares = [];
        game.parseFEN(currentPuzzle.fen);
        renderBoard();
        hideFeedback();
        startTimer();
        
        // Make the first move again
        setTimeout(() => makeOpponentMove(), 500);
    }
}

// Start the application
init();