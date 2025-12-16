// Simple chess logic implementation
class ChessGame {
    constructor() {
        this.board = [];
        this.selectedSquare = null;
        this.currentFEN = '';
        this.isWhiteTurn = true;
    }

    // Parse FEN notation
    parseFEN(fen) {
        this.board = Array(8).fill(null).map(() => Array(8).fill(null));
        const parts = fen.split(' ');
        const position = parts[0];
        const rows = position.split('/');
        
        for (let i = 0; i < 8; i++) {
            let col = 0;
            for (let char of rows[i]) {
                if (char >= '1' && char <= '8') {
                    col += parseInt(char);
                } else {
                    this.board[i][col] = char;
                    col++;
                }
            }
        }
        
        this.isWhiteTurn = parts[1] === 'w';
        this.currentFEN = fen;
    }

    // Get piece at position
    getPiece(row, col) {
        if (row < 0 || row > 7 || col < 0 || col > 7) return null;
        return this.board[row][col];
    }

    // Set piece at position
    setPiece(row, col, piece) {
        if (row >= 0 && row <= 7 && col >= 0 && col <= 7) {
            this.board[row][col] = piece;
        }
    }

    // Check if piece is white
    isWhitePiece(piece) {
        return piece && piece === piece.toUpperCase();
    }

    // Convert algebraic notation to coordinates
    algebraicToCoords(algebraic) {
        const file = algebraic.charCodeAt(0) - 97; // a=0, b=1, etc.
        const rank = 8 - parseInt(algebraic[1]); // 8=0, 7=1, etc.
        return { row: rank, col: file };
    }

    // Convert coordinates to algebraic notation
    coordsToAlgebraic(row, col) {
        const file = String.fromCharCode(97 + col);
        const rank = (8 - row).toString();
        return file + rank;
    }

    // Make a move
    makeMove(from, to) {
        const fromCoords = this.algebraicToCoords(from);
        const toCoords = this.algebraicToCoords(to);
        
        const piece = this.getPiece(fromCoords.row, fromCoords.col);
        if (!piece) return false;
        
        // Handle promotion
        let movingPiece = piece;
        if (to.length > 2) {
            // Promotion move like e7e8q
            movingPiece = to[2];
            if (this.isWhitePiece(piece)) {
                movingPiece = movingPiece.toUpperCase();
            }
        }
        
        this.setPiece(toCoords.row, toCoords.col, movingPiece);
        this.setPiece(fromCoords.row, fromCoords.col, null);
        
        this.isWhiteTurn = !this.isWhiteTurn;
        return true;
    }

    // Get Unicode character for piece
    getPieceUnicode(piece) {
        const pieces = {
            'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
            'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
        };
        return pieces[piece] || '';
    }

    // Check if a move is legal (basic validation)
    isValidMove(from, to) {
        const fromCoords = this.algebraicToCoords(from);
        const toCoords = this.algebraicToCoords(to);
        
        const piece = this.getPiece(fromCoords.row, fromCoords.col);
        if (!piece) return false;
        
        const targetPiece = this.getPiece(toCoords.row, toCoords.col);
        
        // Can't capture your own piece
        if (targetPiece && this.isWhitePiece(piece) === this.isWhitePiece(targetPiece)) {
            return false;
        }
        
        return true;
    }

    // Get possible moves for a piece (simplified)
    getPossibleMoves(row, col) {
        const moves = [];
        const piece = this.getPiece(row, col);
        if (!piece) return moves;
        
        const isWhite = this.isWhitePiece(piece);
        const pieceType = piece.toLowerCase();
        
        // Add all squares as potential moves (simplified for puzzle mode)
        for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) {
                const target = this.getPiece(r, c);
                if (!target || this.isWhitePiece(target) !== isWhite) {
                    moves.push({ row: r, col: c });
                }
            }
        }
        
        return moves;
    }
}