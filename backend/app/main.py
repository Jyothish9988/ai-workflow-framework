import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from sqlalchemy import text

from app.api.auth import auth_router
from app.api.workflow import router as workflow_router

from app.database.db import Base, engine

# IMPORTANT: import models ONCE (this registers metadata)
from app.models.workflow import Workflow
from app.models.workflow_execution import *
from app.models.scheduled_workflow import ScheduledWorkflow  # noqa: F401
from app.api import llm_connections
from app.api.app_integrations import router as app_integrations_router
from app.api.admin import router as admin_router, public_router as packages_router
from app.api.schedule import router as schedule_router
from app.services.run_manager import mark_orphaned_runs
from app.services.scheduler_worker import scheduler_loop


# ============================================================
# Database Initialization
# ============================================================
# create_all() never alters existing tables, so columns added after the first deploy
# are added here (idempotent; PostgreSQL).
_SCHEMA_PATCHES = [
    "ALTER TABLE awf_scheduled_workflows ADD COLUMN IF NOT EXISTS timezone VARCHAR NOT NULL DEFAULT 'UTC'",
    "ALTER TABLE awf_scheduled_workflows ADD COLUMN IF NOT EXISTS last_execution_id VARCHAR",
    "ALTER TABLE awf_scheduled_workflows ADD COLUMN IF NOT EXISTS last_error TEXT",
]


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _SCHEMA_PATCHES:
            await conn.execute(text(stmt))


# ============================================================
# Application lifespan: DB, orphaned runs, cron scheduler
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await mark_orphaned_runs()
    scheduler_task = asyncio.create_task(scheduler_loop())
    try:
        yield
    finally:
        scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await scheduler_task


app = FastAPI(lifespan=lifespan)


# ============================================================
# CORS
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


security = HTTPBearer()


# ============================================================
# Health Check
# ============================================================
@app.get("/health")
async def health():
    return {"status": "healthy"}


# ============================================================
# API Routers
# ============================================================
app.include_router(auth_router)
app.include_router(workflow_router)
app.include_router(schedule_router)
app.include_router(llm_connections.router)
app.include_router(app_integrations_router)
app.include_router(admin_router)
app.include_router(packages_router)