from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
import os

# PostgreSQL engine
postgres_url = (
    f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
)
postgres_engine = create_engine(postgres_url, pool_pre_ping=True)
PostgresSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=postgres_engine)

# SQLite engine
sqlite_url = f"sqlite:///{settings.sqlite_path}"
# Ensure data directory exists
os.makedirs(os.path.dirname(settings.sqlite_path) or ".", exist_ok=True)
sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
SQLiteSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)

Base = declarative_base()


# Dependency to get PostgreSQL session
def get_postgres_db():
    db = PostgresSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Dependency to get SQLite session
def get_sqlite_db():
    db = SQLiteSessionLocal()
    try:
        yield db
    finally:
        db.close()
