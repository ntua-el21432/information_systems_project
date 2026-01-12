#!/usr/bin/env python3
"""
Test script to run text-to-SQL queries from JSON files against populated databases.
Tests both GPT and TinyLlama models on both PostgreSQL and SQLite databases.

Usage:
    python test_text_to_sql.py <json_file> [--limit N] [--models gpt,tinyllama] [--databases postgresql,sqlite]
    
Examples:
    python test_text_to_sql.py datasets/restaurants.json
    python test_text_to_sql.py datasets/restaurants.json --limit 10 --models gpt --databases postgresql
"""

import json
import sys
import argparse
import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
import re

from sqlalchemy import create_engine, text, inspect

from app.config import settings
from app.llm import gpt, tinyllama


def load_schema_info(schema_file: Optional[str] = None) -> str:
    """Load schema information from CSV file or generate from database."""
    if schema_file and Path(schema_file).exists():
        import csv
        schema_lines = []
        with open(schema_file, 'r') as f:
            reader = csv.DictReader(f)
            current_table = None
            for row in reader:
                # Normalize keys and values (strip whitespace from headers and cells)
                norm_row = { (k.strip() if k else ""): (v.strip() if isinstance(v, str) else v)
                             for k, v in row.items() }
                
                table = norm_row.get('Table Name', '') or ''
                field = norm_row.get('Field Name', '') or ''
                field_type = norm_row.get('Type', '') or ''
                is_pk = (norm_row.get('Is Primary Key', '') or '').lower() == 'y'
                is_fk = (norm_row.get('Is Foreign Key', '') or '').lower() == 'y'
                
                if table and table != '-' and field and field != '-':
                    if table != current_table:
                        if current_table:
                            schema_lines.append("")
                        schema_lines.append(f"Table: {table}")
                        current_table = table
                    
                    pk_str = " PRIMARY KEY" if is_pk else ""
                    fk_str = " FOREIGN KEY" if is_fk else ""
                    schema_lines.append(f"  {field}: {field_type}{pk_str}{fk_str}")
        
        return "\n".join(schema_lines)
    else:
        raise FileNotFoundError(f"Schema file not found: {schema_file}")


def get_schema_from_database(db_type: str = "postgresql") -> str:
    """Extract schema information from database."""
    if db_type == "postgresql":
        url = (
            f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
            f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
        )
    else:
        url = f"sqlite:///{settings.sqlite_path}"
    
    engine = create_engine(url)
    inspector = inspect(engine)
    
    schema_lines = []
    for table_name in inspector.get_table_names():
        schema_lines.append(f"Table: {table_name}")
        columns = inspector.get_columns(table_name)
        for col in columns:
            col_type = str(col['type'])
            pk_str = " PRIMARY KEY" if col.get('primary_key') else ""
            schema_lines.append(f"  {col['name']}: {col_type}{pk_str}")
        schema_lines.append("")
    
    return "\n".join(schema_lines)


def substitute_variables(text: str, variables: Dict[str, str]) -> str:
    """Substitute variables in text with their values."""
    result = text
    for var_name, var_value in variables.items():
        # Replace both "var_name" and var_name patterns
        result = result.replace(f'"{var_name}"', f'"{var_value}"')
        result = result.replace(f"'{var_name}'", f"'{var_value}'")
        result = result.replace(var_name, var_value)
    return result


def normalize_sql(sql: str) -> str:
    """Normalize SQL for comparison (remove extra whitespace, lowercase keywords)."""
    # Remove extra whitespace
    sql = re.sub(r'\s+', ' ', sql)
    # Remove trailing semicolons and whitespace
    sql = sql.strip().rstrip(';').strip()
    return sql.lower()


def compare_sql(generated: str, expected: str) -> bool:
    """Compare generated SQL with expected SQL (normalized)."""
    gen_norm = normalize_sql(generated)
    exp_norm = normalize_sql(expected)
    return gen_norm == exp_norm


async def test_query(
    query_text: str,
    expected_sql: Optional[str],
    model: str,
    database: str,
    schema_info: str
) -> Dict[str, Any]:
    """Test a single query with a model and database."""
    result = {
        "query_text": query_text,
        "model": model,
        "database": database,
        "expected_sql": expected_sql,
        "generated_sql": "",
        "execution_time": 0,
        "generation_time": 0,
        "success": False,
        "error": None,
        "result": None,
        "matches_expected": False
    }
    
    start_time = time.time()
    
    try:
        # Generate SQL using LLM
        gen_start = time.time()
        if model == "gpt":
            generated_sql = await gpt.generate_sql_gpt(query_text, schema_info)
        elif model == "tinyllama":
            generated_sql = await tinyllama.generate_sql_tinyllama(query_text, schema_info)
        else:
            raise ValueError(f"Unknown model: {model}")
        
        result["generation_time"] = time.time() - gen_start
        result["generated_sql"] = generated_sql
        
        # Execute SQL on database
        if database == "postgresql":
            engine = create_engine(
                f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
                f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
            )
        else:
            engine = create_engine(
                f"sqlite:///{settings.sqlite_path}",
                connect_args={"check_same_thread": False}
            )
        
        with engine.connect() as conn:
            exec_result = conn.execute(text(generated_sql))
            
            if exec_result.returns_rows:
                rows = exec_result.fetchall()
                columns = exec_result.keys()
                result["result"] = [dict(zip(columns, row)) for row in rows]
            else:
                conn.commit()
                result["result"] = [{"rows_affected": exec_result.rowcount}]
        
        result["success"] = True
        
        # Compare with expected SQL if provided
        if expected_sql:
            result["matches_expected"] = compare_sql(generated_sql, expected_sql)
        
    except Exception as e:
        result["error"] = str(e)
        result["success"] = False
    
    result["execution_time"] = time.time() - start_time
    return result


async def process_json_queries(
    json_file: str,
    models: List[str],
    databases: List[str],
    limit: Optional[int] = None,
    schema_file: Optional[str] = None
):
    """Process queries from JSON file."""
    # Load JSON file
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Load schema info
    schema_info = load_schema_info(schema_file)
    print(f"Schema info loaded ({len(schema_info)} chars)")
    print("-" * 80)
    
    # Process queries
    all_results = []
    query_count = 0
    
    for item in data:
        if limit and query_count >= limit:
            break
        
        # Extract sentences (natural language queries)
        sentences = item.get("sentences", [])
        expected_sqls = item.get("sql", [])
        
        # Use first sentence and first SQL as primary test case
        if sentences and expected_sqls:
            sentence = sentences[0]
            query_text = sentence.get("text", "")
            variables = sentence.get("variables", {})
            
            # Substitute variables
            query_text = substitute_variables(query_text, variables)
            expected_sql = substitute_variables(expected_sqls[0], variables) if expected_sqls else None
            
            query_count += 1
            print(f"\nQuery {query_count}: {query_text[:60]}...")
            
            # Test with each model and database combination
            for model in models:
                for database in databases:
                    print(f"  Testing: {model} on {database}...", end=" ", flush=True)
                    result = await test_query(query_text, expected_sql, model, database, schema_info)
                    all_results.append(result)
                    
                    if result["success"]:
                        match_str = "✓ MATCH" if result["matches_expected"] else "✗ NO MATCH"
                        print(f"✓ ({result['generation_time']:.2f}s gen, {result['execution_time']:.2f}s total) {match_str}")
                    else:
                        print(f"✗ Error: {result['error']}")
    
    return all_results


def print_summary(results: List[Dict[str, Any]]):
    """Print summary statistics."""
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    
    # Group by model and database
    stats = defaultdict(lambda: {
        "total": 0,
        "successful": 0,
        "failed": 0,
        "matches_expected": 0,
        "total_gen_time": 0,
        "total_exec_time": 0
    })
    
    for result in results:
        key = f"{result['model']} + {result['database']}"
        stats[key]["total"] += 1
        if result["success"]:
            stats[key]["successful"] += 1
            stats[key]["total_gen_time"] += result["generation_time"]
            stats[key]["total_exec_time"] += result["execution_time"]
            if result["matches_expected"]:
                stats[key]["matches_expected"] += 1
        else:
            stats[key]["failed"] += 1
    
    # Print statistics
    for key, stat in stats.items():
        print(f"\n{key}:")
        print(f"  Total queries: {stat['total']}")
        print(f"  Successful: {stat['successful']} ({stat['successful']/stat['total']*100:.1f}%)")
        print(f"  Failed: {stat['failed']} ({stat['failed']/stat['total']*100:.1f}%)")
        if stat['successful'] > 0:
            print(f"  Matches expected SQL: {stat['matches_expected']} ({stat['matches_expected']/stat['successful']*100:.1f}%)")
            print(f"  Avg generation time: {stat['total_gen_time']/stat['successful']:.2f}s")
            print(f"  Avg execution time: {stat['total_exec_time']/stat['successful']:.2f}s")
    
    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Test text-to-SQL queries from JSON file")
    parser.add_argument("json_file", help="Path to JSON file with queries")
    parser.add_argument("schema_file", help="Path to schema CSV file (tables/columns)")
    parser.add_argument("--limit", type=int, help="Limit number of queries to test")
    parser.add_argument("--models", default="gpt,tinyllama", help="Comma-separated list of models")
    parser.add_argument("--databases", default="postgresql,sqlite", help="Comma-separated list of databases")
        
    args = parser.parse_args()
    
    # Parse arguments
    models = [m.strip() for m in args.models.split(",")]
    databases = [d.strip() for d in args.databases.split(",")]
    
    # Validate
    valid_models = ["gpt", "tinyllama"]
    valid_databases = ["postgresql", "sqlite"]
    
    for model in models:
        if model not in valid_models:
            print(f"Error: Invalid model '{model}'. Valid models: {valid_models}")
            sys.exit(1)
    
    for database in databases:
        if database not in valid_databases:
            print(f"Error: Invalid database '{database}'. Valid databases: {valid_databases}")
            sys.exit(1)
    
    # Check files exist
    if not Path(args.json_file).exists():
        print(f"Error: JSON file not found: {args.json_file}")
        sys.exit(1)
    if not Path(args.schema_file).exists():
        print(f"Error: Schema file not found: {args.schema_file}")
        sys.exit(1)
        
    print(f"Testing text-to-SQL queries from: {args.json_file}")
    print(f"Models: {', '.join(models)}")
    print(f"Databases: {', '.join(databases)}")
    if args.limit:
        print(f"Limit: {args.limit} queries")
    
    # Run tests
    try:
        results = asyncio.run(process_json_queries(
            args.json_file,
            models,
            databases,
            args.limit,
            args.schema_file
        ))
        
        # Print summary
        print_summary(results)
        
        # Save results to JSON file
        output_file = f"test_results_{int(time.time())}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: {output_file}")
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
