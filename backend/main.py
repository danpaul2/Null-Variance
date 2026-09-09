from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, instruments, sessions, reports, attachments, activity

app = FastAPI(title="NAWI OIML R-76 Test Report System")

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
