from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer

from app.api.auth import auth_router
from app.api.workflow import router as workflow_router

from app.database.db import Base, engine

# IMPORTANT: import models ONCE (this registers metadata)
from app.models.workflow import Workflow
from app.models.workflow_execution import *
from app.api import llm_connections
from app.api.app_integrations import router as app_integrations_router
from app.api.admin import router as admin_router, public_router as packages_router

app = FastAPI()


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
# Database Initialization
# ============================================================
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ============================================================
# Health Check
# ============================================================
@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }


# ============================================================
# Application Startup
# ============================================================
@app.on_event("startup")
async def on_startup():
    await init_db()


# ============================================================
# API Routers
# ============================================================
app.include_router(auth_router)
app.include_router(workflow_router)
app.include_router(llm_connections.router)
app.include_router(app_integrations_router)
app.include_router(admin_router)
app.include_router(packages_router)
