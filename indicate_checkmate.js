require('dotenv').config();
const mysql = require('mysql2/promise');
const { Chess } = require('chess.js');

const BATCH_SIZE = 2000;

async function detectCheckmates() {

  const connection = await mysql.createConnection({
    host: process.env.DB_HOST,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_NAME
  });

  console.log("✅ MySQL connected");

  let lastId = 0;
  let processed = 0;

  while (true) {

    const [rows] = await connection.execute(
        `SELECT id, FEN, Moves
            FROM puzzles
            WHERE id > ?
            ORDER BY id
            LIMIT ${BATCH_SIZE}`,
        [lastId]
    );

    if (rows.length === 0) break;

    const checkmateIds = [];

    for (const row of rows) {

      try {

        const chess = new Chess(row.FEN);

        const moves = row.Moves.split(" ");

        for (const move of moves) {

          const from = move.slice(0,2);
          const to = move.slice(2,4);
          const promotion = move.length === 5 ? move[4] : undefined;

          chess.move({ from, to, promotion });

        }

        if (chess.isCheckmate()) {
          checkmateIds.push(row.id);
        }

      } catch (err) {
        // ignore invalid puzzles
      }

      processed++;

      if (processed % 5000 === 0) {
        console.log("Processed:", processed);
      }

    }

    // BULK UPDATE (very fast)
    if (checkmateIds.length > 0) {

      const placeholders = checkmateIds.map(() => '?').join(',');

      await connection.execute(
        `UPDATE puzzles 
         SET addon='CHECKMATE' 
         WHERE id IN (${placeholders})`,
        checkmateIds
      );

      console.log("✔ Updated", checkmateIds.length, "checkmates");

    }

    lastId = rows[rows.length - 1].id;

  }

  await connection.end();

  console.log("🎉 Finished scanning puzzles");
}

detectCheckmates();