import ollama
from app.config import settings
from typing import Optional


async def generate_sql_tinyllama(text: str, schema_info: Optional[str] = None) -> str:
    """
    Generate SQL query from natural language text using TinyLlama via Ollama.
    
    Args:
        text: Natural language query
        schema_info: Optional database schema information
        
    Returns:
        Generated SQL query string
    """
    # Initialize Ollama client with custom base URL if needed
    client = ollama.Client(host=settings.ollama_base_url)
    
    prompt = f"""Convert the following natural language query to SQL.

"""
    
    if schema_info:
        prompt += f"Database schema:\n{schema_info}\n\n"
    
    prompt += f"Natural language query: {text}\n\n"
    prompt += "Generate only the SQL query, without any explanation:"
    
    try:
        response = client.chat(
            model='tinyllama',
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
        raise Exception(f"TinyLlama generation failed: {str(e)}")
