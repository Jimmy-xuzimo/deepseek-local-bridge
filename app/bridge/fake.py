"""测试用假后端：按脚本返回事件，并记录收到的请求。"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from .base import (
    BackendEvent,
    BackendInfo,
    BackendState,
    ChatBackend,
    Completed,
    ContentDelta,
    Failed,
)


class FakeBackend(ChatBackend):
    def __init__(self, script: list[list[BackendEvent]] | None = None, delay: float = 0.0) -> None:
        self.script: list[list[BackendEvent]] = list(script or [])
        self.delay = delay
        self.calls: list[dict] = []
        self.gate: asyncio.Event | None = None
        self.active = 0
        self.max_active = 0
        self.cancelled = False
        self._state = BackendState.STOPPED
        self.started = False

    async def start(self) -> None:
        self.started = True
        self._state = BackendState.READY

    async def stop(self) -> None:
        self._state = BackendState.STOPPED

    async def refresh_state(self, force: bool = False) -> BackendInfo:
        return self.info()

    def info(self) -> BackendInfo:
        return BackendInfo(
            state=self._state,
            detail="fake",
            logged_in=self._state in (BackendState.READY, BackendState.BUSY),
            browser_open=self.started,
        )

    async def ensure_ready(self) -> None:
        if not self.started:
            await self.start()

    async def cancel_current(self) -> None:
        return None

    async def send(
        self,
        messages: list[dict],
        options,
        attachments: list,
        cancel_event,
    ) -> AsyncIterator[BackendEvent]:
        self.calls.append(
            {"messages": messages, "options": options, "attachments": list(attachments)}
        )
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.gate is not None:
                await self.gate.wait()
            events = self.script.pop(0) if self.script else [ContentDelta("测试回答"), Completed()]
            for event in events:
                if self.delay:
                    await asyncio.sleep(self.delay)
                if cancel_event.is_set():
                    self.cancelled = True
                    yield Failed("请求已取消", code="cancelled")
                    return
                yield event
        finally:
            self.active -= 1
