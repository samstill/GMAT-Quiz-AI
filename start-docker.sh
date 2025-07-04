#!/bin/bash

# GMAT Quiz Docker Setup Script
# This script will build and start the entire application with Docker

set -e  # Exit on any error

echo "🚀 Starting GMAT Quiz Application with Docker..."
echo "================================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker Compose."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ .env file created. You can edit it later to add your Google API key."
fi

# Create necessary directories if they don't exist
echo "📁 Creating necessary directories..."
mkdir -p user_databases
mkdir -p JSON
mkdir -p images

# Stop any existing containers
echo "🛑 Stopping any existing containers..."
docker-compose down --remove-orphans 2>/dev/null || true

# Build and start the application
echo "🔨 Building and starting the application..."
docker-compose up --build -d

# Wait for the application to be ready
echo "⏳ Waiting for the application to start..."
sleep 10

# Check if the application is running
if docker-compose ps | grep -q "Up"; then
    echo ""
    echo "✅ SUCCESS! GMAT Quiz Application is now running!"
    echo "================================================="
    echo "🌐 Frontend (Web App): http://localhost"
    echo "🔧 Backend API: http://localhost:8000"
    echo "📚 API Documentation: http://localhost:8000/docs"
    echo ""
    echo "� SSL Setup (for production domain):"
    echo "   • Run: ./setup-ssl.sh"
    echo "   • After SSL: https://gmat.harshitpadha.me"
    echo ""
    echo "�📋 Useful commands:"
    echo "   • View logs: docker-compose logs -f"
    echo "   • Stop app: docker-compose down"
    echo "   • Restart: docker-compose restart"
    echo ""
    echo "🔧 To add your Google API key:"
    echo "   1. Edit the .env file"
    echo "   2. Set GOOGLE_API_KEY=your_actual_key"
    echo "   3. Restart with: docker-compose restart"
    echo ""
else
    echo "❌ Failed to start the application. Check logs with: docker-compose logs"
    exit 1
fi
