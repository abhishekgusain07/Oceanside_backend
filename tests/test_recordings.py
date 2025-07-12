"""
Unit tests for recording endpoints and functionality.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from app.main import app
from app.schemas.recording import GenerateUploadUrlRequest, ConfirmUploadRequest

client = TestClient(app)

class TestRecordingEndpoints:
    """Test recording API endpoints."""
    
    def test_health_check(self):
        """Test basic health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_create_recording_success(self):
        """Test successful recording creation."""
        recording_data = {
            "user_id": "test-user-123",
            "title": "Test Recording",
            "description": "Test description",
            "max_participants": 5
        }
        
        with patch('app.services.recording_service.RecordingService.create_recording') as mock_create:
            # Mock the recording object
            mock_recording = Mock()
            mock_recording.id = "rec-123"
            mock_recording.room_id = "room-456"
            mock_recording.host_user_id = "test-user-123"
            mock_recording.title = "Test Recording"
            mock_recording.description = "Test description"
            mock_recording.status = "pending"
            mock_recording.created_at = "2025-01-01T00:00:00"
            mock_recording.started_at = None
            mock_recording.ended_at = None
            mock_recording.processed_at = None
            mock_recording.video_url = None
            mock_recording.thumbnail_url = None
            mock_recording.duration_seconds = None
            mock_recording.max_participants = 5
            mock_recording.processing_attempts = 0
            
            mock_create.return_value = mock_recording
            
            response = client.post("/api/v1/recordings", json=recording_data)
            
            assert response.status_code == 201
            response_data = response.json()
            assert response_data["room_id"] == "room-456"
            assert response_data["title"] == "Test Recording"
    
    def test_create_recording_missing_user_id(self):
        """Test recording creation with missing user_id."""
        recording_data = {
            "title": "Test Recording"
            # Missing user_id
        }
        
        response = client.post("/api/v1/recordings", json=recording_data)
        assert response.status_code == 422  # Validation error
    
    def test_get_recording_success(self):
        """Test successful recording retrieval."""
        room_id = "room-456"
        
        with patch('app.services.recording_service.RecordingService.get_recording_by_room_id') as mock_get:
            # Mock the recording object
            mock_recording = Mock()
            mock_recording.id = "rec-123"
            mock_recording.room_id = room_id
            mock_recording.host_user_id = "test-user-123"
            mock_recording.title = "Test Recording"
            mock_recording.description = "Test description"
            mock_recording.status = "pending"
            mock_recording.created_at = "2025-01-01T00:00:00"
            mock_recording.started_at = None
            mock_recording.ended_at = None
            mock_recording.processed_at = None
            mock_recording.video_url = None
            mock_recording.thumbnail_url = None
            mock_recording.duration_seconds = None
            mock_recording.max_participants = 5
            mock_recording.processing_attempts = 0
            
            mock_get.return_value = mock_recording
            
            response = client.get(f"/api/v1/recordings/{room_id}")
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["room_id"] == room_id
            assert response_data["title"] == "Test Recording"
    
    def test_get_recording_not_found(self):
        """Test recording retrieval for non-existent recording."""
        room_id = "non-existent"
        
        with patch('app.services.recording_service.RecordingService.get_recording_by_room_id') as mock_get:
            mock_get.return_value = None
            
            response = client.get(f"/api/v1/recordings/{room_id}")
            assert response.status_code == 404
    
    def test_generate_guest_token_success(self):
        """Test successful guest token generation."""
        room_id = "room-456"
        
        with patch('app.services.recording_service.RecordingService.get_recording_by_room_id') as mock_get_recording, \
             patch('app.services.recording_service.RecordingService.generate_guest_token') as mock_generate_token:
            
            # Mock recording exists
            mock_recording = Mock()
            mock_recording.id = "rec-123"
            mock_get_recording.return_value = mock_recording
            
            # Mock token generation
            mock_generate_token.return_value = "guest-token-789"
            
            response = client.post(f"/api/v1/recordings/{room_id}/guest-token")
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["token"] == "guest-token-789"
    
    def test_generate_upload_url_success(self):
        """Test successful pre-signed URL generation."""
        with patch('app.services.recording_service.RecordingService.get_recording_by_room_id') as mock_get_recording, \
             patch('app.services.r2_storage.r2_storage.generate_presigned_upload_url') as mock_generate_url:
            
            # Mock recording exists
            mock_recording = Mock()
            mock_recording.id = "rec-123"
            mock_recording.host_user_id = "user-123"
            mock_get_recording.return_value = mock_recording
            
            # Mock presigned URL generation
            mock_generate_url.return_value = {
                'pre_signed_url': 'https://r2.example.com/uploads/room-456/host_chunk_1.webm?signature=xyz',
                'file_path': 'uploads/room-456/host_chunk_1.webm',
                'expires_in': 900,
                'expires_at': '2025-01-01T01:00:00Z'
            }
            
            request_data = {
                "recording_id": "room-456",
                "chunk_index": 1,
                "content_type": "video/webm",
                "user_type": "host"
            }
            
            response = client.post("/api/v1/recordings/generate-upload-url", json=request_data)
            
            assert response.status_code == 200
            response_data = response.json()
            assert "pre_signed_url" in response_data
            assert response_data["file_path"] == "uploads/room-456/host_chunk_1.webm"
    
    def test_generate_upload_url_recording_not_found(self):
        """Test pre-signed URL generation for non-existent recording."""
        with patch('app.services.recording_service.RecordingService.get_recording_by_room_id') as mock_get_recording:
            mock_get_recording.return_value = None
            
            request_data = {
                "recording_id": "non-existent",
                "chunk_index": 1,
                "content_type": "video/webm", 
                "user_type": "host"
            }
            
            response = client.post("/api/v1/recordings/generate-upload-url", json=request_data)
            assert response.status_code == 404
    
    def test_confirm_upload_success(self):
        """Test successful upload confirmation."""
        with patch('app.services.recording_service.RecordingService.get_recording_by_room_id') as mock_get_recording, \
             patch('app.services.r2_storage.r2_storage.verify_upload') as mock_verify, \
             patch('app.tasks.video_processing.process_video.delay') as mock_task:
            
            # Mock recording exists
            mock_recording = Mock()
            mock_recording.id = "rec-123"
            mock_get_recording.return_value = mock_recording
            
            # Mock upload verification
            mock_verify.return_value = True
            
            # Mock task creation
            mock_task.return_value = Mock(id="task-123")
            
            request_data = {
                "recording_id": "room-456",
                "chunk_index": 1,
                "file_path": "uploads/room-456/host_chunk_1.webm",
                "etag": "abc123",
                "user_type": "host"
            }
            
            response = client.post("/api/v1/recordings/confirm-upload", json=request_data)
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["message"] == "Upload confirmed successfully"
            assert response_data["verified"] == True
    
    def test_confirm_upload_verification_failed(self):
        """Test upload confirmation with failed verification."""
        with patch('app.services.recording_service.RecordingService.get_recording_by_room_id') as mock_get_recording, \
             patch('app.services.r2_storage.r2_storage.verify_upload') as mock_verify:
            
            # Mock recording exists
            mock_recording = Mock()
            mock_recording.id = "rec-123"
            mock_get_recording.return_value = mock_recording
            
            # Mock upload verification failure
            mock_verify.return_value = False
            
            request_data = {
                "recording_id": "room-456",
                "chunk_index": 1,
                "file_path": "uploads/room-456/host_chunk_1.webm",
                "etag": "abc123",
                "user_type": "host"
            }
            
            response = client.post("/api/v1/recordings/confirm-upload", json=request_data)
            assert response.status_code == 400
    
    def test_turn_credentials(self):
        """Test TURN credentials endpoint."""
        response = client.get("/api/v1/recordings/turn-credentials")
        
        assert response.status_code == 200
        response_data = response.json()
        assert "urls" in response_data
        assert "username" in response_data
        assert "credential" in response_data

class TestR2Storage:
    """Test R2 storage service functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_presigned_url_success(self):
        """Test successful presigned URL generation."""
        from app.services.r2_storage import R2StorageService
        
        # Initialize with test mode
        storage = R2StorageService(skip_validation=True)
        
        result = await storage.generate_presigned_upload_url(
            recording_id="room-456",
            chunk_index=1,
            content_type="video/webm",
            user_type="host",
            user_id="user-123"
        )
        
        assert result is not None
        assert "pre_signed_url" in result
        assert "file_path" in result
        assert result["file_path"] == "uploads/room-456/user_user-123_chunk_1.webm"
    
    @pytest.mark.asyncio
    async def test_verify_upload_test_mode(self):
        """Test upload verification in test mode."""
        from app.services.r2_storage import R2StorageService
        
        # Initialize with test mode
        storage = R2StorageService(skip_validation=True)
        
        result = await storage.verify_upload(
            file_path="uploads/room-456/host_chunk_1.webm",
            expected_etag="abc123"
        )
        
        # In test mode, should always return True
        assert result == True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])