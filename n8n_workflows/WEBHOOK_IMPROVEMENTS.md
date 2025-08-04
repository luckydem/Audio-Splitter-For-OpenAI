# n8n Webhook Integration Improvements

Based on research of n8n documentation and community best practices, here are the key improvements made to prevent webhook timeout issues.

## Problem Analysis

The original webhook 404 errors were caused by:

1. **No Wait Node Timeout**: The Wait node had no limit configured, causing indefinite waiting
2. **Resume URL Expiration**: n8n's resume URLs can become invalid if executions timeout or expire
3. **No Error Handling**: No fallback mechanism if webhook delivery fails
4. **Long Processing Times**: Audio transcription can take 3-5 minutes, exceeding some timeout thresholds

## n8n-Specific Findings

### Resume URL Behavior
- **No Fixed Expiration**: Resume URLs don't have a hard expiration time
- **Execution-Tied**: URLs remain valid as long as the workflow execution is active
- **64-Second Bug**: Known issue where webhook responses fail after 64+ seconds in Wait nodes
- **Execution Context**: Resume URLs change with partial executions

### Best Practices from n8n Documentation
- Configure timeout limits on Wait nodes to prevent indefinite waiting
- Keep webhook response times under 64 seconds when possible
- Use webhook suffixes for multiple Wait nodes
- Ensure resume URL is captured within same execution context

## Workflow Improvements Made

### 1. Added Timeout Limit to Wait Node

**Before:**
```json
{
  "parameters": {
    "resume": "webhook",
    "options": {
      "webhookSuffix": "transcription-complete"
    }
  }
}
```

**After:**
```json
{
  "parameters": {
    "resume": "webhook",
    "limit": true,
    "limitType": "afterTimeInterval", 
    "amount": 10,
    "unit": "minutes",
    "options": {
      "webhookSuffix": "transcription-complete"
    }
  }
}
```

**Benefits:**
- Workflow will automatically resume after 10 minutes even if webhook fails
- Prevents indefinite waiting
- Allows for retry logic or error handling
- Reasonable timeout for audio transcription processing

### 2. Webhook Suffix Configuration

The workflow uses `"webhookSuffix": "transcription-complete"` to:
- Create unique webhook URLs for this Wait node
- Avoid conflicts if multiple Wait nodes are used
- Provide clearer webhook identification in logs

## Cloud Run Service Improvements

The Cloud Run service has been enhanced with:

### Enhanced Webhook Delivery
- **Retry Logic**: 3 attempts with exponential backoff (1s, 2s, 4s)
- **Comprehensive Logging**: Detailed request/response logging for debugging
- **Timeout Handling**: 30-second timeout per webhook attempt
- **n8n URL Detection**: Special handling for n8n resume URLs

### New Testing Endpoints
- **`GET /test-webhook`**: Test webhook connectivity before processing
- **`POST /send-test-webhook`**: Send test payloads to verify webhook functionality

### Backup Webhook Support
- Support for primary and backup webhook URLs
- Automatic fallback if primary webhook fails
- Enhanced delivery tracking

## Usage Recommendations

### 1. Test Webhook Connectivity
Before processing files, test webhook connectivity:
```bash
curl "https://your-service.com/test-webhook?webhook_url=YOUR_N8N_RESUME_URL"
```

### 2. Configure Appropriate Timeouts
- **Small files (<25MB)**: 5-minute timeout sufficient
- **Large files (>25MB)**: 10-15 minute timeout recommended
- **Very large files**: Consider longer timeouts or batch processing

### 3. Monitor Webhook Delivery
The enhanced logging will show:
```
INFO:audio_splitter_drive:Webhook attempt 1/3 to n8n resume URL
INFO:audio_splitter_drive:✅ Webhook delivered successfully in 0.5s
```

Or for failures:
```
ERROR:audio_splitter_drive:❌ Webhook failed after 3 attempts: 404 Client Error
```

### 4. Handle Timeouts Gracefully
If the Wait node times out (10 minutes), consider:
- Checking Cloud Run logs for processing status
- Manually retrieving transcription from GCS bucket
- Implementing retry logic in subsequent workflow nodes

## Common Issues and Solutions

### Issue: "Webhook failed: 404"
**Cause**: n8n resume URL has expired or execution has timed out
**Solution**: 
- Reduce processing time where possible
- Increase Wait node timeout
- Implement backup webhook URLs

### Issue: "Wait node times out after 10 minutes"
**Cause**: Processing is taking longer than expected
**Solution**:
- Check Cloud Run logs for actual processing status
- Increase timeout to 15-20 minutes for large files
- Consider file size limits

### Issue: "Resume URL changes during execution"
**Cause**: Partial executions modify the resume URL
**Solution**: 
- Ensure webhook URL is captured in same execution as Wait node
- Use the "Store Job Info" node to preserve URLs

## Testing the Improved Workflow

1. **Import Updated Workflow**: Use the updated `audio_transcription_workflow_v2.json`
2. **Test with Small File**: Start with a file under 10MB to verify basic functionality
3. **Monitor Logs**: Watch both n8n execution logs and Cloud Run logs
4. **Test Timeout**: Try with larger files to verify timeout behavior
5. **Verify Error Handling**: Test with invalid webhook URLs to verify error handling

The combination of n8n timeout configuration and Cloud Run webhook improvements should resolve the webhook delivery issues and provide a more robust transcription workflow.