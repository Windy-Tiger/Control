"""
Control — Main Application
FastAPI entry point with all routers mounted.
Background alert checker runs every 30 minutes.
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models.database import init_db
from app.routers import auth, users, viagens, pedidos, config, tenants

logger = logging.getLogger("control")

# Alert check interval in seconds (default: 30 min)
ALERT_CHECK_INTERVAL = int(os.getenv("ALERT_CHECK_INTERVAL", "1800"))


async def alert_check_loop():
    """Background loop that checks for alerts every ALERT_CHECK_INTERVAL seconds."""
    # Wait 60s after startup before first check
    await asyncio.sleep(60)

    while True:
        try:
            from app.email_alerts import check_and_send_alerts
            await check_and_send_alerts()
        except Exception as e:
            logger.error(f"Alert check loop error: {e}")

        await asyncio.sleep(ALERT_CHECK_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    init_db()
    # Ensure media directory exists
    media_dir = os.getenv("MEDIA_DIR", "/app/media")
    os.makedirs(media_dir, exist_ok=True)

    # Start background alert checker
    resend_key = os.getenv("RESEND_API_KEY", "")
    if resend_key:
        task = asyncio.create_task(alert_check_loop())
        logger.info("Alert checker started (interval: %ds)", ALERT_CHECK_INTERVAL)
    else:
        task = None
        logger.info("RESEND_API_KEY not set — alert emails disabled")

    yield

    # Shutdown: cancel background task
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


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
