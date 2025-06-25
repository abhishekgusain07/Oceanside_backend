#!/bin/bash

# Start development servers for Riverside backend
# This script starts both FastAPI and Celery in separate terminal tabs

echo "🚀 Starting Riverside Backend Development Servers..."

# Check if we're in the backend directory
if [ ! -f "app/main.py" ]; then
    echo "❌ Please run this script from the backend directory"
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "🔧 Activating virtual environment..."
    source .venv/bin/activate
fi

# Function to start FastAPI server
start_fastapi() {
    echo "🌐 Starting FastAPI server..."
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
}

# Function to start Celery worker
start_celery() {
    echo "⚡ Starting Celery worker..."
    celery -A app.core.celery_app:celery_app worker --loglevel=info -Q video_processing,celery
}

# Check if we're on macOS (for Terminal.app support)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - use Terminal.app
    echo "🖥️  Opening FastAPI server in new terminal tab..."
    osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && source .venv/bin/activate && echo '🌐 Starting FastAPI server...' && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000\""
    
    sleep 2
    
    echo "⚡ Opening Celery worker in new terminal tab..."
    osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && source .venv/bin/activate && echo '⚡ Starting Celery worker...' && celery -A app.core.celery_app:celery_app worker --loglevel=info -Q video_processing,celery\""
    
    echo "✅ Both servers started in separate terminal tabs!"
    echo "📊 FastAPI server: http://localhost:8000"
    echo "📋 FastAPI docs: http://localhost:8000/docs"
    echo "🔧 Celery worker: Check the new terminal tab"
    
else
    # Linux/other - use tmux or gnome-terminal
    if command -v tmux &> /dev/null; then
        echo "🖥️  Using tmux to start services..."
        
        # Create new tmux session
        tmux new-session -d -s riverside-dev
        
        # Split window and start FastAPI
        tmux send-keys -t riverside-dev:0 "source .venv/bin/activate && echo '🌐 Starting FastAPI server...' && python -m uvicorn app.main:application --reload --host 0.0.0.0 --port 8000" Enter
        
        # Create new window for Celery
        tmux new-window -t riverside-dev -n celery
        tmux send-keys -t riverside-dev:celery "source .venv/bin/activate && echo '⚡ Starting Celery worker...' && celery -A app.core.celery_app:celery_app worker --loglevel=info -Q video_processing,celery" Enter
        
        # Attach to session
        echo "✅ Starting tmux session with both services..."
        echo "📊 FastAPI server: http://localhost:8000"
        echo "🔧 Use 'Ctrl+B, n' to switch between FastAPI and Celery windows"
        echo "🚪 Use 'Ctrl+B, d' to detach from tmux"
        tmux attach-session -t riverside-dev
        
    elif command -v gnome-terminal &> /dev/null; then
        echo "🖥️  Using gnome-terminal..."
        gnome-terminal --tab --title="FastAPI" -- bash -c "source .venv/bin/activate && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000; exec bash"
        gnome-terminal --tab --title="Celery" -- bash -c "source .venv/bin/activate && celery -A app.core.celery_app:celery_app worker --loglevel=info -Q video_processing,celery; exec bash"
        echo "✅ Both servers started in separate terminal tabs!"
        
    else
        echo "❌ No supported terminal multiplexer found (tmux/gnome-terminal)"
        echo "💡 Please install tmux or run the commands manually:"
        echo ""
        echo "Terminal 1 (FastAPI):"
        echo "python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
        echo ""
        echo "Terminal 2 (Celery):"
        echo "celery -A app.core.celery_app:celery_app worker --loglevel=info -Q video_processing,celery"
        exit 1
    fi
fi 


# uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# celery -A app.core.celery_app:celery_app worker --loglevel=info -Q video_processing,celery