"""
Tests for the health check endpoint.
"""
import pytest
from fastapi import status


class TestHealth:
    """Test health endpoint."""

    async def test_health_check(self, client):
        """Test health check endpoint returns 200 and correct data."""
        response = await client.get("/api/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        
        # Check all required fields are present
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data
        assert "python_version" in data
        assert "database_status" in data
        
        # Check system info fields
        assert "system_info" in data
        system_info = data["system_info"]
        assert "platform" in system_info
        assert "cpu_count" in system_info
        assert "memory_total_gb" in system_info
        assert "memory_available_percent" in system_info