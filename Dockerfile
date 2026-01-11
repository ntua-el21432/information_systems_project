FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies using uv
# First try to install from pyproject.toml, fallback to direct install
RUN uv pip install --system . 2>/dev/null || \
    uv pip install --system \
        fastapi>=0.104.0 \
        "uvicorn[standard]>=0.24.0" \
        sqlalchemy>=2.0.0 \
        psycopg2-binary>=2.9.9 \
        aiofiles>=23.2.0 \
        ollama>=0.1.0 \
        python-dotenv>=1.0.0 \
        pydantic>=2.5.0 \
        pydantic-settings>=2.1.0

# Copy application code
COPY app/ ./app/

# Create data directory for SQLite
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
