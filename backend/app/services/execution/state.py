"""Mutable bookkeeping shared by every (recursive) graph run of one execution."""
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession


class RunState:
    def __init__(self, db: AsyncSession, execution_id):
        self.db = db
        self.execution_id = execution_id
        self.logs: list[str] = []
        self.ns = 0        # nodes succeeded
        self.nf = 0        # nodes failed
        self.nsk = 0       # nodes skipped
        self.seq = 0       # running sequence number for NodeExecutionLog ordering
        self.error = False

    def next_seq(self) -> int:
        v = self.seq
        self.seq += 1
        return v

    def append_log(self, msg: str) -> None:
        self.logs.append(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}")
