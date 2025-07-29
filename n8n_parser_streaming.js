// Enhanced n8n parser for audio splitter - supports both legacy and streaming modes
// Compatible with original format and new JSON streaming/output modes

const scriptOutput = $('Execute Audio Splitter Script').first().json;

// Check if the script executed successfully
if (!scriptOutput.stdout) {
  throw new Error('Audio splitter script produced no output');
}

// Helper function to parse JSON lines from streaming output
function parseStreamingOutput(output) {
  const lines = output.trim().split('\n').filter(line => line.trim());
  const chunks = [];
  let summary = null;
  
  for (const line of lines) {
    try {
      const data = JSON.parse(line);
      
      // Check if this is a chunk completion event
      if (data.status === 'completed' && data.chunk_number) {
        chunks.push({
          filePath: data.output_path,
          fileName: data.output_path.split('/').pop(),
          chunkNumber: data.chunk_number,
          fileSizeMB: data.file_size_mb,
          status: 'completed'
        });
      } 
      // Check if this is the final summary
      else if (data.status === 'completed' && data.total_chunks !== undefined) {
        summary = data;
      }
    } catch (e) {
      // Not JSON, skip this line
      continue;
    }
  }
  
  return { chunks, summary };
}

// Helper function to parse legacy format
function parseLegacyOutput(output) {
  const filePaths = output
    .split("\n")
    .filter(line => line.includes("Exporting "))
    .map(line => line.replace("Exporting ", "").trim())
    .filter(path => path.length > 0);
  
  return filePaths.map(path => ({
    filePath: path,
    fileName: path.split('/').pop(),
    chunkNumber: parseInt(path.match(/chunk_(\d+)/)?.[1] || '0'),
    status: 'completed'
  }));
}

// Helper function to parse JSON output mode
function parseJsonOutput(output) {
  try {
    const data = JSON.parse(output);
    if (data.status === 'success' && data.files) {
      return data.files.map((file, index) => ({
        filePath: file.path,
        fileName: file.filename,
        fileSizeMB: file.size_mb,
        chunkNumber: index + 1,
        status: 'completed'
      }));
    }
  } catch (e) {
    // Not valid JSON output format
  }
  return null;
}

// Determine output format and parse accordingly
let results = [];

// First, try to detect if it's streaming JSON output
if (scriptOutput.stdout.includes('{"chunk_number"') || scriptOutput.stdout.includes('{"status"')) {
  // Streaming mode
  const { chunks, summary } = parseStreamingOutput(scriptOutput.stdout);
  results = chunks;
  
  // Add summary info if needed
  if (summary && results.length > 0) {
    results.forEach(chunk => {
      chunk.totalChunks = summary.total_chunks;
      chunk.outputFormat = summary.output_format;
    });
  }
} 
// Try JSON output mode
else if (scriptOutput.stdout.trim().startsWith('{')) {
  const jsonResults = parseJsonOutput(scriptOutput.stdout);
  if (jsonResults) {
    results = jsonResults;
  }
}
// Fall back to legacy format
else if (scriptOutput.stdout.includes('Exporting ')) {
  results = parseLegacyOutput(scriptOutput.stdout);
}
// Check for the completion marker
else if (scriptOutput.stdout.includes('✅ Done.')) {
  // Script completed but no chunks found in expected format
  throw new Error('Script completed but no audio chunks were detected in output');
}

// Validate results
if (results.length === 0) {
  // Check stderr for errors
  if (scriptOutput.stderr) {
    throw new Error(`Audio splitter failed: ${scriptOutput.stderr}`);
  } else {
    throw new Error('No audio chunks were created or detected');
  }
}

// Return the parsed results in n8n format
return results.map(chunk => {
  return {
    json: chunk
  };
});