# Webhook Delivery Improvements

This document outlines the comprehensive webhook improvements implemented to resolve n8n integration issues and enhance reliability.

## Problem Analysis

The original webhook implementation had several critical issues:

1. **Basic Error Handling**: Only logged "Webhook failed: 404" without context
2. **No Retry Logic**: Single attempt with no fallback for temporary failures
3. **Minimal Logging**: No request details, response analysis, or debugging information
4. **n8n Resume URL Issues**: n8n resume URLs can expire, causing 404 errors
5. **No Timeout Handling**: Could hang indefinitely on slow responses

## Implemented Solutions

### 1. Enhanced Error Logging & Debugging

```python
# New comprehensive logging includes:
- Request URL and payload details
- Response status codes and body content
- Response headers and timing information
- Specific error categorization (404, timeout, connection errors)
- n8n URL pattern detection
```

### 2. Retry Logic with Exponential Backoff

```python
# Configurable retry system:
- Default: 3 attempts with exponential backoff (1s, 2s, 4s)
- Maximum backoff cap: 30 seconds
- Different handling for different error types
- Skip retries for permanent failures (some 404 cases)
```

### 3. Pre-delivery Connectivity Testing

```python
# Test webhook URL before sending payload:
- HEAD request to check endpoint availability
- DNS and connection validation
- Response time measurement
- Early detection of expired URLs
```

### 4. n8n Integration Improvements

```python
# n8n-specific enhancements:
- Automatic detection of n8n resume URLs
- Special handling for expired resume URLs
- Improved error messages for n8n debugging
- Timeout adjustments for n8n response patterns
```

### 5. Backup Webhook Support

```python
# Multiple webhook delivery options:
- Primary webhook URL (existing)
- Backup webhook URL (new)
- Automatic fallback if primary fails
- Independent retry logic for each
```

### 6. Webhook Status Tracking

```python
# Enhanced result tracking:
- webhook_delivered field in responses
- Success/failure logging
- Processing vs. delivery status separation
```

## New API Endpoints

### Test Webhook Connectivity
```http
GET /test-webhook?webhook_url=https://n8n.example.com/webhook/abc123
```

**Response:**
```json
{
  "url": "https://n8n.example.com/webhook/abc123",
  "is_n8n_url": true,
  "reachable": false,
  "response_time": null,
  "status_code": 404,
  "error": "Webhook URL returns 404 - may be expired or invalid",
  "recommendations": [
    "This appears to be an n8n webhook URL...",
    "404 error suggests the webhook endpoint doesn't exist..."
  ]
}
```

### Send Test Webhook
```http
POST /send-test-webhook?webhook_url=https://n8n.example.com/webhook/abc123
```

**Response:**
```json
{
  "webhook_url": "https://n8n.example.com/webhook/abc123",
  "success": true,
  "message": "Test webhook sent successfully",
  "payload": {
    "test": true,
    "message": "Test webhook from Audio Splitter",
    "timestamp": "2024-08-04T10:30:00",
    "service": "audio-splitter-drive"
  }
}
```

## Updated Request Format

The `DriveFileRequest` now supports backup webhooks:

```json
{
  "drive_file_id": "1ABC123...",
  "webhook_url": "https://n8n.example.com/webhook/primary",
  "backup_webhook_url": "https://n8n.example.com/webhook/backup",
  "notification_email": "user@example.com",
  "openai_api_key": "sk-..."
}
```

## Enhanced Response Format

Processing results now include webhook delivery status:

```json
{
  "job_id": "20240804103000_1ABC123",
  "status": "completed",
  "file_name": "meeting_recording.mp3",
  "transcription_text": "Meeting transcript...",
  "webhook_delivered": true,
  "processing_time_seconds": 45.2,
  "transcription_url": "https://storage.googleapis.com/..."
}
```

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. "Webhook failed: 404"
**Cause**: n8n resume URL has expired or workflow is not active
**Solution**: 
- Restart the n8n workflow to get a fresh resume URL
- Check workflow execution status in n8n
- Use the test webhook endpoint to verify URL validity

#### 2. "Connection timeout"
**Cause**: Network issues or n8n server overload
**Solution**:
- Check network connectivity
- Verify n8n server status
- Consider using backup webhook URL

#### 3. "n8n resume URL expired"
**Cause**: Long processing time exceeded n8n's resume URL TTL
**Solution**:
- Optimize processing to complete faster
- Use n8n's "Wait" node with longer timeout
- Implement polling instead of webhook for long processes

### Debugging Steps

1. **Test Connectivity First**:
   ```bash
   curl "https://your-service.com/test-webhook?webhook_url=YOUR_N8N_URL"
   ```

2. **Send Test Webhook**:
   ```bash
   curl -X POST "https://your-service.com/send-test-webhook?webhook_url=YOUR_N8N_URL"
   ```

3. **Check Cloud Run Logs**:
   ```bash
   gcloud logs read --service=your-service --limit=50
   ```

4. **Verify n8n Workflow**:
   - Check execution status in n8n UI
   - Verify workflow is not stuck or errored
   - Restart workflow if needed

## Best Practices

### For n8n Integration:

1. **Use Test Endpoints**: Always test webhook URLs before production use
2. **Set Appropriate Timeouts**: Allow sufficient time for audio processing
3. **Implement Backup URLs**: Use multiple webhook endpoints for reliability
4. **Monitor Workflow Status**: Check n8n executions for hanging workflows
5. **Handle Expiration**: Implement logic to handle expired resume URLs

### For Webhook Reliability:

1. **Enable Detailed Logging**: Monitor webhook delivery status
2. **Use Retry Logic**: The service now retries automatically
3. **Check Response Status**: Monitor webhook_delivered field in responses
4. **Implement Fallbacks**: Use backup webhooks or email notifications

## Configuration Options

### Environment Variables:
```bash
# Webhook timeout (default: 30 seconds)
WEBHOOK_TIMEOUT=30

# Maximum webhook retries (default: 3)
WEBHOOK_MAX_RETRIES=3

# Enable webhook connectivity testing (default: true)
WEBHOOK_TEST_CONNECTIVITY=true
```

### Request Parameters:
- `webhook_url`: Primary webhook endpoint
- `backup_webhook_url`: Fallback webhook endpoint
- `notification_email`: Email backup (future feature)

## Testing the Improvements

Run the test script to verify all improvements:

```bash
python test_webhook_improvements.py
```

This will test:
- n8n URL pattern detection
- Connectivity testing
- Retry logic
- Error handling
- Various failure scenarios

## Migration Guide

### For Existing n8n Workflows:

1. **No Breaking Changes**: Existing workflows continue to work
2. **Enhanced Logging**: Check logs for more detailed webhook information
3. **Add Backup Webhooks**: Optionally add backup_webhook_url to requests
4. **Monitor Delivery**: Check webhook_delivered field in responses

### For New Integrations:

1. **Use Test Endpoints**: Verify webhook URLs before processing
2. **Set Backup URLs**: Include backup_webhook_url in requests
3. **Handle Failures Gracefully**: Check webhook_delivered status
4. **Implement Polling**: Consider polling as backup for critical workflows

The webhook improvements provide comprehensive reliability enhancements while maintaining backward compatibility with existing n8n integrations.