from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.database import postgres_engine, sqlite_engine

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@router.get("/health/postgres")
async def health_check_postgres():
    """Check PostgreSQL connection"""
    try:
        with postgres_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        return {"status": "healthy", "database": "postgresql"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"PostgreSQL connection failed: {str(e)}")


@router.get("/health/sqlite")
async def health_check_sqlite():
    """Check SQLite connection"""
    try:
        with sqlite_engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        return {"status": "healthy", "database": "sqlite"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"SQLite connection failed: {str(e)}")
