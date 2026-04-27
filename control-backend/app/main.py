"""
Control — Main Application
FastAPI entry point with all routers mounted.
Background alert checker runs every 30 minutes.
"""

import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.models.database import init_db
from app.routers import auth, users, viagens, pedidos, config, tenants
from app.auth import require_admin

# Alert check interval in seconds (default: 30 min)
ALERT_CHECK_INTERVAL = int(os.getenv("ALERT_CHECK_INTERVAL", "1800"))


async def alert_check_loop():
    """Background loop that checks for alerts every ALERT_CHECK_INTERVAL seconds."""
    await asyncio.sleep(60)
    print(f"[ALERTS] First check starting...")

    while True:
        try:
            from app.email_alerts import check_and_send_alerts
            await check_and_send_alerts()
            print(f"[ALERTS] Check completed.")
        except Exception as e:
            print(f"[ALERTS] Error: {e}")
            import traceback
            traceback.print_exc()

        await asyncio.sleep(ALERT_CHECK_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    media_dir = os.getenv("MEDIA_DIR", "/app/media")
    os.makedirs(media_dir, exist_ok=True)

    resend_key = os.getenv("RESEND_API_KEY", "")
    if resend_key:
        task = asyncio.create_task(alert_check_loop())
        print(f"[ALERTS] Alert checker started (interval: {ALERT_CHECK_INTERVAL}s, key: {resend_key[:8]}...)")
    else:
        task = None
        print("[ALERTS] RESEND_API_KEY not set — alert emails disabled")

    yield

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(viagens.router)
app.include_router(pedidos.router)
app.include_router(config.router)
app.include_router(tenants.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "control-api"}


@app.post("/admin/trigger-alerts")
async def trigger_alerts(current_user: dict = Depends(require_admin)):
    """Manually trigger alert check (admin only). For testing."""
    from app.email_alerts import check_and_send_alerts
    try:
        await check_and_send_alerts()
        return {"status": "ok", "message": "Alert check completed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
