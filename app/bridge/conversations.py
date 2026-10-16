"""网页对话注册表：把客户端的每个会话映射到对应的 DeepSeek 网页对话。

只保存对话 URL 与消息指纹（不保存消息内容），可持久化到数据目录，
这样服务重启后仍然能切回之前的网页对话。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConversationEntry:
    url: str
    state_fp: str
    last_used: float


class ConversationRegistry:
    def __init__(self, path: Path, limit: int = 50) -> None:
        self._path = path
        self._limit = max(1, int(limit))
        self._entries: list[ConversationEntry] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, list):
            return
        for item in raw:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            state_fp = str(item.get("state_fp") or "")
            if not url or not state_fp:
                continue
            self._entries.append(
                ConversationEntry(
                    url=url,
                    state_fp=state_fp,
                    last_used=float(item.get("last_used") or 0.0),
                )
            )
        self._trim()

    def save(self) -> None:
        payload = [
            {"url": item.url, "state_fp": item.state_fp, "last_used": item.last_used}
            for item in self._entries
        ]
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except OSError:
            pass

    def _trim(self) -> None:
        if len(self._entries) <= self._limit:
            return
        self._entries.sort(key=lambda item: item.last_used, reverse=True)
        self._entries = self._entries[: self._limit]

    def find(self, state_fp: str) -> ConversationEntry | None:
        """按“上一次请求的完整状态指纹”查找对应的网页对话。"""
        if not state_fp:
            return None
        matches = [item for item in self._entries if item.state_fp == state_fp]
        if not matches:
            return None
        return max(matches, key=lambda item: item.last_used)

    def upsert(self, url: str, state_fp: str) -> ConversationEntry:
        now = time.time()
        for item in self._entries:
            if item.url == url:
                item.state_fp = state_fp
                item.last_used = now
                self._trim()
                self.save()
                return item
        entry = ConversationEntry(url=url, state_fp=state_fp, last_used=now)
        self._entries.append(entry)
        self._trim()
        self.save()
        return entry

    def entries(self) -> list[ConversationEntry]:
        return list(self._entries)
