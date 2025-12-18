require('dotenv').config();
const fs = require('fs');
const fse = require('fs-extra');
const csv = require('csv-parser');
const mysql = require('mysql2/promise');

async function importCSV(index) {
  const FAILED_LOG = `reports/failed_rows${index}.jsonl`;
  const CSV_FILE = `puzzles_db/puzzles_part_${index}.csv`;

  const stats = { processed: 0, inserted: 0, failed: 0 };

  function normalizeRow(row) {
    if (!row.PuzzleId || !row.FEN || !row.Moves) {
      throw new Error('Missing required fields');
    }

    return {
      PuzzleId: row.PuzzleId.trim(),
      FEN: row.FEN.trim(),
      Moves: row.Moves.trim(),
      Rating: parseInt(row.Rating, 10) || 0,
      RatingDeviation: parseInt(row.RatingDeviation, 10) || "",
      Popularity: parseInt(row.Popularity, 10) || "",
      NbPlays: parseInt(row.NbPlays, 10) || "",
      Themes: row.Themes || "",
      GameUrl: row.GameUrl || "",
      OpeningTags: row.OpeningTags || ""
    };
  }

  const connection = await mysql.createConnection({
    host: process.env.DB_HOST,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,
    database: process.env.DB_NAME
  });

  console.log(`✅ MySQL connected (file ${index})`);

  await fse.writeFile(FAILED_LOG, '');

  const insertSQL = `
    INSERT INTO puzzles (
      PuzzleId, FEN, Moves, Rating,
      RatingDeviation, Popularity, NbPlays,
      Themes, GameUrl, OpeningTags,
      addon, addon2, date_time
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `;

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
        row.RatingDeviation,
        row.Popularity,
        row.NbPlays,
        row.Themes,
        row.GameUrl,
        row.OpeningTags,
        "",
        "",
        new Date()
      ]);

      stats.inserted++;
    } catch (err) {
      stats.failed++;
      await fse.appendFile(
        FAILED_LOG,
        JSON.stringify({ error: err.message, row: rawRow }) + '\n'
      );
    }

    if (stats.processed % 1000 === 0) {
      console.log(
        `[file ${index}] Processed: ${stats.processed} | Inserted: ${stats.inserted} | Failed: ${stats.failed}`
      );
    }
  }

  await connection.end();

  console.log(`✔ Finished file ${index}`);
}

(async () => {
  for (let index = 1; index < 35; index++) {
    await importCSV(index); // ⬅️ WAIT here
  }
  console.log('🎉 ALL CSV FILES IMPORTED');
})();
