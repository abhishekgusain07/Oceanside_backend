"""
Tests for pre-signed URL generation functionality.

Tests cover:
1. R2 storage service pre-signed URL generation
2. Generate upload URL endpoint
3. Confirm upload endpoint
4. Error handling and edge cases
"""
import pytest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import FastAPI
from app.api.router import api_router
from app.core.config import settings
from app.services.r2_storage import R2StorageService
from app.schemas.recording import GenerateUploadUrlRequest, ConfirmUploadRequest
from app.models.recording import Recording
from app.services.recording_service import RecordingService


class TestR2StorageService:
    """Test R2 storage service pre-signed URL functionality."""
    
    @pytest.fixture
    def mock_r2_client(self):
        """Mock boto3 R2 client."""
        with patch('boto3.client') as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance
            yield mock_instance
    
    @pytest.fixture
    def r2_service(self, mock_r2_client):
        """Create R2 storage service with mocked client."""
        with patch('app.services.r2_storage.settings') as mock_settings:
            mock_settings.R2_ACCESS_KEY_ID = "test_key"
            mock_settings.R2_SECRET_ACCESS_KEY = "test_secret"
            mock_settings.R2_ENDPOINT_URL = "https://test.r2.cloudflarestorage.com"
            mock_settings.R2_BUCKET_NAME = "test-bucket"
            mock_settings.R2_PUBLIC_URL_BASE = "https://pub-test.r2.dev"
            
            service = R2StorageService()
            service.client = mock_r2_client
            return service
    
    @pytest.mark.asyncio
    async def test_generate_presigned_upload_url_success(self, r2_service, mock_r2_client):
        """Test successful pre-signed URL generation."""
        # Mock the generate_presigned_url method
        expected_url = "https://test.r2.cloudflarestorage.com/test-bucket/uploads/test-recording/user_test-user_chunk_1.webm?signed=true"
        mock_r2_client.generate_presigned_url.return_value = expected_url
        
        result = await r2_service.generate_presigned_upload_url(
            recording_id="test-recording",
            chunk_index=1,
            content_type="video/webm",
            user_type="host",
            user_id="test-user",
            expires_in_minutes=15
        )
        
        assert result is not None
        assert result['pre_signed_url'] == expected_url
        assert result['file_path'] == "uploads/test-recording/user_test-user_chunk_1.webm"
        assert result['expires_in'] == 900  # 15 minutes in seconds
        assert isinstance(result['expires_at'], datetime)
        
        # Verify the client method was called with correct parameters
        mock_r2_client.generate_presigned_url.assert_called_once_with(
            'put_object',
            Params={
                'Bucket': 'test-bucket',
                'Key': 'uploads/test-recording/user_test-user_chunk_1.webm',
                'ContentType': 'video/webm'
            },
            ExpiresIn=900
        )
    
    @pytest.mark.asyncio
    async def test_generate_presigned_upload_url_without_user_id(self, r2_service, mock_r2_client):
        """Test pre-signed URL generation without user_id."""
        expected_url = "https://test.r2.cloudflarestorage.com/test-bucket/uploads/test-recording/host_chunk_2.mp4?signed=true"
        mock_r2_client.generate_presigned_url.return_value = expected_url
        
        result = await r2_service.generate_presigned_upload_url(
            recording_id="test-recording",
            chunk_index=2,
            content_type="video/mp4",
            user_type="host",
            user_id=None,
            expires_in_minutes=10
        )
        
        assert result is not None
        assert result['file_path'] == "uploads/test-recording/host_chunk_2.mp4"
        assert result['expires_in'] == 600  # 10 minutes in seconds
    
    @pytest.mark.asyncio
    async def test_generate_presigned_upload_url_error_handling(self, r2_service, mock_r2_client):
        """Test error handling in pre-signed URL generation."""
        # Mock client to raise an exception
        mock_r2_client.generate_presigned_url.side_effect = Exception("R2 service unavailable")
        
        result = await r2_service.generate_presigned_upload_url(
            recording_id="test-recording",
            chunk_index=1,
            content_type="video/webm"
        )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_verify_upload_success(self, r2_service, mock_r2_client):
        """Test successful upload verification."""
        # Mock head_object response
        mock_r2_client.head_object.return_value = {
            'ETag': '"test-etag-123"',
            'ContentLength': 1024
        }
        
        result = await r2_service.verify_upload(
            file_path="uploads/test-recording/chunk_1.webm",
            expected_etag="test-etag-123"
        )
        
        assert result is True
        mock_r2_client.head_object.assert_called_once_with(
            Bucket='test-bucket',
            Key='uploads/test-recording/chunk_1.webm'
        )
    
    @pytest.mark.asyncio
    async def test_verify_upload_etag_mismatch(self, r2_service, mock_r2_client):
        """Test upload verification with ETag mismatch."""
        mock_r2_client.head_object.return_value = {
            'ETag': '"different-etag"',
            'ContentLength': 1024
        }
        
        result = await r2_service.verify_upload(
            file_path="uploads/test-recording/chunk_1.webm",
            expected_etag="expected-etag"
        )
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_verify_upload_file_not_found(self, r2_service, mock_r2_client):
        """Test upload verification when file doesn't exist."""
        from botocore.exceptions import ClientError
        
        # Mock 404 error
        error = ClientError(
            error_response={'Error': {'Code': '404', 'Message': 'Not Found'}},
            operation_name='HeadObject'
        )
        mock_r2_client.head_object.side_effect = error
        
        result = await r2_service.verify_upload(
            file_path="uploads/test-recording/nonexistent.webm"
        )
        
        assert result is False


class TestPresignedUrlEndpoints:
    """Test pre-signed URL endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        # Create a FastAPI app directly (without SocketIO wrapper)
        from app.main import create_application
        from app.api.socketio_server import sio
        import socketio
        
        # We need to create the app without the SocketIO wrapper for testing
        from app.core.logging import configure_logging
        from app.core.config import settings
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from app.api.router import api_router
        
        configure_logging()
        
        app = FastAPI(
            title=settings.PROJECT_NAME,
            description=settings.PROJECT_DESCRIPTION,
            version=settings.VERSION,
            debug=settings.DEBUG,
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Include API router
        app.include_router(api_router, prefix=settings.API_V1_STR)
        
        return TestClient(app)
    
    @pytest.fixture
    def mock_recording(self):
        """Mock recording object."""
        recording = Mock(spec=Recording)
        recording.id = str(uuid.uuid4())
        recording.room_id = "test-room-123"
        recording.host_user_id = "test-user-456"
        recording.title = "Test Recording"
        recording.status = "created"
        recording.created_at = datetime.now(timezone.utc)
        return recording
    
    @pytest.mark.asyncio
    async def test_generate_upload_url_success(self, client, mock_recording):
        """Test successful upload URL generation endpoint."""
        request_data = {
            "recording_id": "test-room-123",
            "chunk_index": 1,
            "content_type": "video/webm",
            "user_type": "host"
        }
        
        with patch('app.api.endpoints.recordings.RecordingService') as mock_service_class, \
             patch('app.services.r2_storage.r2_storage') as mock_r2_storage, \
             patch('app.api.endpoints.recordings.get_db') as mock_get_db:
            
            # Mock database session
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db
            
            # Mock recording service
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.get_recording_by_room_id.return_value = mock_recording
            
            # Mock R2 storage service
            mock_r2_storage.generate_presigned_upload_url = AsyncMock(return_value={
                'pre_signed_url': 'https://test.r2.cloudflarestorage.com/signed-url',
                'file_path': 'uploads/test-room-123/user_test-user-456_chunk_1.webm',
                'expires_in': 900,
                'expires_at': datetime.now(timezone.utc) + timedelta(minutes=15)
            })
            
            response = client.post("/api/recordings/generate-upload-url", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            assert 'pre_signed_url' in data
            assert 'file_path' in data
            assert 'expires_in' in data
            assert 'expires_at' in data
            assert data['expires_in'] == 900
    
    @pytest.mark.asyncio
    async def test_generate_upload_url_recording_not_found(self, client):
        """Test upload URL generation when recording doesn't exist."""
        request_data = {
            "recording_id": "nonexistent-room",
            "chunk_index": 1,
            "content_type": "video/webm",
            "user_type": "host"
        }
        
        with patch('app.api.endpoints.recordings.RecordingService') as mock_service_class, \
             patch('app.api.endpoints.recordings.get_db') as mock_get_db:
            
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db
            
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.get_recording_by_room_id.return_value = None
            
            response = client.post("/api/recordings/generate-upload-url", json=request_data)
            
            assert response.status_code == 404
            assert "Recording not found" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_generate_upload_url_r2_service_failure(self, client, mock_recording):
        """Test upload URL generation when R2 service fails."""
        request_data = {
            "recording_id": "test-room-123",
            "chunk_index": 1,
            "content_type": "video/webm",
            "user_type": "host"
        }
        
        with patch('app.api.endpoints.recordings.RecordingService') as mock_service_class, \
             patch('app.services.r2_storage.r2_storage') as mock_r2_storage, \
             patch('app.api.endpoints.recordings.get_db') as mock_get_db:
            
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db
            
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.get_recording_by_room_id.return_value = mock_recording
            
            # Mock R2 service failure
            mock_r2_storage.generate_presigned_upload_url = AsyncMock(return_value=None)
            
            response = client.post("/api/recordings/generate-upload-url", json=request_data)
            
            assert response.status_code == 500
            assert "Failed to generate upload URL" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_confirm_upload_success(self, client, mock_recording):
        """Test successful upload confirmation."""
        request_data = {
            "recording_id": "test-room-123",
            "chunk_index": 1,
            "file_path": "uploads/test-room-123/chunk_1.webm",
            "etag": "test-etag-123"
        }
        
        with patch('app.api.endpoints.recordings.RecordingService') as mock_service_class, \
             patch('app.services.r2_storage.r2_storage') as mock_r2_storage, \
             patch('app.api.endpoints.recordings.get_db') as mock_get_db:
            
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db
            
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.get_recording_by_room_id.return_value = mock_recording
            
            # Mock successful verification
            mock_r2_storage.verify_upload = AsyncMock(return_value=True)
            
            response = client.post("/api/recordings/confirm-upload", json=request_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Upload confirmed successfully"
            assert data["recording_id"] == "test-room-123"
            assert data["chunk_index"] == 1
            assert data["verified"] is True
    
    @pytest.mark.asyncio
    async def test_confirm_upload_verification_failed(self, client, mock_recording):
        """Test upload confirmation when verification fails."""
        request_data = {
            "recording_id": "test-room-123",
            "chunk_index": 1,
            "file_path": "uploads/test-room-123/chunk_1.webm",
            "etag": "test-etag-123"
        }
        
        with patch('app.api.endpoints.recordings.RecordingService') as mock_service_class, \
             patch('app.services.r2_storage.r2_storage') as mock_r2_storage, \
             patch('app.api.endpoints.recordings.get_db') as mock_get_db:
            
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db
            
            mock_service = AsyncMock()
            mock_service_class.return_value = mock_service
            mock_service.get_recording_by_room_id.return_value = mock_recording
            
            # Mock failed verification
            mock_r2_storage.verify_upload = AsyncMock(return_value=False)
            
            response = client.post("/api/recordings/confirm-upload", json=request_data)
            
            assert response.status_code == 400
            assert "Upload verification failed" in response.json()["detail"]


class TestPresignedUrlSchemas:
    """Test pre-signed URL request/response schemas."""
    
    def test_generate_upload_url_request_valid(self):
        """Test valid GenerateUploadUrlRequest."""
        request = GenerateUploadUrlRequest(
            recording_id="test-recording-123",
            chunk_index=5,
            content_type="video/webm",
            user_type="host"
        )
        
        assert request.recording_id == "test-recording-123"
        assert request.chunk_index == 5
        assert request.content_type == "video/webm"
        assert request.user_type == "host"
    
    def test_generate_upload_url_request_invalid_content_type(self):
        """Test GenerateUploadUrlRequest with invalid content type."""
        with pytest.raises(ValueError, match="content_type must be one of"):
            GenerateUploadUrlRequest(
                recording_id="test-recording-123",
                chunk_index=1,
                content_type="image/png",  # Invalid content type
                user_type="host"
            )
    
    def test_generate_upload_url_request_negative_chunk_index(self):
        """Test GenerateUploadUrlRequest with negative chunk index."""
        with pytest.raises(ValueError):
            GenerateUploadUrlRequest(
                recording_id="test-recording-123",
                chunk_index=-1,  # Invalid chunk index
                content_type="video/webm",
                user_type="host"
            )
    
    def test_confirm_upload_request_valid(self):
        """Test valid ConfirmUploadRequest."""
        request = ConfirmUploadRequest(
            recording_id="test-recording-123",
            chunk_index=3,
            file_path="uploads/test-recording-123/chunk_3.webm",
            etag="test-etag-456"
        )
        
        assert request.recording_id == "test-recording-123"
        assert request.chunk_index == 3
        assert request.file_path == "uploads/test-recording-123/chunk_3.webm"
        assert request.etag == "test-etag-456"


if __name__ == "__main__":
    pytest.main([__file__]) 