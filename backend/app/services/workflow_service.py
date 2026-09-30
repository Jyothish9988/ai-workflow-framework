from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate


async def create_workflow(
    db: AsyncSession,
    user_id: UUID,
    workflow_data: WorkflowCreate
):
    workflow = Workflow(
        user_id=user_id,
        name=workflow_data.name,
        description=workflow_data.description,
        workflow_json=workflow_data.workflow_json
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def get_workflows(
    db: AsyncSession,
    user_id: UUID
):
    result = await db.execute(
        select(Workflow).where(Workflow.user_id == user_id)
    )
    return result.scalars().all()


async def get_workflow(
    db: AsyncSession,
    workflow_id: UUID,
    user_id: UUID
):
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def update_workflow(
    db: AsyncSession,
    workflow: Workflow,
    payload: WorkflowUpdate
):
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(workflow, key, value)
    workflow.version += 1
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def delete_workflow(
    db: AsyncSession,
    workflow: Workflow
):
    await db.delete(workflow)
    await db.commit()