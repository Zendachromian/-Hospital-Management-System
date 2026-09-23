#!/bin/bash

# Stop all Hospital Management System services

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDS_DIR="$PROJECT_DIR/.pids"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🛑 Stopping Hospital Management System...${NC}"

# Function to kill process by PID file
kill_by_pidfile() {
    if [ -f "$1" ]; then
        PID=$(cat "$1")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${YELLOW}Stopping $2 (PID: $PID)${NC}"
            kill $PID 2>/dev/null
            sleep 1
            if ps -p $PID > /dev/null 2>&1; then
                kill -9 $PID 2>/dev/null
            fi
            echo -e "${GREEN}✓ $2 stopped${NC}"
        else
            echo -e "${YELLOW}⚠ $2 not running${NC}"
        fi
        rm -f "$1"
    fi
}

# Stop services in reverse order
kill_by_pidfile "$PIDS_DIR/celery_beat.pid" "Celery Beat"
kill_by_pidfile "$PIDS_DIR/celery_worker.pid" "Celery Worker"
kill_by_pidfile "$PIDS_DIR/frontend.pid" "Frontend"
kill_by_pidfile "$PIDS_DIR/backend.pid" "Backend"
kill_by_pidfile "$PIDS_DIR/redis.pid" "Redis"

# Kill any remaining processes on ports
for port in 5000 8080 6379; do
    PID=$(lsof -ti:$port 2>/dev/null)
    if [ ! -z "$PID" ]; then
        echo -e "${YELLOW}Killing process on port $port (PID: $PID)${NC}"
        kill -9 $PID 2>/dev/null
    fi
done

echo -e "${GREEN}✓ All services stopped${NC}"
