from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.deps import get_db
from app.core.security import get_current_user

from app.schemas.schedule import ScheduleCreate, ScheduleUpdate, ScheduleResponse

from app.services.schedule_service import (
    get_schedule,
    get_schedule_by_id,
    list_schedules,
    upsert_schedule,
    patch_schedule,
    delete_schedule,
    record_run,
)

router = APIRouter(prefix="/schedules", tags=["schedules"])


# ─────────────────────────────────────────────
# LIST ALL SCHEDULES
# ─────────────────────────────────────────────
@router.get("/", response_model=List[ScheduleResponse])
async def list_user_schedules(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    enabled_only: bool = False,
):
    return await list_schedules(
        db=db,
        user_id=str(current_user.id),
        enabled_only=enabled_only,
    )



# ─────────────────────────────────────────────
# GET BY WORKFLOW
# ─────────────────────────────────────────────
@router.get("/workflow/{workflow_id}", response_model=ScheduleResponse)
async def get_schedule_by_workflow_api(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    schedule = await get_schedule(
        db=db,
        workflow_id=workflow_id,
        user_id=str(current_user.id),
    )

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
    schedule = await get_schedule_by_id(
        db=db,
        schedule_id=schedule_id,
        user_id=str(current_user.id),
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return schedule


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
    return await upsert_schedule(
        db=db,
        workflow_id=workflow_id,
        user_id=str(current_user.id),
        payload=payload,
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
    schedule = await get_schedule_by_id(
        db=db,
        schedule_id=schedule_id,
        user_id=str(current_user.id),
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return await patch_schedule(
        db=db,
        schedule=schedule,
        payload=payload,
    )


# ─────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────
@router.delete("/{schedule_id}")
async def delete_schedule_api(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    schedule = await get_schedule_by_id(
        db=db,
        schedule_id=schedule_id,
        user_id=str(current_user.id),
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await delete_schedule(db=db, schedule=schedule)
    return {"status": "deleted"}


# ─────────────────────────────────────────────
# RECORD RUN (called by worker)
# ─────────────────────────────────────────────
@router.post("/{schedule_id}/run")
async def record_schedule_run_api(
    schedule_id: UUID,
    success: bool,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    schedule = await get_schedule_by_id(
        db=db,
        schedule_id=schedule_id,
        user_id=str(current_user.id),
    )

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await record_run(
        db=db,
        schedule=schedule,
        success=success,
    )

    return {"status": "recorded"}