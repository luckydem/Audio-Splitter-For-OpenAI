# n8n Audio Transcription Workflow Guide

## Complete Setup Instructions - Step by Step

### Overview: The Complete Flow
```
Main Workflow 
  → Split Audio Sub-workflow (creates chunks)
    → Transcribe Audio Sub-workflow (transcribes all chunks)
      → Back to Main Workflow (with merged transcription)
```

### Visual Flow Diagram
```
┌─────────────────┐
│  Main Workflow  │ 
│                 │
│ 1. Google Drive │
│    Trigger      │
│ 2. Download     │
│    Audio File   │
└────────┬────────┘
         │ file_path: "audio.wma"
         ▼
┌─────────────────┐
│ Split Audio     │ ← YOU ONLY CHANGE THIS ONE!
│ Sub-workflow    │   - Add --stream flag
│                 │   - Update parser code
│ • Runs script   │
│ • Gets chunks   │
└────────┬────────┘
         │ Array of chunks
         ▼
┌─────────────────┐
│ Transcribe      │ ← NO CHANGES NEEDED
│ Sub-workflow    │
│                 │
│ • Loop chunks   │
│ • OpenAI API    │
│ • Merge text    │
└────────┬────────┘
         │ merged text + duration
         ▼
┌─────────────────┐
│  Main Workflow  │ ← NO CHANGES NEEDED
│  (continues)    │
│                 │
│ 4. GPT-4 Summary│
│ 5. Create Doc   │
│ 6. Log Results  │
└─────────────────┘
```

## RECOMMENDED SETUP: Minimal Changes, Maximum Performance

### Step 1: Update Your Split Audio Sub-workflow

1. **Open** your existing "Sub-Workflow: Split Audio" in n8n
2. **Find** the "Execute Audio Splitter Script" node
3. **Update** the command to add `--stream` flag:
   ```bash
   /home/demian/.n8n/scripts/.venv/bin/python /home/demian/.n8n/scripts/split_audio.py --input "/home/demian/.n8n/binaryData/{{ $json.file_path }}" --output "/tmp/" --stream
   ```

4. **Find** the "extract file paths" Code node
5. **Replace** the entire code with this parser that handles both formats:
   ```javascript
   // Enhanced parser supporting both streaming and legacy formats
   const scriptOutput = $('Execute Audio Splitter Script').first().json;
   
   if (!scriptOutput.stdout) {
     throw new Error('Audio splitter script produced no output');
   }
   
   const lines = scriptOutput.stdout.trim().split('\n').filter(line => line.trim());
   const chunks = [];
   
   for (const line of lines) {
     try {
       const data = JSON.parse(line);
       if (data.status === 'completed' && data.chunk_number) {
         chunks.push({
           filePath: data.output_path,
           fileName: data.output_path.split('/').pop(),
           chunkNumber: data.chunk_number,
           fileSizeMB: data.file_size_mb
         });
       }
     } catch (e) {
       if (line.includes('Exporting ')) {
         const path = line.replace('Exporting ', '').trim();
         if (path) {
           chunks.push({
             filePath: path,
             fileName: path.split('/').pop(),
             chunkNumber: parseInt(path.match(/chunk_(\d+)/)?.[1] || '0')
           });
         }
       }
     }
   }
   
   if (chunks.length === 0) {
     throw new Error('No audio chunks were created');
   }
   
   return chunks.map(chunk => ({ json: chunk }));
   ```

### Step 2: Keep Your Existing Transcribe Audio Sub-workflow

**No changes needed!** Your current transcribe workflow already:
- Receives all chunks
- Loops through them
- Transcribes each one
- Merges all transcriptions
- Returns the complete text

### Step 3: Your Main Workflow Stays the Same

**No changes needed!** The main workflow continues to:
1. Trigger on new audio files
2. Call Split Audio sub-workflow
3. Call Transcribe Audio sub-workflow  
4. Process the merged transcription with GPT-4
5. Create Google Doc and log results

## What Actually Changes with This Setup?

### Before (Sequential):
```
Split chunk 1 (30s) → Split chunk 2 (30s) → Split chunk 3 (30s)
Then: Transcribe 1 → Transcribe 2 → Transcribe 3
Total time: ~3 minutes
```

### After (Optimized):
```
Split ALL chunks (with streaming - 40s total for WMA→WAV)
Then: Transcribe 1, 2, 3 in PARALLEL via OpenAI
Total time: ~1 minute
```

## The Data Flow

1. **Main Workflow** sends to Split Audio:
   ```json
   {
     "file_path": "workflows/YVuRhb9uUg29QLmC/executions/40369/binary_data/audio.wma"
   }
   ```

2. **Split Audio** returns array of chunks:
   ```json
   [
     {"filePath": "/tmp/chunk_001.wav", "fileName": "chunk_001.wav", "chunkNumber": 1},
     {"filePath": "/tmp/chunk_002.wav", "fileName": "chunk_002.wav", "chunkNumber": 2},
     {"filePath": "/tmp/chunk_003.wav", "fileName": "chunk_003.wav", "chunkNumber": 3}
   ]
   ```

3. **Transcribe Audio** receives all chunks, processes them, returns:
   ```json
   {
     "text": "This is the complete merged transcription of all chunks...",
     "duration": 185.5
   }
   ```

4. **Main Workflow** continues with the merged text for GPT-4 processing

## Why This Works Better

1. **Smart Format Selection**: WMA files convert to WAV (5-10x faster than M4A on Pi)
2. **Streaming Output**: Chunks are available as soon as they're created
3. **Parallel Transcription**: OpenAI processes multiple chunks simultaneously
4. **No Workflow Redesign**: Just 2 small changes to one sub-workflow

## Troubleshooting

**If chunks are too large (>25MB):**
- The script now properly calculates WAV file sizes
- Uses 20% safety margin to ensure compliance

**If you see the old format output:**
- Make sure you added the `--stream` flag
- Check that the parser code was updated

**If transcription seems slow:**
- This is likely OpenAI API rate limits
- The splitting part should be much faster now

## Python Script Usage

### Basic Usage (current)
```bash
python split_audio.py --input file.wma --output /tmp/
```

### Optimized Usage (recommended)
```bash
python split_audio.py --input file.wma --output /tmp/ --stream
```

### JSON Output (for debugging)
```bash
python split_audio.py --input file.wma --output /tmp/ --output-json
```

## Performance Benefits

- **Auto Format Selection**: WMA→WAV (5-10x faster on Pi 4)
- **Streaming Output**: Chunks available immediately
- **Parallel Transcription**: Multiple chunks process simultaneously
- **25MB Compliance**: Proper chunk sizing for OpenAI limits

## File Locations

- **Workflows**: `/home/demian/.n8n/scripts/subworkflow_*.json`
- **Python Script**: `/home/demian/.n8n/scripts/split_audio.py`
- **Parsers**: 
  - `/home/demian/.n8n/scripts/n8n_parser_improved.js` (legacy)
  - `/home/demian/.n8n/scripts/n8n_parser_streaming.js` (new, supports all formats)