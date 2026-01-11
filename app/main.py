from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, text_to_sql

app = FastAPI(
    title="LLMSQL2 - Text-to-SQL Comparison",
    description="Comparison between text-to-SQL methods: GPT, TinyLlama, SQLite, PostgreSQL",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(text_to_sql.router, prefix="/api", tags=["text-to-sql"])


@app.get("/")
async def root():
    return {
        "message": "LLMSQL2 - Text-to-SQL Comparison API",
        "version": "0.1.0",
        "docs": "/docs"
    }
    }
