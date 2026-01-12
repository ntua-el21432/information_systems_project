#!/usr/bin/env python3
"""
Universal SQLite to PostgreSQL Migrator
- Automatically detects schema from SQLite.
- Fixes DECIMAL(1,1) -> NUMERIC to prevent overflows.
- Fixes int(11) -> INTEGER.
- Removes Foreign Keys.
- Forces Quoted Identifiers.
- Isolates transactions per table.
"""

import sqlite3
import sys
import os
import re
from pathlib import Path
from sqlalchemy import create_engine, text
from app.config import settings


def get_source_connection(sqlite_file_path: str) -> sqlite3.Connection:
    if not os.path.exists(sqlite_file_path):
        raise FileNotFoundError(f"Source SQLite file not found: {sqlite_file_path}")
    return sqlite3.connect(sqlite_file_path)


def get_target_engine(target_db: str):
    if target_db.lower() == "postgresql":
        url = (
            f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
            f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        )
        return create_engine(url, pool_pre_ping=True)
    elif target_db.lower() == "sqlite":
        url = f"sqlite:///{settings.sqlite_path}"
        os.makedirs(os.path.dirname(settings.sqlite_path) or ".", exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False})
    else:
        raise ValueError(f"Unsupported target database: {target_db}")


def transpile_schema_to_postgres(sqlite_schema: str, table_name: str) -> str:
    """
    Intelligently converts a raw SQLite CREATE TABLE statement into
    a clean, strict PostgreSQL statement.
    """
    schema = sqlite_schema.strip()
    
    # 1. Remove "IF NOT EXISTS"
    schema = re.sub(r'IF\s+NOT\s+EXISTS\s+', '', schema, flags=re.IGNORECASE)
    
    # 2. Extract Body
    match = re.search(r'CREATE\s+TABLE\s+(?:["`\[]?\w+["`\]]?)\s*\((.*)\)', schema, re.DOTALL | re.IGNORECASE)
    if not match:
        return schema
    
    body = match.group(1)
    
    new_lines = []
    
    # Split by comma safely (handling parens)
    raw_lines = [x.strip() for x in body.split(',')]
    merged_lines = []
    buffer = ""
    
    for line in raw_lines:
        if buffer:
            buffer += ", " + line
        else:
            buffer = line
        if buffer.count('(') == buffer.count(')'):
            merged_lines.append(buffer)
            buffer = ""
            
    for defn in merged_lines:
        defn = defn.strip()
        if not defn: continue
        
        # SKIP Foreign Keys / Constraints
        upper_def = defn.upper()
        if upper_def.startswith(('FOREIGN KEY', 'CONSTRAINT', 'UNIQUE', 'CHECK')):
            continue
            
        parts = defn.split(None, 1)
        if len(parts) < 2: continue
        
        col_name_raw = parts[0]
        rest = parts[1]
        col_name = col_name_raw.strip('"`[]')
        
        # ---------------------------------------------------------
        # TYPE MAPPING CORRECTIONS
        # ---------------------------------------------------------
        type_upper = rest.upper()
        
        # Fix 1: DECIMAL/NUMERIC overflow. 
        # Convert decimal(1,1) or similar to just NUMERIC (unconstrained).
        if 'DECIMAL' in type_upper or 'NUMERIC' in type_upper:
            pg_type = 'NUMERIC' 
        elif 'INT' in type_upper:
            pg_type = 'INTEGER'
        elif 'CHAR' in type_upper or 'TEXT' in type_upper or 'CLOB' in type_upper:
            pg_type = 'TEXT'
        elif 'BLOB' in type_upper:
            pg_type = 'BYTEA'
        elif 'REAL' in type_upper or 'DOUBLE' in type_upper or 'FLOAT' in type_upper:
            pg_type = 'DOUBLE PRECISION'
        else:
            pg_type = rest # Fallback

        # Handle PK / Serial
        if 'AUTOINCREMENT' in type_upper:
            new_lines.append(f'"{col_name}" SERIAL PRIMARY KEY')
        else:
            # Clean up leftovers
            clean_rest = pg_type
            if 'PRIMARY KEY' in type_upper and 'PRIMARY KEY' not in pg_type:
                clean_rest += " PRIMARY KEY"
            
            # Remove sqlite artifacts
            clean_rest = re.sub(r'DEFAULT\s+\'[^\']*\'', '', clean_rest) 
            
            new_lines.append(f'"{col_name}" {clean_rest}')

    columns_block = ",\n  ".join(new_lines)
    final_sql = f'CREATE TABLE "{table_name}" (\n  {columns_block}\n)'
    return final_sql


def copy_table_data(source_conn: sqlite3.Connection, target_conn, table_name: str):
    source_cursor = source_conn.cursor()
    try:
        source_cursor.execute(f'SELECT * FROM "{table_name}"')
    except:
        source_cursor.execute(f'SELECT * FROM {table_name}')
        
    columns = [description[0] for description in source_cursor.description]
    rows = source_cursor.fetchall()
    
    if not rows:
        print(f"  ⚠ No data to copy for table: {table_name}")
        return
    
    placeholders = ", ".join([":" + col for col in columns])
    column_names = ", ".join([f'"{col}"' for col in columns])
    insert_sql = f'INSERT INTO "{table_name}" ({column_names}) VALUES ({placeholders})'
    
    data = [dict(zip(columns, row)) for row in rows]
    
    target_conn.execute(text(insert_sql), data)
    print(f"  ✓ Copied {len(rows)} rows to table: {table_name}")


def populate_database(sqlite_file: str, target_db: str):
    # Path logic
    if not sqlite_file.endswith('.sqlite') and not sqlite_file.endswith('.db'):
        sqlite_file += '.sqlite'
    
    datasets_dir = Path("datasets")
    possible_paths = [datasets_dir / sqlite_file, Path("data") / sqlite_file, Path(sqlite_file)]
    
    sqlite_path = None
    for p in possible_paths:
        if p.exists():
            sqlite_path = p
            break
            
    if not sqlite_path:
        sqlite_path = datasets_dir / sqlite_file.replace('.sqlite', '')
        if not sqlite_path.exists():
            raise FileNotFoundError(f"SQLite file not found. Checked: {[str(p) for p in possible_paths]}")

    print(f"Source: {sqlite_path}")
    print(f"Target: {target_db.upper()}")
    print("-" * 60)

    source_conn = get_source_connection(str(sqlite_path))
    
    try:
        target_engine = get_target_engine(target_db)
        
        cursor = source_conn.cursor()
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = cursor.fetchall()
        
        if not tables:
            print("⚠ No tables found.")
            return
            
        print(f"Found {len(tables)} tables.")
        
        for table_name, sqlite_sql in tables:
            print(f"\nProcessing table: {table_name}")
            
            # ISOLATED TRANSACTION BLOCK
            # Use begin() to ensure we get a fresh transaction for each table
            try:
                with target_engine.begin() as target_conn:
                    # 1. Drop Old
                    if target_db.lower() == "postgresql":
                        target_conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
                    else:
                        target_conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
                    
                    # 2. Create New
                    if target_db.lower() == "postgresql":
                        create_sql = transpile_schema_to_postgres(sqlite_sql, table_name)
                        print(f"  SQL > {create_sql.splitlines()[0]} ...")
                    else:
                        create_sql = sqlite_sql
                    
                    target_conn.execute(text(create_sql))
                    print("  ✓ Created table")
                    
                    # 3. Copy Data
                    copy_table_data(source_conn, target_conn, table_name)
                    # Commit happens automatically at end of 'with' block
            
            except Exception as e:
                print(f"  ✗ Error: {e}")
                # We catch here so the loop continues to the next table!
                    
        print("\n" + "=" * 60)
        print("✓ Auto-migration completed!")
        print("=" * 60)
        
    finally:
        source_conn.close()


def main():
    if len(sys.argv) < 3:
        print("Usage: python populate.py <sqlite_file> <target_db>")
        sys.exit(1)
    
    try:
        populate_database(sys.argv[1], sys.argv[2])
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()