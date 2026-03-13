#!/bin/bash

# Quick Start Script for PDF Claims Extraction API

echo "================================"
echo "PDF Claims Extraction API Setup"
echo "================================"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file and add your GEMINI_API_KEY"
    echo "   Get your API key from: https://makersuite.google.com/app/apikey"
    echo ""
    read -p "Press Enter after you've added your API key to .env..."
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check for poppler
echo ""
echo "🔍 Checking for poppler-utils..."
if ! command -v pdfinfo &> /dev/null; then
    echo "⚠️  poppler-utils not found!"
    echo "   Please install it:"
    echo "   - Ubuntu/Debian: sudo apt-get install poppler-utils"
    echo "   - macOS: brew install poppler"
    echo "   - Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases"
    echo ""
else
    echo "✅ poppler-utils is installed"
fi

# Create directories
echo ""
echo "📁 Creating directories..."
mkdir -p uploads responses

echo ""
echo "================================"
echo "✅ Setup Complete!"
echo "================================"
echo ""
echo "To start the server:"
echo "  python main.py"
echo ""
echo "Or with uvicorn:"
echo "  uvicorn main:app --reload"
echo ""
echo "API will be available at: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "To run tests:"
echo "  python test_api.py"
echo ""
