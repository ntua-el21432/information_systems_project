#!/bin/bash

# Setup script for LLMSQL2 project

echo "Setting up LLMSQL2 project..."

# Start Docker containers
echo "Starting Docker containers..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 10

# Pull models in Ollama
echo "Pulling TinyLlama model in Ollama..."
docker exec llmsql2_ollama ollama pull tinyllama

echo "Pulling GPT-OSS model in Ollama..."
docker exec llmsql2_ollama ollama pull gpt-oss

echo "Setup complete!"
echo ""
echo "Services:"
echo "  - FastAPI Backend: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - Ollama: http://localhost:11434"
echo "  - PostgreSQL: localhost:5432"
echo ""
echo "To check service status: docker-compose ps"
echo "To view logs: docker-compose logs -f"
