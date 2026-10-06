from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database.deps import get_db
from app.schemas.schedule import ScheduleCreate, ScheduleResponse, ScheduleUpdate
from app.services.run_manager import RunnerBusy
from app.services.schedule_service import (
    delete_schedule,
    dispatch_run,
    get_schedule,
    get_schedule_by_id,
    list_schedules,
    patch_schedule,
    record_run,
    upsert_schedule,
)
from app.services.workflow_service import get_workflow

router = APIRouter(prefix="/schedules", tags=["schedules"])


async def _schedule_or_404(db: AsyncSession, schedule_id: UUID, user):
    schedule = await get_schedule_by_id(db=db, schedule_id=schedule_id, user_id=str(user.id))
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


# ─────────────────────────────────────────────
# LIST ALL SCHEDULES
# ─────────────────────────────────────────────
@router.get("/", response_model=List[ScheduleResponse])
async def list_user_schedules(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    enabled_only: bool = False,
):
    return await list_schedules(db=db, user_id=str(current_user.id), enabled_only=enabled_only)


# ─────────────────────────────────────────────
# GET BY WORKFLOW
# ─────────────────────────────────────────────
@router.get("/workflow/{workflow_id}", response_model=ScheduleResponse)
async def get_schedule_by_workflow_api(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    schedule = await get_schedule(db=db, workflow_id=workflow_id, user_id=str(current_user.id))
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


# ─────────────────────────────────────────────
# GET BY ID
# ─────────────────────────────────────────────
@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule_by_id_api(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await _schedule_or_404(db, schedule_id, current_user)


# ─────────────────────────────────────────────
# CREATE / UPSERT
# ─────────────────────────────────────────────
@router.post("/{workflow_id}", response_model=ScheduleResponse)
async def upsert_schedule_api(
    workflow_id: UUID,
    payload: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # The workflow must exist AND belong to the caller (previously unchecked).
    if not await get_workflow(db, workflow_id, current_user.id):
        raise HTTPException(status_code=404, detail="Workflow not found")

    return await upsert_schedule(
        db=db, workflow_id=workflow_id, user_id=str(current_user.id), payload=payload
    )


# ─────────────────────────────────────────────
# PATCH
# ─────────────────────────────────────────────
@router.patch("/{schedule_id}", response_model=ScheduleResponse)
async def patch_schedule_api(
    schedule_id: UUID,
    payload: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    schedule = await _schedule_or_404(db, schedule_id, current_user)
    try:
        return await patch_schedule(db=db, schedule=schedule, payload=payload)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ─────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────
@router.delete("/{schedule_id}")
async def delete_schedule_api(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    schedule = await _schedule_or_404(db, schedule_id, current_user)
    await delete_schedule(db=db, schedule=schedule)
    return {"status": "deleted"}


# ─────────────────────────────────────────────
# RUN NOW  (starts the workflow immediately, in the background)
# ─────────────────────────────────────────────
@router.post("/{schedule_id}/run-now", status_code=202)
async def run_schedule_now_api(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    schedule = await _schedule_or_404(db, schedule_id, current_user)
    try:
        execution_id = await dispatch_run(db, schedule)
    except RunnerBusy as e:
        raise HTTPException(status_code=503, detail=str(e))
    except (ValueError, RuntimeError) as e:       # empty workflow / no Start node, ...
        raise HTTPException(status_code=400, detail=str(e))

    await db.commit()   # persist counters before the run can finish and update the same row
    return {"execution_id": execution_id, "status": "running"}


# ─────────────────────────────────────────────
# RECORD RUN (manual bookkeeping; kept for backwards compatibility)
# ─────────────────────────────────────────────
@router.post("/{schedule_id}/run")
async def record_schedule_run_api(
    schedule_id: UUID,
    success: bool,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    schedule = await _schedule_or_404(db, schedule_id, current_user)
    await record_run(db=db, schedule=schedule, success=success)
    return {"status": "recorded"}