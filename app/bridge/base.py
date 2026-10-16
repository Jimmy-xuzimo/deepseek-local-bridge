"""后端抽象：事件模型与接口定义。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import AsyncIterator


class BackendState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    WAITING_LOGIN = "waiting_login"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"


@dataclass
class BackendInfo:
    state: BackendState = BackendState.STOPPED
    detail: str = ""
    logged_in: bool = False
    browser_open: bool = False
    last_error: str | None = None
    channel: str | None = None


@dataclass
class SendOptions:
    thinking: bool = False
    web_search: bool = False
    idle_seconds: float = 2.5
    timeout_seconds: float = 600.0


@dataclass
class Attachment:
    path: Path
    filename: str
    kind: str  # image / file


class BackendError(Exception):
    def __init__(self, message: str, code: str = "backend_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class ThinkingDelta:
    text: str


@dataclass
class ContentDelta:
    text: str


@dataclass
class Completed:
    finish_reason: str = "stop"


@dataclass
class Failed:
    message: str
    code: str = "backend_error"


BackendEvent = ThinkingDelta | ContentDelta | Completed | Failed


class ChatBackend(ABC):
    """聊天后端接口。实现方负责真实浏览器或测试替身。"""

    @abstractmethod
    async def start(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def refresh_state(self, force: bool = False) -> BackendInfo:
        ...

    @abstractmethod
    def info(self) -> BackendInfo:
        ...

    @abstractmethod
    async def ensure_ready(self) -> None:
        ...

    @abstractmethod
    def send(
        self,
        messages: list[dict],
        options: SendOptions,
        attachments: list[Attachment],
        cancel_event,
    ) -> AsyncIterator[BackendEvent]:
        ...

    @abstractmethod
    async def cancel_current(self) -> None:
        ...

    async def diagnose(self) -> dict:
        return {}

    async def focus_browser(self) -> None:
        return None
