from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, instruments, sessions, reports, attachments, activity
from app.db.database import engine, Base, SessionLocal
from app.db.seed import seed_database
import app.db.models  # ensure models are registered with Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist (Alembic or create_all for startup convenience)
    Base.metadata.create_all(bind=engine)
    # Seed demo data if database is empty
    with SessionLocal() as db:
        seed_database(db)
    yield

app = FastAPI(
    title="NAWI OIML R-76 Test Report System",
    lifespan=lifespan
)

origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(instruments.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(attachments.router, prefix="/api")
app.include_router(activity.router, prefix="/api")

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
