import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.database import Base
from app.db.seed import seed_database
from app.api.deps import get_db_session
from app.db import models
from main import app

# SQLite in-memory database for fast, isolated tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables and seed data
Base.metadata.create_all(bind=engine)
with TestingSessionLocal() as session:
    seed_database(session)

def override_get_db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db_session] = override_get_db_session

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
