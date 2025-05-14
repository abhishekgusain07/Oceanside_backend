# FastAPI Backend Template

A production-ready FastAPI backend template with async database support, structured project layout, and best practices.

## Features

- **Modern FastAPI Structure**: Well-organized codebase with modular design
- **Async Database Integration**: Uses SQLAlchemy 2.0+ with asyncpg for high-performance database access
- **Database Migrations**: Alembic for database version control and migrations
- **Environment Configuration**: Pydantic settings with environment variable support
- **Structured Logging**: Configured with structlog for JSON and developer-friendly logging
- **Testing Ready**: Pytest setup with async support and fixtures
- **Health Checks**: Built-in health check endpoint with database connectivity testing
- **CORS Middleware**: Configurable CORS support
- **Docker Support**: Includes Dockerfile and docker-compose.yml for containerization
- **API Documentation**: Auto-generated Swagger/OpenAPI docs

## Project Structure

```
├── alembic/                  # Database migrations
├── app/                      # Application code
│   ├── api/                  # API endpoints
│   │   ├── dependencies.py   # Reusable API dependencies
│   │   ├── endpoints/        # API route handlers
│   │   └── router.py         # Main API router
│   ├── core/                 # Core application code
│   │   ├── config.py         # Configuration settings
│   │   ├── database.py       # Database setup
│   │   └── logging.py        # Logging configuration
│   ├── models/               # SQLAlchemy database models
│   ├── schemas/              # Pydantic schemas for request/response validation
│   ├── services/             # Business logic services
│   └── main.py               # Application entry point
├── tests/                    # Test directory
│   ├── conftest.py           # Test configuration and fixtures
│   └── test_*.py             # Test files
├── Dockerfile                # Docker configuration
├── docker-compose.yml        # Docker Compose configuration
├── .gitignore                # Git ignore file
├── env.example               # Example environment variables
├── pyproject.toml            # Project dependencies and metadata
└── README.md                 # Project documentation
```

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL

### Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/fastapi-backend-template.git
cd fastapi-backend-template
```

2. Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate     # Windows
```

3. Install dependencies:

```bash
pip install -e .           # Install the project in development mode
# OR
pip install -r requirements.txt
```

4. Create a `.env` file:

```bash
cp env.example .env
# Edit .env with your database credentials and settings
```

5. Run database migrations:

```bash
alembic upgrade head
```

6. Start the development server:

```bash
uvicorn app.main:app --reload
```

7. Open http://localhost:8000/docs in your browser to see the API documentation.

### Using Docker

1. Build and start the containers:

```bash
docker-compose up -d
```

2. The API will be available at http://localhost:8000

## Development

### Creating Database Migrations

After changing models, create a new migration:

```bash
alembic revision --autogenerate -m "Description of the change"
```

Apply the migration:

```bash
alembic upgrade head
```

### Running Tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=app
```

### Code Formatting and Linting

Format code with Black:

```bash
black .
```

Run the linter:

```bash
ruff check .
```

Type checking:

```bash
mypy app
```

## Adding New Endpoints

1. Create a new file in `app/api/endpoints/`
2. Add routes to the file
3. Include the router in `app/api/router.py`

## Deployment

### Production Best Practices

- Set `DEBUG=false` in production
- Configure proper logging with `JSON_LOGS=true`
- Use environment variables for all secrets
- Set up proper database connection pooling
- Configure proper CORS settings
- Use HTTPS in production

## License

This project is licensed under the MIT License - see the LICENSE file for details.