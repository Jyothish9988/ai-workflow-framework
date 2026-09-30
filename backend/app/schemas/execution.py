# app/schemas/execution.py

from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict
from pydantic import BaseModel


class NodeLogOut(BaseModel):
    id: UUID
    node_id: str
    node_type: str
    node_label: Optional[str]
    sequence: int
    status: str

    log_message: Optional[str]
    input_context: Optional[Dict]
    output_context: Optional[Dict]

    error_message: Optional[str]
    branch_taken: Optional[str]

    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[float]

    class Config:
        from_attributes = True


class ExecutionOut(BaseModel):
    id: UUID
    workflow_id: str
    status: str
    trigger_type: str

    nodes_total: int
    nodes_success: int
    nodes_failed: int

    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ExecutionDetailOut(ExecutionOut):
    initial_context: Optional[dict]
    final_context: Optional[dict]
    error_message: Optional[str]
    error_traceback: Optional[str]

    node_logs: List[NodeLogOut] = []