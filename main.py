# main.py
# FastAPI application entry point — mounts all routers and configures middleware
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from database.db import Base, engine
import models.models  # noqa: F401  — ensures all models are registered before create_all
from routes.auth import router as auth_router
from routes.users import router as users_router
from routes.posts import router as posts_router
from routes.jobs import router as jobs_router
from routes.connections import router as connections_router
from routes.messages import router as messages_router
from routes.notifications import router as notifications_router

load_dotenv()

# ── Create all tables ─────────────────────────────────────────────────────────
# In production, prefer Alembic migrations instead of create_all.
Base.metadata.create_all(bind=engine)

# ── Ensure upload directory exists ────────────────────────────────────────────
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── App instance ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Profio API",
    description="Professional social networking platform",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static file serving (uploaded avatars / post images) ─────────────────────
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(posts_router)
app.include_router(jobs_router)
app.include_router(connections_router)
app.include_router(messages_router)
app.include_router(notifications_router)


@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "message": "Profio API is running"}
