import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load DATABASE_URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Create the engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # helps with dropped connections
)

# Create a sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()
Base.metadata.create_all(engine)
# Dependency to get a database session
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
