FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN uv pip install --system -r requirements.txt

# Copy project files
COPY . /app/

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]