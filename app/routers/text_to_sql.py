from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Literal, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import time

from app.llm import gpt, tinyllama
from app.database import get_postgres_db, get_sqlite_db

router = APIRouter()


class TextToSQLRequest(BaseModel):
    text: str
    model: Literal["gpt", "tinyllama"]
    database: Literal["postgresql", "sqlite"]
    schema_info: Optional[str] = None


class TextToSQLResponse(BaseModel):
    sql_query: str
    execution_time: float
    model: str
    database: str
    success: bool
    error: Optional[str] = None
    result: Optional[list] = None


@router.post("/text-to-sql", response_model=TextToSQLResponse)
async def text_to_sql(
    request: TextToSQLRequest,
    postgres_db: Session = Depends(get_postgres_db),
    sqlite_db: Session = Depends(get_sqlite_db)
):
    """
    Convert natural language text to SQL query using specified LLM and execute on specified database.
    """
    start_time = time.time()
    sql_query = ""
    result = []
    error = None
    
    try:
        # 1. Generate SQL from text using specified model
        if request.model == "gpt":
            sql_query = await gpt.generate_sql_gpt(request.text, request.schema_info)
        elif request.model == "tinyllama":
            sql_query = await tinyllama.generate_sql_tinyllama(request.text, request.schema_info)
        else:
            raise ValueError(f"Unsupported model: {request.model}")
        
        # 2. Execute SQL on specified database
        db = postgres_db if request.database == "postgresql" else sqlite_db
        
        # Execute the query
        query_result = db.execute(text(sql_query))
        
        # Fetch results
        if query_result.returns_rows:
            rows = query_result.fetchall()
            # Convert rows to list of dictionaries
            columns = query_result.keys()
            result = [dict(zip(columns, row)) for row in rows]
        else:
            # For INSERT, UPDATE, DELETE, etc.
            db.commit()
            result = [{"rows_affected": query_result.rowcount}]
        
        execution_time = time.time() - start_time
        
        return TextToSQLResponse(
            sql_query=sql_query,
            execution_time=execution_time,
            model=request.model,
            database=request.database,
            success=True,
            result=result
        )
    except Exception as e:
        execution_time = time.time() - start_time
        error = str(e)
        return TextToSQLResponse(
            sql_query=sql_query if sql_query else "",
            execution_time=execution_time,
            model=request.model,
            database=request.database,
            success=False,
            error=error
        )
