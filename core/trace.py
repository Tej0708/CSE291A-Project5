from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class TraceLogger:
    """Append-only JSONL trace for one workflow run."""

    def __init__(
        self,
        *,
        workflow: str,
        task_id: str,
        log_dir: str | Path,
        run_id: str | None = None,
    ) -> None:
        self.workflow = workflow
        self.task_id = task_id
        self.run_id = run_id or str(uuid4())
        self.started = time.perf_counter()
        self.last_stage: str | None = None

        directory = Path(log_dir) / workflow / task_id
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{self.run_id}.jsonl"

    def log(
        self,
        event_type: str,
        *,
        stage: str | None = None,
        data: dict[str, Any] | None = None,
        parent_ids: list[str] | tuple[str, ...] | None = None,
    ) -> str:
        event_id = str(uuid4())
        if stage is not None:
            self.last_stage = stage
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event_id": event_id,
            "elapsed_ms": round((time.perf_counter() - self.started) * 1000, 3),
            "workflow": self.workflow,
            "task_id": self.task_id,
            "event_type": event_type,
            "stage": stage,
            "parent_ids": list(parent_ids or []),
            "data": data or {},
        }

        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")

        return event_id
