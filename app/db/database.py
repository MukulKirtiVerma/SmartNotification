from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pymongo import MongoClient
import redis

from config.config import current_config

# PostgreSQL connection
engine = create_engine(current_config.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# MongoDB connection
mongo_client = MongoClient(current_config.MONGODB_URL)
mongo_db = mongo_client.get_database()

# Redis connection
redis_client = redis.from_url(current_config.REDIS_URL)

def get_db():
    """Get SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_mongo_collection(collection_name):
    """Get MongoDB collection."""
    return mongo_db[collection_name]

def get_redis():
    """Get Redis client."""
    return redis_client