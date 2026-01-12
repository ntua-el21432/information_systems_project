#!/usr/bin/env python3
"""
Simple script to inspect database tables, columns, and row counts.
Usage:
    python review_database.py [postgresql|sqlite]
"""

import sys
import os
from sqlalchemy import create_engine, inspect, text
from app.config import settings

def get_engine(db_type="postgresql"):
    if db_type.lower() == "postgresql":
        print(f"🔌 Connecting to PostgreSQL ({settings.postgres_host})...")
        url = (
            f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
            f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        )
    elif db_type.lower() == "sqlite":
        print(f"🔌 Connecting to SQLite ({settings.sqlite_path})...")
        url = f"sqlite:///{settings.sqlite_path}"
    else:
        raise ValueError("Invalid database type. Use 'postgresql' or 'sqlite'.")
    
    return create_engine(url)

def inspect_database(db_type):
    try:
        engine = get_engine(db_type)
        inspector = inspect(engine)
        
        table_names = inspector.get_table_names()
        
        if not table_names:
            print("⚠️  No tables found in the database.")
            return

        print(f"\n📊 Found {len(table_names)} Tables:")
        print("=" * 60)

        with engine.connect() as conn:
            for table in table_names:
                # Get Row Count
                try:
                    # Quote table name for safety
                    count_query = text(f'SELECT COUNT(*) FROM "{table}"')
                    row_count = conn.execute(count_query).scalar()
                except Exception as e:
                    row_count = "Error fetching count"

                print(f"\n📁 TABLE: {table} (Rows: {row_count})")
                print("-" * 60)
                
                # Get Columns
                columns = inspector.get_columns(table)
                # Header
                print(f"{'Column Name':<30} {'Type':<20} {'PK':<5} {'Nullable'}")
                print("-" * 60)
                
                for col in columns:
                    name = col['name']
                    dtype = str(col['type'])
                    pk = "✅" if col.get('primary_key') else ""
                    nullable = "✅" if col.get('nullable') else "❌"
                    
                    print(f"{name:<30} {dtype:<20} {pk:<5} {nullable}")
                print("\n")

    except Exception as e:
        print(f"\n❌ Error inspecting database: {e}")

if __name__ == "__main__":
    db_choice = "postgresql"
    if len(sys.argv) > 1:
        db_choice = sys.argv[1]
    
    inspect_database(db_choice)