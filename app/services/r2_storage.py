"""
Cloudflare R2 Storage Service for handling video chunk uploads and downloads.
"""
import logging
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from typing import Optional, Dict, Any, List
import tempfile
import os
from datetime import datetime, timedelta, timezone
from app.core.config import settings

logger = logging.getLogger(__name__)


class R2StorageService:
    """Service for interacting with Cloudflare R2 storage."""
    
    def __init__(self, skip_validation: bool = False):
        """Initialize R2 storage client."""
        self.bucket_name = settings.R2_BUCKET_NAME
        self.endpoint_url = settings.R2_ENDPOINT_URL
        self.public_url_base = settings.R2_PUBLIC_URL_BASE
        self.riverside_prefix = settings.RIVERSIDE_PATH_PREFIX
        self.client = None
        self.is_test_mode = False
        
        # Skip validation during testing
        if skip_validation:
            logger.info("⚠️ R2 client initialized in test mode (validation skipped)")
            self.is_test_mode = True
            return
        
        # Validate required settings
        missing_vars = []
        if not settings.R2_ACCESS_KEY_ID:
            missing_vars.append("R2_ACCESS_KEY_ID")
        if not settings.R2_SECRET_ACCESS_KEY:
            missing_vars.append("R2_SECRET_ACCESS_KEY")
        if not settings.R2_ENDPOINT_URL:
            missing_vars.append("R2_ENDPOINT_URL")
        
        if missing_vars:
            error_msg = f"Missing required R2 environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Initialize boto3 client for R2
        try:
            self.client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name='auto'  # R2 uses 'auto' as region
            )
            
            # Test the connection by listing buckets
            try:
                response = self.client.list_buckets()
                logger.info(f"✅ R2 client initialized successfully. Found {len(response.get('Buckets', []))} buckets")
                logger.info(f"✅ Using bucket: {self.bucket_name}")
            except Exception as test_error:
                logger.warning(f"⚠️ R2 client initialized but connection test failed: {str(test_error)}")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize R2 client: {str(e)}")
            logger.error("Please check your R2 credentials and endpoint URL")
            raise
        
    async def generate_presigned_upload_url(
        self,
        recording_id: str,
        chunk_index: int,
        content_type: str = "video/webm",
        user_type: str = "host",
        user_id: Optional[str] = None,
        expires_in_minutes: int = 15
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a pre-signed URL for uploading a chunk directly to R2.
        
        Args:
            recording_id: The ID of the overall recording session
            chunk_index: The sequential number of the chunk (e.g., 1, 2, 3...)
            content_type: The MIME type of the file (e.g., video/webm)
            user_type: Type of user (host or guest)
            user_id: ID of the user (for path construction)
            expires_in_minutes: URL expiration time in minutes (default 15)
            
        Returns:
            Dict containing pre_signed_url, file_path, expires_in, expires_at
            None if generation fails
        """
        try:
            # Construct the object key (file path) with riverside prefix
            # Format: riverside/uploads/{recording_id}/user_{user_id}_chunk_{chunk_index}.webm
            # Or if no user_id: riverside/uploads/{recording_id}/{user_type}_chunk_{chunk_index}.webm
            file_extension = content_type.split('/')[-1] if '/' in content_type else 'webm'
            
            if user_id:
                file_path = f"{self.riverside_prefix}/uploads/{recording_id}/user_{user_id}_chunk_{chunk_index}.{file_extension}"
            else:
                file_path = f"{self.riverside_prefix}/uploads/{recording_id}/{user_type}_chunk_{chunk_index}.{file_extension}"
            
            # Calculate expiration time
            expires_in_seconds = expires_in_minutes * 60
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
            
            # Handle test mode where client is None
            if self.is_test_mode or self.client is None:
                logger.warning("⚠️ R2 client in test mode, returning mock pre-signed URL")
                return {
                    'pre_signed_url': f"https://mock-r2-endpoint.com/{self.bucket_name}/{file_path}?mock=true",
                    'file_path': file_path,
                    'expires_in': expires_in_seconds,
                    'expires_at': expires_at
                }
            
            # Generate pre-signed URL for PUT operation
            presigned_url = self.client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': file_path,
                    'ContentType': content_type
                },
                ExpiresIn=expires_in_seconds
            )
            
            logger.info(f"✅ Generated pre-signed URL for {file_path}, expires at {expires_at}")
            
            return {
                'pre_signed_url': presigned_url,
                'file_path': file_path,
                'expires_in': expires_in_seconds,
                'expires_at': expires_at
            }
            
        except Exception as e:
            logger.error(f"Failed to generate pre-signed URL: {str(e)}")
            return None

    async def verify_upload(self, file_path: str, expected_etag: Optional[str] = None) -> bool:
        """
        Verify that a file exists in R2 storage and optionally check its ETag.
        
        Args:
            file_path: The object key/path of the file in R2
            expected_etag: Expected ETag for verification (optional)
            
        Returns:
            bool: True if file exists (and ETag matches if provided), False otherwise
        """
        try:
            # Handle test mode where client is None
            if self.is_test_mode or self.client is None:
                logger.warning("⚠️ R2 client in test mode, simulating upload verification")
                # In test mode, always return True for verification
                # unless we're specifically testing failure scenarios
                return True
            
            # Use head_object to check if file exists without downloading it
            response = self.client.head_object(Bucket=self.bucket_name, Key=file_path)
            
            # Check ETag if provided
            if expected_etag:
                actual_etag = response.get('ETag', '').strip('"')
                expected_etag = expected_etag.strip('"')
                
                if actual_etag != expected_etag:
                    logger.warning(f"ETag mismatch for {file_path}: expected {expected_etag}, got {actual_etag}")
                    return False
            
            logger.info(f"✅ Verified upload exists in R2: {file_path}")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.warning(f"File not found in R2: {file_path}")
            else:
                logger.error(f"Error verifying upload in R2: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Failed to verify upload in R2: {str(e)}")
            return False
    
    async def upload_chunk(
        self, 
        file_content: bytes, 
        room_id: str, 
        user_type: str, 
        chunk_name: str
    ) -> Optional[str]:
        """
        Upload a video chunk to R2 storage.
        
        Args:
            file_content: Binary content of the chunk file
            room_id: Room ID for the recording
            user_type: Type of user ("host" or "guest")
            chunk_name: Name of the chunk file
            
        Returns:
            str: R2 object key if successful, None if failed
        """
        try:
            # Construct the R2 object key with riverside prefix
            object_key = f"{self.riverside_prefix}/{room_id}/{user_type}/{chunk_name}"
            
            # Handle test mode where client is None
            if self.client is None:
                logger.warning(f"⚠️ R2 client not initialized (test mode), simulating chunk upload for {object_key}")
                return object_key
            
            # Upload to R2
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=file_content,
                ContentType='video/webm'
            )
            
            logger.info(f"✅ Chunk uploaded to R2: {object_key}")
            return object_key
            
        except Exception as e:
            logger.error(f"Failed to upload chunk to R2: {str(e)}")
            return None
    
    async def upload_metadata(
        self, 
        metadata_content: str, 
        room_id: str, 
        user_type: str
    ) -> Optional[str]:
        """
        Upload metadata file to R2 storage.
        
        Args:
            metadata_content: Text content of the metadata file
            room_id: Room ID for the recording
            user_type: Type of user ("host" or "guest")
            
        Returns:
            str: R2 object key if successful, None if failed
        """
        try:
            # Construct the R2 object key for metadata with riverside prefix
            object_key = f"{self.riverside_prefix}/{room_id}/{user_type}/{user_type}.txt"
            
            # Handle test mode where client is None
            if self.client is None:
                logger.warning(f"⚠️ R2 client not initialized (test mode), simulating metadata upload for {object_key}")
                return object_key
            
            # Upload metadata to R2
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=metadata_content.encode('utf-8'),
                ContentType='text/plain'
            )
            
            logger.info(f"✅ Metadata uploaded to R2: {object_key}")
            return object_key
            
        except Exception as e:
            logger.error(f"Failed to upload metadata to R2: {str(e)}")
            return None
    
    async def download_chunk(self, object_key: str, local_path: str) -> bool:
        """
        Download a chunk from R2 to local file.
        
        Args:
            object_key: R2 object key
            local_path: Local file path to save the chunk
            
        Returns:
            bool: True if successful, False if failed
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Handle test mode where client is None
            if self.client is None:
                logger.warning(f"⚠️ R2 client not initialized (test mode), simulating chunk download for {object_key}")
                # Create an empty file for testing
                with open(local_path, 'wb') as f:
                    f.write(b'mock video data')
                return True
            
            # Download from R2
            self.client.download_file(self.bucket_name, object_key, local_path)
            
            logger.info(f"✅ Downloaded chunk from R2: {object_key} -> {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download chunk from R2: {str(e)}")
            return False
    
    async def download_metadata(self, room_id: str, user_type: str) -> Optional[str]:
        """
        Download metadata file content from R2.
        
        Args:
            room_id: Room ID for the recording
            user_type: Type of user ("host" or "guest")
            
        Returns:
            str: Metadata content if successful, None if failed
        """
        try:
            object_key = f"{self.riverside_prefix}/{room_id}/{user_type}/{user_type}.txt"
            
            response = self.client.get_object(Bucket=self.bucket_name, Key=object_key)
            content = response['Body'].read().decode('utf-8')
            
            logger.info(f"✅ Downloaded metadata from R2: {object_key}")
            return content
            
        except Exception as e:
            logger.error(f"Failed to download metadata from R2: {str(e)}")
            return None
    
    async def list_chunks(self, room_id: str, user_type: str) -> List[str]:
        """
        List all chunk files for a room and user type.
        Updated to work with new pre-signed URL path format.
        
        Args:
            room_id: Room ID for the recording
            user_type: Type of user ("host" or "guest")
            
        Returns:
            List[str]: List of R2 object keys for chunks
        """
        try:
            # New path format with riverside prefix: riverside/uploads/{recording_id}/user_{user_id}_chunk_{chunk_index}.webm
            # OR: riverside/uploads/{recording_id}/{user_type}_chunk_{chunk_index}.webm
            prefix = f"{self.riverside_prefix}/uploads/{room_id}/"
            
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                # Try the old path format for backward compatibility
                logger.info(f"No chunks found with new path format, trying old format...")
                return await self._list_chunks_old_format(room_id, user_type)
            
            # Filter chunks by user type and file extension
            chunks = []
            for obj in response['Contents']:
                key = obj['Key']
                filename = key.split('/')[-1]  # Get just the filename
                
                # Check if it's a video chunk and matches the user type
                if (key.endswith('.webm') or key.endswith('.mp4')) and not key.endswith('final_video.mp4'):
                    # For new format: user_{user_id}_chunk_{chunk_index}.webm or {user_type}_chunk_{chunk_index}.webm
                    if (filename.startswith(f'{user_type}_chunk_') or 
                        filename.startswith(f'user_') and user_type in filename):
                        chunks.append(key)
            
            logger.info(f"Found {len(chunks)} chunks for room {room_id}, user {user_type} (new format)")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to list chunks from R2: {str(e)}")
            return []

    async def _list_chunks_old_format(self, room_id: str, user_type: str) -> List[str]:
        """
        Fallback method for old path format (backward compatibility).
        
        Args:
            room_id: Room ID for the recording
            user_type: Type of user ("host" or "guest")
            
        Returns:
            List[str]: List of R2 object keys for chunks
        """
        try:
            # Old path format with riverside prefix: riverside/{room_id}/{user_type}/
            prefix = f"{self.riverside_prefix}/{room_id}/{user_type}/"
            
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                return []
            
            # Filter out metadata files and return only video chunks
            chunks = []
            for obj in response['Contents']:
                key = obj['Key']
                if key.endswith('.webm') or key.endswith('.mp4'):
                    chunks.append(key)
            
            logger.info(f"Found {len(chunks)} chunks for room {room_id}, user {user_type} (old format)")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to list chunks from R2 (old format): {str(e)}")
            return []
    
    async def upload_final_video(self, file_path: str, room_id: str) -> Optional[str]:
        """
        Upload final processed video to R2.
        Updated to use consistent path format with processed videos.
        
        Args:
            file_path: Local path to the final video file
            room_id: Room ID for the recording
            
        Returns:
            str: Public URL of the uploaded video if successful, None if failed
        """
        try:
            # Use riverside/processed/ prefix to organize final videos separately from chunks
            object_key = f"{self.riverside_prefix}/processed/{room_id}/final_video.mp4"
            
            # Handle test mode where client is None
            if self.client is None:
                logger.warning(f"⚠️ R2 client not initialized (test mode), simulating final video upload for {object_key}")
                return f"https://mock-r2-endpoint.com/{self.bucket_name}/{object_key}"
            
            # Upload final video to R2
            with open(file_path, 'rb') as file:
                self.client.put_object(
                    Bucket=self.bucket_name,
                    Key=object_key,
                    Body=file,
                    ContentType='video/mp4'
                )
            
            # Construct public URL if available
            if self.public_url_base:
                public_url = f"{self.public_url_base.rstrip('/')}/{object_key}"
            else:
                public_url = f"{self.endpoint_url}/{self.bucket_name}/{object_key}"
            
            logger.info(f"✅ Final video uploaded to R2: {object_key}")
            return public_url
            
        except Exception as e:
            logger.error(f"Failed to upload final video to R2: {str(e)}")
            return None
    
    async def cleanup_chunks(self, room_id: str) -> bool:
        """
        Clean up all chunk files for a room after processing.
        Updated to work with new pre-signed URL path format.
        
        Args:
            room_id: Room ID for the recording
            
        Returns:
            bool: True if successful, False if failed
        """
        try:
            objects_to_delete = []
            
            # Clean up chunks from new path format: riverside/uploads/{room_id}/
            new_prefix = f"{self.riverside_prefix}/uploads/{room_id}/"
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=new_prefix
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    # Delete all chunk files but keep final video
                    if not key.endswith('final_video.mp4'):
                        objects_to_delete.append({'Key': key})
            
            # Also clean up chunks from old path format: riverside/{room_id}/
            old_prefix = f"{self.riverside_prefix}/{room_id}/"
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=old_prefix
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    # Don't delete the final video, and avoid duplicates
                    if (not key.endswith('final_video.mp4') and 
                        {'Key': key} not in objects_to_delete):
                        objects_to_delete.append({'Key': key})
            
            if objects_to_delete:
                # Delete in batches if there are many files (R2 has a 1000 object limit per delete)
                batch_size = 1000
                for i in range(0, len(objects_to_delete), batch_size):
                    batch = objects_to_delete[i:i + batch_size]
                    self.client.delete_objects(
                        Bucket=self.bucket_name,
                        Delete={'Objects': batch}
                    )
                
                logger.info(f"✅ Cleaned up {len(objects_to_delete)} files for room {room_id}")
            else:
                logger.info(f"No chunks found to cleanup for room {room_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup chunks from R2: {str(e)}")
            return False


# Global instance - initialize with proper error handling
_r2_storage_instance = None

def get_r2_storage() -> R2StorageService:
    """Get or create the R2 storage service instance."""
    import os
    global _r2_storage_instance
    if _r2_storage_instance is None:
        # Only enter test mode for actual pytest runs, not missing env vars
        is_testing = (
            "pytest" in os.environ.get("_", "") or
            "PYTEST_CURRENT_TEST" in os.environ
        )
        _r2_storage_instance = R2StorageService(skip_validation=is_testing)
    return _r2_storage_instance

# For backward compatibility, expose as r2_storage
# This will only be created when actually accessed
class _R2StorageProxy:
    """Proxy class to lazily initialize R2 storage."""
    def __getattr__(self, name):
        return getattr(get_r2_storage(), name)

r2_storage = _R2StorageProxy() 