// Aggregation code for merging transcriptions
// Use this in a Code node after collecting all chunk results

// If results are in a database
const chunks = $input.all(); // Assuming chunks are retrieved from DB

// Sort by chunk number
chunks.sort((a, b) => a.json.chunk_number - b.json.chunk_number);

// Merge transcriptions
const mergedText = chunks
  .map(chunk => chunk.json.transcription.text)
  .join(' ');

const totalDuration = chunks
  .reduce((sum, chunk) => sum + (chunk.json.transcription.duration || 0), 0);

// Merge word-level timestamps if available
const allWords = chunks
  .flatMap(chunk => chunk.json.transcription.words || []);

// Merge segments if available  
const allSegments = chunks
  .flatMap(chunk => chunk.json.transcription.segments || []);

return {
  original_file: chunks[0]?.json.original_file || 'unknown',
  total_chunks: chunks.length,
  merged_transcription: {
    text: mergedText,
    duration: totalDuration,
    words: allWords,
    segments: allSegments
  },
  chunks_processed: chunks.map(c => ({
    number: c.json.chunk_number,
    duration: c.json.transcription.duration,
    text_length: c.json.transcription.text.length
  })),
  timestamp: new Date().toISOString()
};