require('dotenv').config();

const fs = require('fs');
const fse = require('fs-extra');
const csv = require('csv-parser');
const mysql = require('mysql2/promise');


const FAILED_LOG = 'failed_rows.jsonl'; // one JSON per line
const CSV_FILE = 'puzzles_part_1.csv';


const stats = {
  processed: 0,
  inserted: 0,
  failed: 0
};

function normalizeRow(row) {
  // Basic validation & cleanup
  if (!row.PuzzleId || !row.FEN || !row.Moves) {
    throw new Error('Missing required fields');
  }

  return {
    PuzzleId: row.PuzzleId.trim(),
    FEN: row.FEN.trim(),
    Moves: row.Moves.trim(),
    Rating: parseInt(row.Rating, 10) || 0,
    RatingDeviation: parseInt(row.RatingDeviation, 10) || null,
    Popularity: parseInt(row.Popularity, 10) || null,
    NbPlays: parseInt(row.NbPlays, 10) || null,
    Themes: row.Themes || null,
    GameUrl: row.GameUrl || null,
    OpeningTags: row.OpeningTags || null
  };
}

(async () => {
  const connection = await mysql.createConnection({
    host: process.env.DB_HOST,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_NAME,
    // port: process.env.DB_PORT
  });

  console.log('✅ MySQL connected');

  const insertSQL = `
    INSERT INTO puzzles (
      PuzzleId, FEN, Moves, Rating,
      RatingDeviation, Popularity, NbPlays,
      Themes, GameUrl, OpeningTags,
      addon, addon2, date_time
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `;

  // Ensure failed log file is fresh
  await fse.writeFile(FAILED_LOG, '');

  const stream = fs.createReadStream(CSV_FILE).pipe(csv());

  for await (const rawRow of stream) {
    stats.processed++;

    try {
      const row = normalizeRow(rawRow);

      await connection.execute(insertSQL, [
        row.PuzzleId,
        row.FEN,
        row.Moves,
        row.Rating,
        row.RatingDeviation || "",
        row.Popularity || "",
        row.NbPlays || "",
        row.Themes || "",
        row.GameUrl || "",
        row.OpeningTags || "",
        "",
        "",
        new Date()
      ]);

      stats.inserted++;

    } catch (err) {
      stats.failed++;

      // Save failed row + reason
      await fse.appendFile(
        FAILED_LOG,
        JSON.stringify({
          error: err.message,
          row: rawRow
        }) + '\n'
      );
    }

    // Progress report
    if (stats.processed % 1000 === 0) {
      console.log(
        `Processed: ${stats.processed} | Inserted: ${stats.inserted} | Failed: ${stats.failed}`
      );
    }
  }

  await connection.end();

  console.log('\n📊 FINAL REPORT');
  console.log('-------------------------');
  console.log(`Total processed : ${stats.processed}`);
  console.log(`Successfully in DB : ${stats.inserted}`);
  console.log(`Failed rows : ${stats.failed}`);
  console.log(`Failed log file : ${FAILED_LOG}`);
})();
