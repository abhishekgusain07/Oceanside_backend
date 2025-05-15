"""
CrewAI API endpoints.
"""
from fastapi import APIRouter

from app.api.routes.crewai import router as crewai_router

# Re-export the router
router = crewai_router 