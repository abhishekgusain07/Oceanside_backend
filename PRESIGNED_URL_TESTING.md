# Pre-signed URL Testing Guide

This document explains how to test the newly implemented pre-signed URL functionality (Step 1 of the reliable upload architecture).

## What Was Implemented

✅ **Step 1: Pre-signed URL Generation (Backend)**

The following components have been implemented:

1. **New R2 Storage Service Methods:**
   - `generate_presigned_upload_url()` - Generates secure, time-limited upload URLs
   - `verify_upload()` - Verifies file existence and ETag after upload

2. **New API Endpoints:**
   - `POST /api/v1/recordings/generate-upload-url` - Generate pre-signed URLs
   - `POST /api/v1/recordings/confirm-upload` - Confirm and verify uploads

3. **New Schemas:**
   - `GenerateUploadUrlRequest` - Request schema for URL generation
   - `GenerateUploadUrlResponse` - Response schema with URL and metadata
   - `ConfirmUploadRequest` - Request schema for upload confirmation

4. **Comprehensive Tests:**
   - Unit tests for R2 storage service methods
   - Integration tests for API endpoints
   - Schema validation tests
   - Error handling tests

## Prerequisites

Before running the tests, ensure you have:

1. **Backend server running:** The development server should be running on `localhost:8000`
2. **R2 credentials configured:** Set up your Cloudflare R2 environment variables
3. **Database connection:** Ensure your database is accessible
4. **Python dependencies:** Install required packages

### Environment Variables

Make sure these R2 environment variables are set:

```bash
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET_NAME=riversideuploads
R2_ENDPOINT_URL=https://your_account_id.r2.cloudflarestorage.com
UPLOAD_URL_EXPIRATION_MINUTES=15
```

## Running the Tests

### 1. Automated Unit Tests

Run the comprehensive test suite:

```bash
cd backend
python -m pytest tests/test_presigned_urls.py -v
```

This will run:
- R2 storage service tests (mocked)
- API endpoint tests (mocked)
- Schema validation tests
- Error handling tests

### 2. Manual Integration Tests

Run the manual test script to test against a real running server:

```bash
cd backend
python test_presigned_urls_manual.py
```

This script will:
1. Create a test recording
2. Generate pre-signed URLs for multiple chunks
3. Simulate file uploads (without actually uploading to R2)
4. Test upload confirmation
5. Test error cases

### 3. Testing with Real R2 Upload (Optional)

If you want to test actual uploads to R2, you can modify the manual test script:

1. Edit `test_presigned_urls_manual.py`
2. In the `test_upload_to_presigned_url` method, uncomment the actual upload code:

```python
# Uncomment this line to perform real uploads:
# response = requests.put(presigned_url, data=dummy_data, headers=headers)
```

## API Usage Examples

### Generate Upload URL

```bash
curl -X POST "http://localhost:8000/api/v1/recordings/generate-upload-url" \
  -H "Content-Type: application/json" \
  -d '{
    "recording_id": "your-room-id-here",
    "chunk_index": 1,
    "content_type": "video/webm",
    "user_type": "host"
  }'
```

**Response:**
```json
{
  "pre_signed_url": "https://account_id.r2.cloudflarestorage.com/riversideuploads/uploads/room-id/user_user-id_chunk_1.webm?X-Amz-Algorithm=...",
  "file_path": "uploads/room-id/user_user-id_chunk_1.webm",
  "expires_in": 900,
  "expires_at": "2024-01-15T10:30:00Z"
}
```

### Upload to Pre-signed URL

```bash
curl -X PUT "pre_signed_url_from_above" \
  -H "Content-Type: video/webm" \
  --data-binary @your_video_chunk.webm
```

### Confirm Upload

```bash
curl -X POST "http://localhost:8000/api/v1/recordings/confirm-upload" \
  -H "Content-Type: application/json" \
  -d '{
    "recording_id": "your-room-id-here",
    "chunk_index": 1,
    "file_path": "uploads/room-id/user_user-id_chunk_1.webm",
    "etag": "etag-from-upload-response"
  }'
```

## Architecture Benefits

This implementation provides:

1. **Security:** Pre-signed URLs provide temporary, scoped access without exposing permanent credentials
2. **Scalability:** Direct uploads bypass your backend, reducing server load
3. **Reliability:** Upload verification ensures files are actually stored before proceeding
4. **Cost-effectiveness:** Reduces bandwidth costs on your server

## Next Steps

After successful testing of Step 1, you can proceed with:

- **Step 2:** Client-side upload logic with retry mechanisms
- **Step 3:** Upload confirmation and verification
- **Step 4:** Error handling and resume functionality
- **Step 5:** Triggering final video processing jobs

## Troubleshooting

### Common Issues

1. **"Recording not found" error:**
   - Make sure you've created a recording first using the create recording endpoint

2. **R2 credentials error:**
   - Verify your R2 environment variables are set correctly
   - Check that the R2 bucket exists and you have access

3. **URL generation fails:**
   - Check R2 service logs for detailed error messages
   - Verify boto3 is properly configured

4. **Upload verification fails:**
   - Ensure the file was actually uploaded to the correct path
   - Check that the ETag matches between upload response and verification request

### Debug Mode

To enable more detailed logging, set:

```bash
LOG_LEVEL=DEBUG
```

This will provide detailed logs for R2 operations and API requests.

## Testing Checklist

- [ ] Unit tests pass
- [ ] Manual test script runs successfully
- [ ] Can generate pre-signed URLs for different chunk indices
- [ ] Can generate URLs for different content types (video/webm, video/mp4, etc.)
- [ ] Upload confirmation works correctly
- [ ] Error cases are handled properly (non-existent recordings, invalid requests)
- [ ] URLs expire correctly after the specified time
- [ ] File path generation follows the expected pattern

## Implementation Details

### File Path Pattern

Files are stored using this pattern:
```
uploads/{recording_id}/user_{user_id}_chunk_{chunk_index}.{extension}
```

### URL Expiration

- Default expiration: 15 minutes (configurable via `UPLOAD_URL_EXPIRATION_MINUTES`)
- Recommendation: 5-15 minutes for production use

### Supported Content Types

- `video/webm`
- `video/mp4` 
- `audio/webm`
- `audio/mp4`

### Error Codes

- `404`: Recording not found
- `400`: Upload verification failed
- `422`: Invalid request schema
- `500`: Internal server error (R2 service issues) 