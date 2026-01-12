import ollama
from app.config import settings
from typing import Optional, List, Dict


async def generate_sql_gpt(
    text: str,
    schema_info: Optional[str] = None,
    examples: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Generate SQL query from natural language text using GPT-OSS via Ollama.
    
    Args:
        text: Natural language query
        schema_info: Optional database schema information
        
    Returns:
        Generated SQL query string
    """
    # Initialize Ollama client with custom base URL if needed
    client = ollama.Client(host=settings.ollama_base_url)
    
    prompt = (
        "You are a senior SQL expert.\n"
        "Generate ONE SQL statement that answers the question.\n"
        "Rules:\n"
        "- Use ONLY the tables/columns listed in the schema.\n"
        "- Do NOT invent table or column names.\n"
        "- Do NOT prefix tables with schema names; use plain table names.\n"
        "- Prefer ANSI JOINs.\n"
        "- Return ONLY the SQL (no markdown or commentary).\n"
    )
    
    if schema_info:
        prompt += f"\nSchema:\n{schema_info}\n"

    if examples:
        prompt += "\nExample pairs of question -> SQL:\n"
        for ex in examples:
            q = ex.get("question", "").strip()
            s = ex.get("sql", "").strip()
            if q and s:
                prompt += f"- Q: {q}\n  SQL: {s}\n"
        prompt += "\nUse the same table/column names; do not invent schemas or prefixes.\n"
    
    prompt += f"\nQuestion: {text}\nSQL:"
    
    try:
        response = client.chat(
            model='gpt-oss',  # GPT-OSS model via Ollama
            messages=[
                {
                    'role': 'system',
                    'content': 'You are a SQL expert. Convert natural language queries to SQL.'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            options={
                'temperature': 0.1,
            }
        )
        
        # Ollama returns a response - handle both dict and object formats
        if isinstance(response, dict):
            sql_query = response.get('message', {}).get('content', '').strip()
        else:
            sql_query = response.message.content.strip()
        
        # Clean up the response (remove markdown code blocks if present)
        if sql_query.startswith('```sql'):
            sql_query = sql_query[6:]
        if sql_query.startswith('```'):
            sql_query = sql_query[3:]
        if sql_query.endswith('```'):
            sql_query = sql_query[:-3]
        sql_query = sql_query.strip()
        
        return sql_query
    except Exception as e:
        raise Exception(f"GPT-OSS generation failed: {str(e)}")
