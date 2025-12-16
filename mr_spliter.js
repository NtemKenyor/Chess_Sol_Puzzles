const fs = require("fs");
const readline = require("readline");

async function splitCsv(inputFile, rowsPerFile = 100000) {
    const inputStream = fs.createReadStream(inputFile);
    const rl = readline.createInterface({ input: inputStream });

    let header = null;
    let fileIndex = 1;
    let rowCount = 0;
    let outputStream = null;

    function createNewFile() {
        const outputFile = `puzzles_part_${fileIndex}.csv`;
        outputStream = fs.createWriteStream(outputFile);

        // Write header first
        outputStream.write(header + "\n");

        console.log(`Created file: ${outputFile}`);
        fileIndex++;
        rowCount = 0;
    }

    for await (const line of rl) {
        // Store header from first row
        if (!header) {
            header = line;
            continue;
        }

        // If no output file open yet, create the first one
        if (!outputStream) {
            createNewFile();
        }

        // Write data row
        outputStream.write(line + "\n");
        rowCount++;

        // If this file reached 100k rows, close and start a new one
        if (rowCount >= rowsPerFile) {
            outputStream.end();
            outputStream = null;
        }
    }

    // Close last file if still open
    if (outputStream) {
        outputStream.end();
    }

    console.log("Done! All CSV chunks created successfully.");
}

splitCsv("puzzles.csv", 100000)
    .catch(err => console.error(err));
