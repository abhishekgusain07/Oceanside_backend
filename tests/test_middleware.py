"""
Tests for custom middleware.
"""
import pytest
from fastapi import status


class TestRequestIdMiddleware:
    """Test request ID middleware."""

    async def test_request_id_header(self, client):
        """Test that request ID header is set in the response."""
        # Make a request
        response = await client.get("/api/health")
        assert response.status_code == status.HTTP_200_OK
        
        # Check that request ID header exists
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"] != ""
        
    async def test_custom_request_id(self, client):
        """Test that a custom request ID is preserved in the response."""
        custom_id = "test-request-id-123"
        
        # Make a request with a custom request ID
        response = await client.get(
            "/api/health", 
            headers={"X-Request-ID": custom_id}
        )
        assert response.status_code == status.HTTP_200_OK
        
        # Check that our custom request ID is preserved
        assert response.headers["X-Request-ID"] == custom_id 