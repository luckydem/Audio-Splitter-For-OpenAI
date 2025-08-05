# Transcription Service Comparison for Long Audio Files (2-3 hours)

## Quick Summary Table

| Service | Cost per Hour | Max File Size | Max Duration | Speed | Accuracy | WMA Support |
|---------|--------------|---------------|--------------|-------|----------|-------------|
| **OpenAI Whisper API** | $0.36 | 25MB | ~2.5 hrs* | Fast (3-5 min/hr) | Excellent | ❌ Need conversion |
| **AssemblyAI** | $0.65 | 5GB | No limit | Fast (2-4 min/hr) | Excellent | ✅ Direct support |
| **AWS Transcribe** | $1.44 | 2GB | 4 hours | Medium (5-10 min/hr) | Very Good | ✅ Direct support |
| **Google Speech-to-Text** | $2.16 | 10GB | 8 hours | Medium (5-10 min/hr) | Very Good | ❌ Need conversion |
| **Rev.ai** | $1.50 | 2GB | 7.5 hours | Fast (2-5 min/hr) | Excellent | ✅ Direct support |
| **Deepgram** | $0.52 | 2GB | No limit | Very Fast (1-2 min/hr) | Very Good | ✅ Direct support |
| **Local Whisper** | $0 | Unlimited | Unlimited | Slow (30-120 min/hr) | Excellent | ✅ Via FFmpeg |

*With chunking workaround

## Detailed Analysis for Your Use Case

### Your Files:
- **250609_0051 BoD Mtg.WMA**: 30.4MB, 130 minutes
- **250621_0053 AGM.WMA**: 41MB, 172 minutes

---

## 1. **OpenAI Whisper API** (Current Implementation)
### Pros:
- Best accuracy for meeting transcription
- Excellent with accents and technical terms
- Good punctuation
- Supports 97+ languages

### Cons:
- Requires WMA → MP3/WAV conversion
- 25MB file limit requires chunking
- Chunking adds complexity

### Cost Calculation:
- 130 min file: $0.36/hr × 2.17 hrs = **$0.78**
- 172 min file: $0.36/hr × 2.87 hrs = **$1.03**

### Implementation:
```python
# Your current chunking approach
# Total time: ~10-15 minutes with parallel processing
```

---

## 2. **AssemblyAI** (Best Alternative)
### Pros:
- **Direct WMA support** - no conversion needed!
- 5GB file size limit
- Built-in speaker diarization
- Automatic chapters and summaries
- PII redaction available

### Cons:
- 80% more expensive than OpenAI
- Requires account setup

### Cost Calculation:
- 130 min file: $0.65/hr × 2.17 hrs = **$1.41**
- 172 min file: $0.65/hr × 2.87 hrs = **$1.87**

### Implementation:
```python
import assemblyai as aai
aai.settings.api_key = "your-key"

transcriber = aai.Transcriber()
transcript = transcriber.transcribe("250609_0051 BoD Mtg.WMA")
print(transcript.text)
```

---

## 3. **Deepgram** (Best Value + Speed)
### Pros:
- **Direct WMA support**
- Very fast processing
- Real-time streaming option
- Good accuracy
- Mid-range pricing

### Cons:
- Slightly less accurate than Whisper
- Less language support

### Cost Calculation:
- 130 min file: $0.52/hr × 2.17 hrs = **$1.13**
- 172 min file: $0.52/hr × 2.87 hrs = **$1.49**

### Implementation:
```python
from deepgram import Deepgram
dg = Deepgram("your-api-key")

with open("audio.wma", "rb") as audio:
    response = await dg.transcription.prerecorded(
        {"buffer": audio},
        {"punctuate": True, "utterances": True}
    )
```

---

## 4. **AWS Transcribe** (Enterprise Choice)
### Pros:
- **Direct WMA support**
- Speaker identification
- Custom vocabulary
- HIPAA compliant
- Batch processing discounts

### Cons:
- More complex setup
- Higher cost
- AWS account required

### Cost Calculation:
- 130 min file: $0.024/min × 130 = **$3.12**
- 172 min file: $0.024/min × 172 = **$4.13**

---

## 5. **Local Whisper** (Free but Slow)
### Pros:
- Completely free
- No file limits
- Privacy - runs locally
- Supports all formats via FFmpeg

### Cons:
- Requires GPU for reasonable speed
- 10-50x slower than cloud services
- High memory usage (5-10GB)

### Time Estimates (on CPU):
- 130 min file: **2-4 hours** processing
- 172 min file: **3-5 hours** processing

### Implementation:
```bash
# Install
pip install openai-whisper

# Run
whisper "250609_0051 BoD Mtg.WMA" --model large --language en
```

---

## Recommendations

### For Your Current Files:

1. **If WMA conversion is OK**: Continue with **OpenAI Whisper**
   - Best accuracy
   - Lowest cost
   - Already implemented

2. **If you want direct WMA support**: Use **AssemblyAI**
   - No conversion needed
   - Single API call
   - Extra features (diarization, summaries)

3. **Best balance**: **Deepgram**
   - Direct WMA support
   - Fast processing
   - Reasonable cost

### Decision Matrix:

| If you prioritize... | Choose... |
|---------------------|-----------|
| **Lowest cost** | OpenAI Whisper (with chunking) |
| **Simplicity** | AssemblyAI |
| **Speed** | Deepgram |
| **Privacy** | Local Whisper |
| **Enterprise features** | AWS Transcribe |

## Quick Start Commands

### Test with AssemblyAI (no chunking needed):
```bash
pip install assemblyai
export ASSEMBLYAI_API_KEY="your-key"
python -c "import assemblyai as aai; t=aai.Transcriber(); print(t.transcribe('250609_0051 BoD Mtg.WMA').text)"
```

### Test with Deepgram:
```bash
pip install deepgram-sdk
# Then use their Python SDK with your WMA file directly
```

## Cost Summary for Your Files

For both files (130 + 172 = 302 minutes):
- **OpenAI**: $1.81 (requires chunking)
- **Deepgram**: $2.62 (direct WMA)
- **AssemblyAI**: $3.28 (direct WMA + features)
- **AWS**: $7.25 (enterprise features)
- **Local**: $0 (but 5-9 hours processing)