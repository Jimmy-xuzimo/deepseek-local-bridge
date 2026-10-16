"""请求串行化：一个账号同一时间只处理一条消息，其余排队。"""

from __future__ import annotations

import asyncio
import itertools
import time
from collections import deque
from dataclasses import dataclass, field
from typing import AsyncIterator

from .bridge.base import Attachment, BackendError, BackendEvent, Failed, SendOptions


class QueueFullError(Exception):
    def __init__(self, limit: int) -> None:
        super().__init__(f"请求队列已满（{limit}）")
        self.limit = limit


@dataclass
class Job:
    id: str
    messages: list[dict]
    options: SendOptions
    attachments: list[Attachment]
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    state: str = "queued"
    error: str | None = None

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "state": self.state,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }


class BridgeService:
    def __init__(self, backend, config, logger) -> None:
        self._backend = backend
        self._cfg = config
        self._log = logger
        self._lock = asyncio.Lock()
        self._waiting = 0
        self._active: str | None = None
        self._jobs: deque[Job] = deque(maxlen=30)
        self._last_error: str | None = None
        self._counter = itertools.count(1)

    @property
    def backend(self):
        return self._backend

    def new_job(
        self, messages: list[dict], options: SendOptions, attachments: list[Attachment]
    ) -> Job:
        limit = max(1, int(self._cfg.max_queue))
        if self._waiting >= limit:
            raise QueueFullError(limit)
        self._waiting += 1
        job = Job(
            id=f"job-{next(self._counter)}",
            messages=messages,
            options=options,
            attachments=attachments,
        )
        self._jobs.append(job)
        return job

    async def iter_events(self, job: Job) -> AsyncIterator[BackendEvent]:
        try:
            async with self._lock:
                if job.cancel_event.is_set():
                    job.state = "cancelled"
                    job.finished_at = time.time()
                    yield Failed("请求已取消", code="cancelled")
                    return
                job.state = "running"
                job.started_at = time.time()
                self._active = job.id
                try:
                    async for event in self._backend.send(
                        job.messages, job.options, job.attachments, job.cancel_event
                    ):
                        if isinstance(event, Failed):
                            job.error = event.message
                            if event.code == "cancelled":
                                job.state = "cancelled"
                            else:
                                job.state = "failed"
                                self._last_error = event.message
                        yield event
                except BackendError as exc:
                    job.error = str(exc)
                    job.state = "failed"
                    self._last_error = str(exc)
                    yield Failed(str(exc), code=exc.code)
                except asyncio.CancelledError:
                    job.state = "cancelled"
                    raise
                except Exception as exc:  # noqa: BLE001
                    self._log.exception("处理 %s 时发生内部错误", job.id)
                    message = f"内部错误：{exc.__class__.__name__}: {exc}"
                    job.error = message
                    job.state = "failed"
                    self._last_error = message
                    yield Failed(message, code="internal_error")
                else:
                    if job.state == "running":
                        job.state = "done"
                finally:
                    job.finished_at = time.time()
                    self._active = None
        finally:
            self._waiting = max(0, self._waiting - 1)

    def snapshot(self) -> dict:
        return {
            "waiting": self._waiting,
            "active_job": self._active,
            "last_error": self._last_error,
            "jobs": [job.to_public() for job in list(self._jobs)[-10:]],
        }
