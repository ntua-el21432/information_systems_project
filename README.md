# LLMSQL2 - Text-to-SQL Comparison Project

Semester project for Information Systems, Analysis and Design. Task is: "Comparison between text-to-SQL methods"

**Variant: LLMSQL2**
- LLMs: GPT-OSS (via Ollama), TinyLlama (via Ollama)
- RDBMS: SQLite, PostgreSQL

## Project Structure

```
.
├── app/                    # FastAPI application
│   ├── __init__.py
│   ├── main.py            # FastAPI app entry point
│   ├── config.py          # Configuration settings
│   ├── database.py        # Database connections
│   ├── llm/               # LLM integrations
│   │   ├── __init__.py
│   │   ├── gpt.py         # GPT-OSS integration via Ollama
│   │   └── tinyllama.py   # TinyLlama integration via Ollama
│   └── routers/           # API routers
│       ├── __init__.py
│       ├── health.py      # Health check endpoints
│       └── text_to_sql.py # Text-to-SQL endpoints
├── data/                  # SQLite database files (gitignored)
├── compose.yml            # Docker Compose configuration
├── Dockerfile             # Python container Dockerfile
├── pyproject.toml         # Python dependencies (uv)
├── env.template           # Environment variables template
└── setup.sh               # Setup script

```

## Prerequisites

- Docker and Docker Compose
- No API keys required - all models run via Ollama

## Setup

1. **Clone the repository** (if applicable)

2. **Start the services:**
   ```bash
   docker-compose up -d
   ```
   
   **Or use the setup script (recommended):**
   ```bash
   ./setup.sh
   ```
   
   The setup script will:
   - Start all Docker containers
   - Pull the TinyLlama model
   - Pull the GPT-OSS model

3. **Manually pull models (if not using setup script):**
   ```bash
   docker exec llmsql2_ollama ollama pull tinyllama
   docker exec llmsql2_ollama ollama pull gpt-oss
   ```

4. **Verify services are running:**
   ```bash
   docker-compose ps
   ```

## Usage

### API Documentation

Once the services are running, access the API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Health Checks

```bash
# General health check
curl http://localhost:8000/api/health

# PostgreSQL health check
curl http://localhost:8000/api/health/postgres

# SQLite health check
curl http://localhost:8000/api/health/sqlite
```

### Text-to-SQL Endpoint

```bash
curl -X POST "http://localhost:8000/api/text-to-sql" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Show me all users",
    "model": "gpt",
    "database": "postgresql",
    "schema_info": "CREATE TABLE users (id INT, name VARCHAR(100));"
  }'

# Or with TinyLlama:
curl -X POST "http://localhost:8000/api/text-to-sql" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Show me all users",
    "model": "tinyllama",
    "database": "sqlite",
    "schema_info": "CREATE TABLE users (id INT, name VARCHAR(100));"
  }'
```

## Services

- **Backend (FastAPI)**: http://localhost:8000
- **Ollama**: http://localhost:11434
- **PostgreSQL**: localhost:5432

## Development

### Using uv for package management

The project uses `uv` as the Python package manager. Dependencies are defined in `pyproject.toml`.

### Running locally (without Docker)

1. Install uv: `pip install uv`
2. Install dependencies: `uv pip install -r pyproject.toml`
3. Set up environment variables in `.env`
4. Run: `uvicorn app.main:app --reload`

## Notes

- SQLite database file will be created in `./data/sqlite.db`
- PostgreSQL data persists in Docker volume `postgres_data`
- Ollama models (TinyLlama and GPT-OSS) are stored in Docker volume `ollama_data`
- Both LLM models run via Ollama - no API keys required

## Next Steps

1. Implement full text-to-SQL conversion logic
2. Add query execution and result comparison
3. Set up benchmarking framework
4. Load test datasets
5. Implement performance metrics collection
