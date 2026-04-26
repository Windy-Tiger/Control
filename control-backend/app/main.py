"""
Control — Main Application
FastAPI entry point with all routers mounted.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.database import init_db
from app.routers import auth, users, viagens, pedidos, config, tenants


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    init_db()
    # Ensure media directory exists
    media_dir = os.getenv("MEDIA_DIR", "/app/media")
    os.makedirs(media_dir, exist_ok=True)
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="Control API",
    description="Gestão de Transportes — Backend API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the frontend (Netlify, local dev, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(viagens.router)
app.include_router(pedidos.router)
app.include_router(config.router)
app.include_router(tenants.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "control-api"}
