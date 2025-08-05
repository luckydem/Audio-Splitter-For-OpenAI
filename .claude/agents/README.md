# Claude Code Agents for DriveScribe Project

This directory contains specialized Claude Code agent configurations optimized for the DriveScribe audio transcription project.

## Available Agents

### 1. gcp-cloudrun-diagnostician 🟡
**File**: `gcp-cloudrun-diagnostician.md`
**Specialization**: Google Cloud Run log analysis and diagnostics

**Use when**:
- Analyzing Cloud Run service logs
- Diagnosing deployment issues
- Investigating performance problems
- Optimizing logging strategies

**Perfect for DriveScribe**:
- Monitoring `audio-transcriber-assemblyai` service health
- Diagnosing webhook delivery issues
- Analyzing GCS upload performance
- Troubleshooting AssemblyAI API integration problems

**Example usage**:
```
"My AssemblyAI transcriber service is returning 500 errors, can you check the logs and identify the issue?"
```

## Project-Specific Agent Usage

### For DriveScribe Services:

#### AssemblyAI Service Issues:
```
Use: gcp-cloudrun-diagnostician
Query: "Check logs for audio-transcriber-assemblyai service for authentication or API errors in the last 2 hours"
```

#### Deployment Problems:
```
Use: gcp-cloudrun-diagnostician  
Query: "The Cloud Build for audio-transcriber-assemblyai is failing, can you diagnose the issue?"
```

#### Performance Analysis:
```
Use: gcp-cloudrun-diagnostician
Query: "Analyze the performance of file uploads to GCS in the assemblyai service logs"
```

#### Webhook Issues:
```
Use: gcp-cloudrun-diagnostician
Query: "Check if there are any webhook delivery failures or timeout issues in the logs"
```

## Common Debugging Workflows

### 1. New Deployment Issues
1. **gcp-cloudrun-diagnostician** → Check build and deployment logs
2. Manual code review
3. **gcp-cloudrun-diagnostician** → Verify service startup and health

### 2. Production Service Issues  
1. **gcp-cloudrun-diagnostician** → Analyze recent error patterns
2. **gcp-cloudrun-diagnostician** → Check resource utilization
3. Manual fixes
4. **gcp-cloudrun-diagnostician** → Confirm resolution

### 3. Performance Optimization
1. **gcp-cloudrun-diagnostician** → Identify bottlenecks in logs
2. **gcp-cloudrun-diagnostician** → Analyze request patterns
3. Manual optimization
4. **gcp-cloudrun-diagnostician** → Compare before/after metrics

## Service-Specific Log Commands

### AssemblyAI Service:
```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="audio-transcriber-assemblyai" AND resource.labels.location="us-central1"' --limit=50 --format="table(timestamp,severity,textPayload)" --freshness=2h
```

### Legacy Whisper Service (if deployed):
```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="audio-splitter" AND resource.labels.location="us-central1"' --limit=50 --format="table(timestamp,severity,textPayload)" --freshness=2h
```

## Best Practices

### When to Use Agents:
✅ **DO use agents for**:
- Complex multi-step debugging
- Cross-service log correlation
- Performance analysis across time periods
- Root cause analysis of cascading failures

❌ **DON'T use agents for**:
- Simple single log lookups
- Basic health checks
- Quick status verification

### Effective Agent Queries:
1. **Be specific about the service**: Mention "audio-transcriber-assemblyai" or "whisper-chunking"
2. **Include time ranges**: "in the last 2 hours" or "since yesterday"
3. **Describe symptoms**: "returning 500 errors" or "webhook timeouts"
4. **Mention context**: "after deployment" or "during high load"

## Agent Configuration Details

### gcp-cloudrun-diagnostician Configuration:
- **Model**: Claude Sonnet
- **Color**: Yellow 🟡
- **Expertise**: GCP Cloud Run, logging, performance analysis
- **Tools**: Full access to all Claude Code tools
- **Specializations**:
  - Log pattern analysis
  - Resource utilization monitoring
  - Error correlation and root cause analysis
  - Performance optimization recommendations

## Integration with DriveScribe Architecture

The agents are specifically valuable for:

1. **AssemblyAI Integration Monitoring**:
   - API authentication issues
   - Webhook delivery problems
   - GCS upload failures
   - Signed URL generation errors

2. **Service Performance Analysis**:
   - Memory usage patterns (512MB limit)
   - Request processing times
   - Cold start frequency
   - Concurrent request handling

3. **Deployment Pipeline Issues**:
   - Cloud Build failures
   - Docker image problems
   - Environment variable issues
   - Service account permissions

## Future Agent Expansions

Consider adding specialized agents for:
- **assemblyai-api-specialist**: Deep AssemblyAI API expertise
- **n8n-integration-helper**: n8n workflow debugging
- **gcs-storage-optimizer**: Google Cloud Storage management

---

**Last Updated**: August 2025  
**Active Agents**: 1 (gcp-cloudrun-diagnostician)  
**Project Status**: Production Ready ✅