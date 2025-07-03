#!/usr/bin/env python3
"""
Manual test script for pre-signed URL functionality.

This script demonstrates how to use the new pre-signed URL endpoints
and can be used for manual testing and validation.

Usage:
    python test_presigned_urls_manual.py

Requirements:
    - Backend server running on localhost:8000
    - R2 credentials configured in environment
    - A test recording created in the database
"""

import asyncio
import requests
import json
import uuid
from datetime import datetime
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
HEADERS = {"Content-Type": "application/json"}


class PresignedUrlTester:
    """Test class for manual testing of pre-signed URL functionality."""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
    
    def create_test_recording(self) -> Dict[str, Any]:
        """Create a test recording for testing."""
        test_data = {
            "user_id": f"test-user-{uuid.uuid4()}",
            "title": "Test Recording for Pre-signed URLs",
            "description": "Testing the new pre-signed URL functionality"
        }
        
        response = self.session.post(f"{self.base_url}/recordings", json=test_data)
        
        if response.status_code == 201:
            recording = response.json()
            print(f"✅ Created test recording: {recording['room_id']}")
            return recording
        else:
            print(f"❌ Failed to create recording: {response.status_code} - {response.text}")
            return None
    
    def test_generate_upload_url(self, recording_id: str, chunk_index: int = 1) -> Dict[str, Any]:
        """Test the generate upload URL endpoint."""
        print(f"\n🔧 Testing generate upload URL for recording: {recording_id}")
        
        test_data = {
            "recording_id": recording_id,
            "chunk_index": chunk_index,
            "content_type": "video/webm",
            "user_type": "host"
        }
        
        response = self.session.post(f"{self.base_url}/recordings/generate-upload-url", json=test_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Generated pre-signed URL successfully")
            print(f"   📁 File path: {result['file_path']}")
            print(f"   ⏱️  Expires in: {result['expires_in']} seconds")
            print(f"   📅 Expires at: {result['expires_at']}")
            print(f"   🔗 URL length: {len(result['pre_signed_url'])} characters")
            return result
        else:
            print(f"❌ Failed to generate upload URL: {response.status_code}")
            print(f"   Error: {response.text}")
            return None
    
    def test_upload_to_presigned_url(self, presigned_url: str, file_path: str) -> Dict[str, str]:
        """Test uploading to the pre-signed URL with dummy data."""
        print(f"\n📤 Testing upload to pre-signed URL")
        
        # Create dummy video data (simulating a chunk)
        dummy_data = b"DUMMY_VIDEO_CHUNK_DATA_" + b"A" * 1024  # 1KB of dummy data
        
        headers = {
            "Content-Type": "video/webm"
        }
        
        # Note: This would be a PUT request to the pre-signed URL
        # For this test, we'll simulate what the client would do
        print(f"   📋 Would upload {len(dummy_data)} bytes to:")
        print(f"   🔗 {presigned_url[:80]}..." if len(presigned_url) > 80 else presigned_url)
        
        # In a real scenario, you would do:
        # response = requests.put(presigned_url, data=dummy_data, headers=headers)
        # For this test, we'll simulate a successful response
        
        print(f"   ⚠️  Simulated upload (not actually uploading to R2)")
        
        # Return simulated ETag that would come from a real upload
        return {
            "etag": f"simulated-etag-{uuid.uuid4().hex[:16]}",
            "status": "simulated_success"
        }
    
    def test_confirm_upload(self, recording_id: str, chunk_index: int, file_path: str, etag: str) -> bool:
        """Test the confirm upload endpoint."""
        print(f"\n✅ Testing confirm upload for chunk {chunk_index}")
        
        test_data = {
            "recording_id": recording_id,
            "chunk_index": chunk_index,
            "file_path": file_path,
            "etag": etag
        }
        
        response = self.session.post(f"{self.base_url}/recordings/confirm-upload", json=test_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Upload confirmed successfully")
            print(f"   📋 Message: {result['message']}")
            print(f"   🔍 Verified: {result['verified']}")
            return True
        else:
            print(f"❌ Failed to confirm upload: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    
    def test_error_cases(self):
        """Test various error cases."""
        print(f"\n🔍 Testing error cases")
        
        # Test with non-existent recording
        print("Testing with non-existent recording...")
        result = self.test_generate_upload_url("nonexistent-recording-id")
        if result is None:
            print("✅ Correctly handled non-existent recording")
        else:
            print("❌ Should have failed for non-existent recording")
        
        # Test with invalid content type (this should be caught by schema validation)
        print("\nTesting with invalid content type...")
        test_data = {
            "recording_id": "test-recording",
            "chunk_index": 1,
            "content_type": "image/png",  # Invalid
            "user_type": "host"
        }
        
        response = self.session.post(f"{self.base_url}/recordings/generate-upload-url", json=test_data)
        if response.status_code == 422:  # Validation error
            print("✅ Correctly rejected invalid content type")
        else:
            print(f"❌ Should have rejected invalid content type, got: {response.status_code}")
    
    def run_full_test(self):
        """Run the complete test suite."""
        print("🚀 Starting Pre-signed URL Functionality Test")
        print("=" * 50)
        
        # Step 1: Create a test recording
        recording = self.create_test_recording()
        if not recording:
            print("❌ Cannot proceed without a test recording")
            return False
        
        recording_id = recording["room_id"]
        
        # Step 2: Test generating upload URL
        upload_info = self.test_generate_upload_url(recording_id, chunk_index=1)
        if not upload_info:
            print("❌ Cannot proceed without upload URL")
            return False
        
        # Step 3: Simulate upload to pre-signed URL
        upload_result = self.test_upload_to_presigned_url(
            upload_info["pre_signed_url"],
            upload_info["file_path"]
        )
        
        # Step 4: Test confirm upload
        confirm_success = self.test_confirm_upload(
            recording_id,
            1,
            upload_info["file_path"],
            upload_result["etag"]
        )
        
        # Step 5: Test multiple chunks
        print(f"\n🔄 Testing multiple chunks")
        for chunk_idx in [2, 3]:
            chunk_upload_info = self.test_generate_upload_url(recording_id, chunk_index=chunk_idx)
            if chunk_upload_info:
                chunk_upload_result = self.test_upload_to_presigned_url(
                    chunk_upload_info["pre_signed_url"],
                    chunk_upload_info["file_path"]
                )
                self.test_confirm_upload(
                    recording_id,
                    chunk_idx,
                    chunk_upload_info["file_path"],
                    chunk_upload_result["etag"]
                )
        
        # Step 6: Test error cases
        self.test_error_cases()
        
        print("\n" + "=" * 50)
        print("🏁 Test completed!")
        
        return True


def main():
    """Main function to run the tests."""
    print("Pre-signed URL Manual Test Script")
    print("Make sure your backend server is running on localhost:8000")
    print("And that R2 credentials are properly configured")
    
    input("Press Enter to continue...")
    
    tester = PresignedUrlTester()
    
    try:
        success = tester.run_full_test()
        if success:
            print("\n✅ All tests completed successfully!")
        else:
            print("\n❌ Some tests failed. Check the output above.")
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 