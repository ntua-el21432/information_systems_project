from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # PostgreSQL settings
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "llmsql2_db"
    
    # SQLite settings
    sqlite_path: str = "./data/sqlite.db"

    # Optional schema description file (CSV) used to guide text-to-SQL models
    schema_csv_path: str = "./datasets/restaurants-schema.csv"
    
    # Ollama settings
    ollama_base_url: str = "http://localhost:11434"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
