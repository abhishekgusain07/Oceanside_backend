# FastAPI PostgreSQL Template

This template provides a ready-to-use FastAPI backend with PostgreSQL integration via SQLAlchemy.

## Features

- FastAPI setup with best practices
- PostgreSQL connection through SQLAlchemy
- Docker and docker-compose configuration
- Dependency management with uv package manager
- Health check endpoint
- Structured project layout
- Testing setup with pytest

## Getting Started

### Prerequisites

- Python 3.10+
- Docker and docker-compose
- [uv](https://github.com/astral-sh/uv) package manager

### Setup

1. Clone this repository
2. Create a virtual environment with uv:

```bash
uv venv
```

3. Install dependencies:

```bash
uv pip install -r requirements.txt
```

4. Copy the environment example file and modify as needed:

```bash
cp .env.example .env
```

5. Run the application:

```bash
uvicorn app.main:app --reload
```

### Using Docker

```bash
docker-compose up -d
```

## Project Structure

- `app/`: Main application package
  - `main.py`: Application entry point
  - `api/`: API routes and endpoints
  - `core/`: Core components (config, dependencies)
  - `models/`: SQLAlchemy models
  - `schemas/`: Pydantic schemas
  - `crud/`: CRUD operations
  - `db/`: Database setup and session management
- `tests/`: Test suite
- `Dockerfile`: Docker configuration
- `docker-compose.yml`: Docker Compose configuration
- `requirements.txt`: Project dependencies

## API Documentation

Once running, you can access:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/api/health`