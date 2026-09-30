from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from app.models.user import User

from app.database.deps import get_db
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse
from app.services.workflow_service import (
    create_workflow,
    get_workflows,
    get_workflow,
    update_workflow,
    delete_workflow,
)
from app.core.security import get_current_user
from app.services.execution_engine import cancel_execution
from app.services.run_manager import start_run
from app.models.workflow_execution import (
    WorkflowExecution, NodeExecutionLog,
    ExecutionStatus,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, workflow_id: UUID, user_id: UUID):
    wf = await get_workflow(db, workflow_id, user_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


# ─────────────────────────────────────────────
# WORKFLOW CRUD
# ─────────────────────────────────────────────

@router.post("/", response_model=WorkflowResponse, status_code=201)
async def create(
    payload: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return await create_workflow(db, current_user.id, payload)


@router.get("/", response_model=list[WorkflowResponse])
async def list_all(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return await get_workflows(db, current_user.id)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def retrieve(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return await _get_or_404(db, workflow_id, current_user.id)


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update(
    workflow_id: UUID,
    payload: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    wf = await _get_or_404(db, workflow_id, current_user.id)
    return await update_workflow(db, wf, payload)


@router.delete("/{workflow_id}", status_code=204)
async def destroy(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    wf = await _get_or_404(db, workflow_id, current_user.id)
    await delete_workflow(db, wf)


# ─────────────────────────────────────────────
# SAVE WORKFLOW NODES/EDGES
# ─────────────────────────────────────────────

class WorkflowSavePayload(BaseModel):
    nodes: list[dict] = []
    edges: list[dict] = []


@router.post("/{workflow_id}/save", response_model=WorkflowResponse)
async def save(
    workflow_id: UUID,
    payload: WorkflowSavePayload,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    Persist the canvas state (nodes + edges) for a workflow.
    Stored inside workflow_json as { "nodes": [...], "edges": [...] },
    matching what the frontend's ReactFlow editor sends and reads back.
    """
    wf = await _get_or_404(db, workflow_id, current_user.id)
    update_payload = WorkflowUpdate(
        workflow_json={"nodes": payload.nodes, "edges": payload.edges}
    )
    return await update_workflow(db, wf, update_payload)


# ─────────────────────────────────────────────
# EXECUTE WORKFLOW
# ─────────────────────────────────────────────

@router.post("/{workflow_id}/execute", status_code=202)
async def execute(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Starts the run in the background and returns at once; poll /executions/{id}."""
    wf = await _get_or_404(db, workflow_id, current_user.id)

    if not wf.workflow_json:
        raise HTTPException(400, "Workflow has no nodes")

    try:
        execution_id = await start_run(wf.workflow_json, workflow_id, current_user.id)
    except RuntimeError as e:            # invalid workflow (e.g. no Start node) or server busy
        raise HTTPException(400, str(e))

    return {"execution_id": execution_id, "status": "running"}


# ─────────────────────────────────────────────
# LIST EXECUTIONS (WORKFLOW SCOPED)
# ─────────────────────────────────────────────

@router.get("/{workflow_id}/executions")
async def list_executions(
    workflow_id: UUID,
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    await _get_or_404(db, workflow_id, current_user.id)

    q = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.workflow_id == str(workflow_id),
            WorkflowExecution.user_id == str(current_user.id),
        )
        .order_by(desc(WorkflowExecution.created_at))
    )

    if status:
        q = q.where(WorkflowExecution.status == status)

    result = await db.execute(q.limit(limit).offset(offset))

    return {
        "data": result.scalars().all()
    }


# ─────────────────────────────────────────────
# EXECUTION STATS
# ─────────────────────────────────────────────

@router.get("/{workflow_id}/executions/stats")
async def execution_stats(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    await _get_or_404(db, workflow_id, current_user.id)

    base = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.workflow_id == str(workflow_id),
            WorkflowExecution.user_id == str(current_user.id),
        )
    )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    success = (await db.execute(select(func.count()).select_from(
        base.where(WorkflowExecution.status == ExecutionStatus.SUCCESS).subquery()
    ))).scalar() or 0

    failed = (await db.execute(select(func.count()).select_from(
        base.where(WorkflowExecution.status == ExecutionStatus.FAILED).subquery()
    ))).scalar() or 0

    partial = (await db.execute(select(func.count()).select_from(
        base.where(WorkflowExecution.status == ExecutionStatus.PARTIAL).subquery()
    ))).scalar() or 0

    avg_ms = (await db.execute(
        select(func.avg(WorkflowExecution.duration_ms)).select_from(base.subquery())
    )).scalar()

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "partial": partial,
        "success_rate": round(success / total * 100, 1) if total else 0.0,
        "avg_duration_ms": round(avg_ms) if avg_ms else None,
    }


# ─────────────────────────────────────────────
# EXECUTION DETAIL (WORKFLOW SCOPED)
# ─────────────────────────────────────────────

@router.get("/{workflow_id}/executions/{execution_id}")
async def get_execution(
    workflow_id: UUID,
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    await _get_or_404(db, workflow_id, current_user.id)

    result = await db.execute(
        select(WorkflowExecution)
        .options(selectinload(WorkflowExecution.node_logs))
        .where(
            WorkflowExecution.id == str(execution_id),
            WorkflowExecution.workflow_id == str(workflow_id),
            WorkflowExecution.user_id == str(current_user.id),
        )
    )

    ex = result.scalar_one_or_none()

    if not ex:
        raise HTTPException(404, "Execution not found")

    return {
        "data": ex
    }


# ─────────────────────────────────────────────
# EXECUTION NODES
# ─────────────────────────────────────────────

@router.get("/{workflow_id}/executions/{execution_id}/nodes")
async def get_execution_nodes(
    workflow_id: UUID,
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    await _get_or_404(db, workflow_id, current_user.id)

    result = await db.execute(
        select(WorkflowExecution).where(
            WorkflowExecution.id == str(execution_id),
            WorkflowExecution.workflow_id == str(workflow_id),
            WorkflowExecution.user_id == str(current_user.id),
        )
    )
    ex = result.scalar_one_or_none()

    if not ex:
        raise HTTPException(404, "Execution not found")

    result = await db.execute(
        select(NodeExecutionLog)
        .where(NodeExecutionLog.execution_id == str(execution_id))
        .order_by(NodeExecutionLog.sequence)
    )

    return {
        "data": result.scalars().all()
    }


# ─────────────────────────────────────────────
# DELETE EXECUTION
# ─────────────────────────────────────────────

@router.delete("/{workflow_id}/executions/{execution_id}", status_code=204)
async def delete_execution(
    workflow_id: UUID,
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    await _get_or_404(db, workflow_id, current_user.id)

    ex = await db.get(WorkflowExecution, str(execution_id))

    if not ex or str(ex.user_id) != str(current_user.id):
        raise HTTPException(404, "Execution not found")

    await db.delete(ex)
    await db.commit()


# ─────────────────────────────────────────────
# CANCEL EXECUTION
# ─────────────────────────────────────────────

@router.post("/{workflow_id}/executions/{execution_id}/cancel")
async def cancel_workflow_execution(
    workflow_id:  UUID,
    execution_id: UUID,
    db:           AsyncSession  = Depends(get_db),
    current_user: User          = Depends(get_current_user),
):
    """
    Send a cancellation signal to a running workflow execution.
    The executor checks for this signal at every node boundary, so
    the execution will stop within milliseconds (or after the current
    node finishes, whichever comes first).
    """
    execution = await db.get(WorkflowExecution, str(execution_id))

    if not execution or str(execution.workflow_id) != str(workflow_id):
        raise HTTPException(status_code=404, detail="Execution not found")

    if str(execution.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    if execution.status != ExecutionStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail=f"Execution is not running (current status: {execution.status})",
        )

    found = cancel_execution(str(execution_id))

    if not found:
        # The execution finished between our status check and the cancel call.
        # This is a harmless race — just report it.
        # Not running in this process (e.g. server restarted): close the stale row.
        execution.status = ExecutionStatus.CANCELLED
        await db.commit()
        return {"message": "Execution was no longer active; marked as cancelled", "execution_id": str(execution_id)}

    return {"message": "Cancellation signal sent", "execution_id": str(execution_id)}