#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 Starting MineContext Development Environment..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file not found${NC}"
    echo "   It's recommended to use .env file for environment variables"
    echo "   Run: cp .env.example .env"
    echo "   Then edit .env with your configuration"
    echo ""
fi

# Check if config exists
if [ ! -f "config/config.yaml" ]; then
    echo -e "${YELLOW}⚠️  Warning: config/config.yaml not found${NC}"
    echo "   Checking for example configurations..."
    
    if [ -f "config/config.ollama.example.yaml" ]; then
        echo -e "${GREEN}✓${NC} Found Ollama example configuration"
        echo "   To use Ollama, run: cp config/config.ollama.example.yaml config/config.yaml"
    fi
    
    echo -e "${RED}✗${NC} Please create config/config.yaml before starting"
    echo "   See docs/LLM_CONFIGURATION_GUIDE.md for configuration help"
    exit 1
fi

echo -e "${GREEN}✓${NC} Configuration file found"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "🐍 Activating Python virtual environment..."
    source .venv/bin/activate
    echo -e "${GREEN}✓${NC} Virtual environment activated"
else
    echo -e "${YELLOW}⚠️  No .venv found, using system Python${NC}"
    echo "   Consider creating a virtual environment:"
    echo "   python3 -m venv .venv && source .venv/bin/activate"
fi

# Function to check Python dependencies
check_python_deps() {
    echo "🔍 Checking Python dependencies..."
    
    # Use the correct Python command (python in venv, python3 otherwise)
    local PYTHON_CMD="python"
    if [ -z "$VIRTUAL_ENV" ]; then
        PYTHON_CMD="python3"
    fi
    
    # Critical dependencies to check
    local deps=("opencontext" "sqlalchemy" "fastapi" "pyyaml" "chromadb" "openai")
    local missing_deps=()
    
    for dep in "${deps[@]}"; do
        if ! $PYTHON_CMD -c "import ${dep}" 2>/dev/null; then
            missing_deps+=("${dep}")
        fi
    done
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Missing Python dependencies: ${missing_deps[*]}${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓${NC} All critical Python dependencies found"
    return 0
}

# Check and install Python dependencies
if ! check_python_deps; then
    echo "📦 Installing Python dependencies..."
    echo "   This may take a few minutes..."
    
    if pip install -e . ; then
        echo -e "${GREEN}✓${NC} Python dependencies installed successfully"
        
        # Verify installation
        if ! check_python_deps; then
            echo -e "${RED}✗${NC} Dependency installation failed. Please check errors above."
            exit 1
        fi
    else
        echo -e "${RED}✗${NC} Failed to install Python dependencies"
        echo "   Try manually: pip install -e ."
        exit 1
    fi
fi

# Start backend and save its PID
echo "🔧 Starting backend service..."
# Use python in venv, python3 otherwise
if [ -n "$VIRTUAL_ENV" ]; then
    python -m opencontext.cli start &
else
    python3 -m opencontext.cli start &
fi
BACKEND_PID=$!

# Wait a bit to check if backend started successfully
sleep 2
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}✗${NC} Backend failed to start. Check logs for details."
    exit 1
fi

echo -e "${GREEN}✓${NC} Backend started with PID: $BACKEND_PID"

# Function to kill the backend process
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    if kill -0 $BACKEND_PID 2>/dev/null; then
        kill $BACKEND_PID
        echo -e "${GREEN}✓${NC} Backend stopped"
    fi
    exit
}

# Trap Ctrl+C and call cleanup
trap cleanup INT TERM

# Function to check frontend dependencies
check_frontend_deps() {
    echo "🔍 Checking frontend dependencies..."
    
    if [ ! -d "frontend/node_modules" ]; then
        echo -e "${YELLOW}⚠️  node_modules directory not found${NC}"
        return 1
    fi
    
    # Check for critical packages
    local critical_packages=("electron" "vite" "react" "pidusage")
    local missing_packages=()
    
    cd frontend
    for package in "${critical_packages[@]}"; do
        if [ ! -d "node_modules/${package}" ]; then
            missing_packages+=("${package}")
        fi
    done
    cd ..
    
    if [ ${#missing_packages[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Missing frontend packages: ${missing_packages[*]}${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓${NC} All critical frontend dependencies found"
    return 0
}

# Check and install frontend dependencies
if ! check_frontend_deps; then
    echo "📦 Installing frontend dependencies..."
    echo "   This may take a few minutes..."
    
    cd frontend
    if pnpm install; then
        cd ..
        echo -e "${GREEN}✓${NC} Frontend dependencies installed successfully"
        
        # Verify installation
        if ! check_frontend_deps; then
            echo -e "${RED}✗${NC} Frontend dependency installation incomplete"
            echo "   Try manually: cd frontend && pnpm install"
            exit 1
        fi
    else
        cd ..
        echo -e "${RED}✗${NC} Failed to install frontend dependencies"
        echo "   Try manually: cd frontend && pnpm install"
        exit 1
    fi
fi

# Start frontend in the foreground
echo "💻 Starting frontend development server..."
cd frontend && pnpm run dev

# Call cleanup when frontend exits
cleanup