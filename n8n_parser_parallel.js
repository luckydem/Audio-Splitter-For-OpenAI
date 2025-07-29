// Parser for TRUE parallel processing - emits each chunk as a separate item
// This allows n8n to process chunks immediately as they're created

const scriptOutput = $('Execute Audio Splitter Script').first().json;

// Check if the script executed successfully
if (!scriptOutput.stdout) {
  throw new Error('Audio splitter script produced no output');
}

// For parallel processing, we need to return each chunk as a separate item
// This way, n8n can process them individually as they arrive

const lines = scriptOutput.stdout.trim().split('\n').filter(line => line.trim());
const items = [];

for (const line of lines) {
  try {
    const data = JSON.parse(line);
    
    // Only process chunk completion events
    if (data.status === 'completed' && data.chunk_number) {
      items.push({
        json: {
          filePath: data.output_path,
          fileName: data.output_path.split('/').pop(),
          chunkNumber: data.chunk_number,
          fileSizeMB: data.file_size_mb,
          status: 'completed',
          // Add original file info for tracking
          originalFile: $('When Executed by Another Workflow').first().json.file_path
        }
      });
    }
  } catch (e) {
    // Handle legacy format
    if (line.includes('Exporting ')) {
      const path = line.replace('Exporting ', '').trim();
      if (path) {
        items.push({
          json: {
            filePath: path,
            fileName: path.split('/').pop(),
            chunkNumber: parseInt(path.match(/chunk_(\d+)/)?.[1] || '0'),
            status: 'completed',
            originalFile: $('When Executed by Another Workflow').first().json.file_path
          }
        });
      }
    }
  }
}

// Return items for parallel processing
// Each item will be processed separately by the next node
return items;