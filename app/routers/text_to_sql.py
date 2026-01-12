from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Literal, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import time
import csv
from functools import lru_cache
from pathlib import Path

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


# --- Helpers ---------------------------------------------------------------
@lru_cache()
def load_schema_from_csv(schema_path: str = "/app/datasets/restaurants-schema.csv") -> Optional[str]:
    """
    Load a human-readable schema description from the provided CSV.
    Falls back to None if the file is missing.
    """
    csv_path = Path(schema_path)
    if not csv_path.exists():
        return None

    lines = []
    try:
        with csv_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            current_table = None
            for row in reader:
                table = row.get("Table Name", "").strip()
                field = row.get("Field Name", "").strip()
                ftype = row.get("Type", "").strip()
                is_pk = row.get("Is Primary Key", "").strip().lower() == "y"
                is_fk = row.get("Is Foreign Key", "").strip().lower() == "y"

                if table and table != "-" and field and field != "-":
                    if table != current_table:
                        if current_table:
                            lines.append("")
                        lines.append(f"Table: {table}")
                        current_table = table

                    pk = " PRIMARY KEY" if is_pk else ""
                    fk = " FOREIGN KEY" if is_fk else ""
                    lines.append(f"  {field}: {ftype}{pk}{fk}")
        if lines:
            # Add a guidance footer to prevent schema prefixes
            lines.append("")
            lines.append("Notes: Do NOT prefix table names with a schema. Tables are: GEOGRAPHIC, RESTAURANT, LOCATION.")
            return "\n".join(lines)
    except Exception:
        return None

    return None


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
        # If caller didn't provide schema info, attempt to load from CSV
        schema_info = request.schema_info or load_schema_from_csv()

        # 1. Generate SQL from text using specified model
        if request.model == "gpt":
            sql_query = await gpt.generate_sql_gpt(request.text, schema_info)
        elif request.model == "tinyllama":
            sql_query = await tinyllama.generate_sql_tinyllama(request.text, schema_info)
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
