#!/bin/bash

# Hospital Management System - Unified Startup Script
# This script starts all required services in the background

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Log files
LOGS_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOGS_DIR"

REDIS_LOG="$LOGS_DIR/redis.log"
BACKEND_LOG="$LOGS_DIR/backend.log"
FRONTEND_LOG="$LOGS_DIR/frontend.log"
CELERY_WORKER_LOG="$LOGS_DIR/celery_worker.log"
CELERY_BEAT_LOG="$LOGS_DIR/celery_beat.log"

# PID files
PIDS_DIR="$PROJECT_DIR/.pids"
mkdir -p "$PIDS_DIR"

REDIS_PID="$PIDS_DIR/redis.pid"
BACKEND_PID="$PIDS_DIR/backend.pid"
FRONTEND_PID="$PIDS_DIR/frontend.pid"
CELERY_WORKER_PID="$PIDS_DIR/celery_worker.pid"
CELERY_BEAT_PID="$PIDS_DIR/celery_beat.pid"

# Function to check if a port is in use
check_port() {
    lsof -i :$1 >/dev/null 2>&1
    return $?
}

# Function to kill process by PID file
kill_by_pidfile() {
    if [ -f "$1" ]; then
        PID=$(cat "$1")
        if ps -p $PID > /dev/null 2>&1; then
            echo -e "${YELLOW}Killing process $PID${NC}"
            kill $PID 2>/dev/null
            sleep 1
            if ps -p $PID > /dev/null 2>&1; then
                kill -9 $PID 2>/dev/null
            fi
        fi
        rm -f "$1"
    fi
}

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}🛑 Stopping all services...${NC}"
    
    kill_by_pidfile "$CELERY_BEAT_PID"
    kill_by_pidfile "$CELERY_WORKER_PID"
    kill_by_pidfile "$FRONTEND_PID"
    kill_by_pidfile "$BACKEND_PID"
    kill_by_pidfile "$REDIS_PID"
    
    echo -e "${GREEN}✓ All services stopped${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
echo -e "${CYAN}   🏥 Hospital Management System - Startup    ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}📦 Creating Python virtual environment...${NC}"
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Failed to create virtual environment${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to activate virtual environment${NC}"
    exit 1
fi

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_DIR"

echo -e "${BLUE}📦 Checking Python dependencies...${NC}"

# Upgrade pip, setuptools, and wheel
echo -e "${YELLOW}  → Upgrading pip and setuptools...${NC}"
pip install --upgrade pip setuptools wheel > /dev/null 2>&1

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}✗ requirements.txt not found${NC}"
    exit 1
fi

# Install requirements from requirements.txt
echo -e "${YELLOW}  → Installing required libraries from requirements.txt...${NC}"
if pip install -r requirements.txt > /dev/null 2>&1; then
    echo -e "${GREEN}✓ All Python dependencies installed successfully${NC}"
else
    echo -e "${RED}✗ Failed to install dependencies${NC}"
    echo -e "${YELLOW}  Running with verbose output for debugging:${NC}"
    pip install -r requirements.txt
    exit 1
fi

# Verify critical packages are installed
echo -e "${YELLOW}  → Verifying critical packages...${NC}"
python3 -c "import flask, flask_cors, flask_jwt_extended, flask_mail, celery, redis, sqlalchemy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Some critical packages are missing${NC}"
    exit 1
fi
echo -e "${GREEN}✓ All critical packages verified${NC}"

echo ""
echo -e "${BLUE}📦 Checking system dependencies...${NC}"

# Check if Redis is installed
if ! command -v redis-server &> /dev/null; then
    echo -e "${RED}✗ Redis not installed${NC}"
    echo -e "${YELLOW}Please install Redis: sudo apt install redis-server${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Redis is installed${NC}"

echo ""
echo -e "${GREEN}Starting services...${NC}"
echo ""

# 1. Start Redis Server
echo -e "${CYAN}[1/5]${NC} Starting Redis Server (Port 6379)..."
if check_port 6379; then
    echo -e "${YELLOW}  ⚠  Redis already running on port 6379${NC}"
else
    redis-server --daemonize yes --pidfile "$REDIS_PID" --logfile "$REDIS_LOG" --port 6379
    sleep 1
    if redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓  Redis started successfully${NC}"
    else
        echo -e "${RED}  ✗  Failed to start Redis${NC}"
        exit 1
    fi
fi

# 2. Start Backend API (Flask)
echo -e "${CYAN}[2/5]${NC} Starting Backend API (Port 5000)..."
if check_port 5000; then
    echo -e "${YELLOW}  ⚠  Backend already running on port 5000${NC}"
else
    nohup python3 -m backend.app > "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID"
    sleep 2
    if check_port 5000; then
        echo -e "${GREEN}  ✓  Backend API started successfully${NC}"
    else
        echo -e "${RED}  ✗  Failed to start Backend API${NC}"
        cat "$BACKEND_LOG"
        exit 1
    fi
fi

# 3. Start Frontend Server
echo -e "${CYAN}[3/5]${NC} Starting Frontend Server (Port 8080)..."
if check_port 8080; then
    echo -e "${YELLOW}  ⚠  Frontend already running on port 8080${NC}"
else
    nohup python3 frontend/server.py > "$FRONTEND_LOG" 2>&1 &
    echo $! > "$FRONTEND_PID"
    sleep 1
    if check_port 8080; then
        echo -e "${GREEN}  ✓  Frontend server started successfully${NC}"
    else
        echo -e "${RED}  ✗  Failed to start Frontend server${NC}"
        cat "$FRONTEND_LOG"
        exit 1
    fi
fi

# 4. Start Celery Worker
echo -e "${CYAN}[4/5]${NC} Starting Celery Worker (Background Jobs)..."
if [ -f "$CELERY_WORKER_PID" ] && ps -p $(cat "$CELERY_WORKER_PID") > /dev/null 2>&1; then
    echo -e "${YELLOW}  ⚠  Celery Worker already running${NC}"
else
    nohup celery -A backend.celery_app.celery_app worker --loglevel=info > "$CELERY_WORKER_LOG" 2>&1 &
    echo $! > "$CELERY_WORKER_PID"
    sleep 3
    if [ -f "$CELERY_WORKER_PID" ] && ps -p $(cat "$CELERY_WORKER_PID") > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓  Celery Worker started successfully${NC}"
    else
        echo -e "${RED}  ✗  Failed to start Celery Worker${NC}"
        echo -e "${YELLOW}  Check logs: $CELERY_WORKER_LOG${NC}"
    fi
fi

# 5. Start Celery Beat (Scheduler)
echo -e "${CYAN}[5/5]${NC} Starting Celery Beat (Scheduled Tasks)..."
if [ -f "$CELERY_BEAT_PID" ] && ps -p $(cat "$CELERY_BEAT_PID") > /dev/null 2>&1; then
    echo -e "${YELLOW}  ⚠  Celery Beat already running${NC}"
else
    nohup celery -A backend.celery_app.celery_app beat --loglevel=info > "$CELERY_BEAT_LOG" 2>&1 &
    echo $! > "$CELERY_BEAT_PID"
    sleep 3
    if [ -f "$CELERY_BEAT_PID" ] && ps -p $(cat "$CELERY_BEAT_PID") > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓  Celery Beat started successfully${NC}"
    else
        echo -e "${RED}  ✗  Failed to start Celery Beat${NC}"
        echo -e "${YELLOW}  Check logs: $CELERY_BEAT_LOG${NC}"
    fi
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}   ✓ All services started successfully!        ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}📊 Service URLs:${NC}"
echo -e "  ${BLUE}Frontend:${NC}     http://localhost:8080"
echo -e "  ${BLUE}Backend API:${NC}  http://localhost:5000/api"
echo -e "  ${BLUE}Health Check:${NC} http://localhost:5000/api/health"
echo -e "  ${BLUE}Redis:${NC}        localhost:6379"
echo ""
echo -e "${CYAN}📝 Log Files:${NC}"
echo -e "  Backend:       $BACKEND_LOG"
echo -e "  Frontend:      $FRONTEND_LOG"
echo -e "  Celery Worker: $CELERY_WORKER_LOG"
echo -e "  Celery Beat:   $CELERY_BEAT_LOG"
echo -e "  Redis:         $REDIS_LOG"
echo ""
echo -e "${CYAN}🤖 Background Jobs:${NC}"
echo -e "  ${GREEN}✓${NC} Daily Reminders    - Runs at 9:00 AM daily"
echo -e "  ${GREEN}✓${NC} Monthly Reports    - Runs on 1st of month at 8:00 AM"
echo -e "  ${GREEN}✓${NC} CSV Export         - On-demand from Patient dashboard"
echo ""
echo -e "${CYAN}⚡ Performance:${NC}"
echo -e "  ${GREEN}✓${NC} Redis Caching      - 5-15 min TTL on all major endpoints"
echo -e "  ${GREEN}✓${NC} Auto Invalidation  - Cache clears on data changes"
echo ""
echo -e "${CYAN}👤 Admin Credentials:${NC}"
echo -e "  Username: ${GREEN}admin${NC}"
echo -e "  Password: ${GREEN}admin123${NC}"
echo ""
echo -e "${CYAN}📧 Email Configuration:${NC}"
echo -e "  Set environment variables for email features:"
echo -e "  ${YELLOW}export MAIL_USERNAME=your-email@gmail.com${NC}"
echo -e "  ${YELLOW}export MAIL_PASSWORD=your-app-password${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Keep script running and monitor services
while true; do
    sleep 5
    
    # Check if services are still running
    if ! check_port 5000; then
        echo -e "${RED}⚠ Backend API stopped unexpectedly${NC}"
        break
    fi
    
    if ! check_port 8080; then
        echo -e "${RED}⚠ Frontend server stopped unexpectedly${NC}"
        break
    fi
done

cleanup
