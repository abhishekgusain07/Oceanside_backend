"""
API routes for CrewAI operations.
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Literal
import structlog

from app.agents.crew import run_research_crew
from app.core.crewai_config import crewai_settings

# Create a logger for this module
logger = structlog.get_logger(__name__)

# Create router
router = APIRouter()


class ResearchRequest(BaseModel):
    """Request model for research operations."""
    topic: str
    content_type: str = "report"
    audience: str = "professionals"
    model: Optional[str] = None
    provider: Optional[Literal["google", "openai"]] = None


class ResearchResponse(BaseModel):
    """Response model for research operations."""
    task_id: str
    status: str = "processing"


class ResearchResult(BaseModel):
    """Result model for completed research."""
    task_id: str
    status: str
    result: str = None
    error: str = None


# In-memory storage for task results
# In a production environment, this should be replaced with a proper database
task_results = {}


@router.post("/research", response_model=ResearchResponse)
async def create_research_task(request: ResearchRequest, background_tasks: BackgroundTasks):
    """
    Start a new research task using CrewAI.
    
    This endpoint runs a research crew in the background and returns a task ID
    that can be used to poll for results.
    """
    # Generate a simple task ID (in production, use a UUID or similar)
    import time
    task_id = f"task_{int(time.time())}"
    
    # Store initial task status
    task_results[task_id] = {
        "status": "processing",
        "result": None,
        "error": None
    }
    
    # Add the background task
    background_tasks.add_task(
        process_research_task,
        task_id,
        request.topic,
        request.content_type,
        request.audience,
        request.model,
        request.provider
    )
    
    logger.info("Research task created", task_id=task_id, topic=request.topic)
    return ResearchResponse(task_id=task_id)


@router.get("/research/{task_id}", response_model=ResearchResult)
async def get_research_result(task_id: str):
    """
    Get the results of a research task.
    
    This endpoint returns the current status of the task and its result if available.
    """
    if task_id not in task_results:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_data = task_results[task_id]
    return ResearchResult(
        task_id=task_id,
        status=task_data["status"],
        result=task_data["result"],
        error=task_data["error"]
    )


async def process_research_task(task_id: str, topic: str, content_type: str, 
                               audience: str, model: str = None, provider: str = None):
    """
    Process a research task in the background.
    
    This function runs the CrewAI research flow and updates the task status.
    """
    try:
        # Run the research crew
        result = await run_research_crew(
            topic, 
            content_type, 
            audience, 
            model, 
            provider
        )
        
        # Update task status
        task_results[task_id]["status"] = "completed"
        task_results[task_id]["result"] = result
        
        logger.info("Research task completed", task_id=task_id)
    except Exception as e:
        # Handle any errors
        task_results[task_id]["status"] = "failed"
        task_results[task_id]["error"] = str(e)
        
        logger.error("Research task failed", task_id=task_id, error=str(e)) 