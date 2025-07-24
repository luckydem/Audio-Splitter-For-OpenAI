// Improved n8n parser for audio splitter output
// This version is more robust and handles errors better

const scriptOutput = $('Execute Audio Splitter Script').first().json;

// Check if the script executed successfully
if (!scriptOutput.stdout) {
  throw new Error('Audio splitter script produced no output');
}

// Parse file paths from stdout
const filePaths = scriptOutput.stdout
    .split("\n")
    .filter(line => line.includes("Exporting "))
    .map(line => line.replace("Exporting ", "").trim())
    .filter(path => path.length > 0);  // Remove empty paths

// Check if any files were created
if (filePaths.length === 0) {
  // Check stderr for errors
  if (scriptOutput.stderr) {
    throw new Error(`Audio splitter failed: ${scriptOutput.stderr}`);
  } else {
    throw new Error('No audio chunks were created');
  }
}

// Return the file paths
return filePaths.map(path => {
  return {
    json: {
      filePath: path,
      fileName: path.split('/').pop(),  // Extract just the filename
      chunkNumber: parseInt(path.match(/chunk_(\d+)/)?.[1] || '0')
    }
  };
});