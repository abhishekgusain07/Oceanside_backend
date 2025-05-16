# CrewAI Integration

This module provides a robust integration of CrewAI into the FastAPI application, enabling you to create and run specialized AI agent workflows.

## Overview

The implementation follows best practices from the CrewAI documentation and provides:

1. Specialized agents with clear roles, goals, and backstories
2. Well-defined tasks with explicit descriptions and expected outputs
3. A crew orchestration system that runs tasks sequentially
4. API endpoints for triggering and monitoring crew executions
5. Support for both OpenAI and Google Gemini models

## Architecture

The implementation consists of three main components:

- **Agents**: Specialized AI entities with roles, goals, and backstories
- **Tasks**: Well-defined activities for agents to perform
- **Crews**: Orchestrators that coordinate agents and tasks

## Usage

### API Endpoints

The CrewAI functionality is exposed through the following API endpoints:

#### Start a Research Task

```
POST /api/crewai/research

{
  "topic": "Artificial intelligence trends in healthcare",
  "content_type": "report",
  "audience": "healthcare professionals",
  "model": "gemini-1.5-flash",
  "provider": "google"
}
```

Response:

```json
{
  "task_id": "task_1620139200",
  "status": "processing"
}
```

#### Get Research Results

```
GET /api/crewai/research/{task_id}
```

Response:

```json
{
  "task_id": "task_1620139200",
  "status": "completed",
  "result": "...",
  "error": null
}
```

### Configuration

Configure the CrewAI implementation through environment variables:

```
# CrewAI Settings
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_GEMINI_API_KEY_here
DEFAULT_LLM_PROVIDER=google
DEFAULT_LLM_MODEL=gemini-1.5-flash
DEFAULT_LLM_TEMPERATURE=0.7
```

### Supported Model Providers

This implementation supports two model providers:

1. **Google AI (Gemini)**: Set `provider` to `google` and use models like `gemini-1.5-flash`
2. **OpenAI**: Set `provider` to `openai` and use models like `gpt-4`

The default is set to use Google's Gemini 1.5 Flash model.

## Extending the Implementation

### Adding New Agents

Create new agent functions in `agents.py` following the role-goal-backstory pattern:

```python
def create_custom_agent(llm=None):
    return Agent(
        role="Your Specialized Role",
        goal="Clear, outcome-focused goal",
        backstory="Experience and perspective that inform the agent's approach",
        verbose=True,
        llm=llm or default_llm,
    )
```

### Creating New Tasks

Define new tasks in `tasks.py` with clear descriptions and expected outputs:

```python
def create_custom_task(agent, input_parameter):
    return Task(
        description="Clear process instructions",
        expected_output="Specific deliverable format",
        agent=agent,
        context=["Relevant context information"]
    )
```

### Building New Crews

Create new crew factories or modify the existing one in `crew.py` to orchestrate different workflows.

## Best Practices

1. **Specialized Agents**: Design agents with specific roles rather than generalists
2. **Clear Tasks**: Define tasks with explicit descriptions and expected outputs
3. **Single-Purpose Tasks**: Each task should do one thing well
4. **Appropriate Contexts**: Provide relevant context to help agents understand their work
5. **Sequential Processes**: Start with simple sequential processes before attempting complex workflows 