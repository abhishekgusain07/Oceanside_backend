#!/bin/bash

# Stop development servers for Riverside backend
# This script stops both FastAPI and Celery processes

echo "🛑 Stopping Riverside Backend Development Servers..."

# Function to kill processes by pattern
kill_processes() {
    local pattern=$1
    local service_name=$2
    
    pids=$(pgrep -f "$pattern")
    if [ -n "$pids" ]; then
        echo "🔄 Stopping $service_name processes..."
        echo "PIDs: $pids"
        kill $pids
        sleep 2
        
        # Check if processes are still running and force kill if needed
        remaining_pids=$(pgrep -f "$pattern")
        if [ -n "$remaining_pids" ]; then
            echo "⚡ Force killing stubborn $service_name processes..."
            kill -9 $remaining_pids
        fi
        echo "✅ $service_name stopped"
    else
        echo "ℹ️  No $service_name processes found"
    fi
}

# Stop FastAPI (uvicorn) processes
kill_processes "uvicorn.*app.main:app" "FastAPI"

# Stop Celery worker processes
kill_processes "celery.*worker" "Celery"

# Stop any remaining celery processes
kill_processes "celery.*app.core.celery_app" "Celery (specific)"

# Check for any remaining processes
echo ""
echo "🔍 Checking for remaining processes..."

fastapi_remaining=$(pgrep -f "uvicorn.*app.main:app")
celery_remaining=$(pgrep -f "celery.*worker")

if [ -z "$fastapi_remaining" ] && [ -z "$celery_remaining" ]; then
    echo "✅ All development servers stopped successfully!"
else
    echo "⚠️  Some processes might still be running:"
    if [ -n "$fastapi_remaining" ]; then
        echo "   FastAPI PIDs: $fastapi_remaining"
    fi
    if [ -n "$celery_remaining" ]; then
        echo "   Celery PIDs: $celery_remaining"
    fi
    echo ""
    echo "💡 You can manually kill them with:"
    echo "   kill -9 <PID>"
    echo "   or run this script again"
fi

# Optional: Stop tmux session if it exists (for Linux users)
if command -v tmux &> /dev/null; then
    if tmux has-session -t riverside-dev 2>/dev/null; then
        echo "🔄 Stopping tmux session 'riverside-dev'..."
        tmux kill-session -t riverside-dev
        echo "✅ Tmux session stopped"
    fi
fi

echo ""
echo "🏁 Stop script completed!" 