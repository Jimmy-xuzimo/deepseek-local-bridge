"""把 OpenAI 风格的消息转换为网页可理解的一段文本。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .base import Attachment, SendOptions

ROLE_LABELS = {
    "user": "用户",
    "assistant": "助手",
    "system": "系统指令",
    "developer": "系统指令",
}

# 客户端（如 Chatbox）常注入带时间戳的 system/developer 提醒，属于易变内容，
# 判断“能否续聊”时需要忽略它们，否则每条消息都会被误判成新对话。
VOLATILE_ROLES = {"system", "developer"}


def content_to_text(content: Any) -> str:
    """把消息 content（字符串或分段数组）转成纯文本。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    items = content if isinstance(content, list) else [content]
    for part in items:
        if isinstance(part, str):
            parts.append(part)
            continue
        if not isinstance(part, dict):
            continue
        kind = part.get("type")
        if kind in ("text", "input_text"):
            parts.append(str(part.get("text", "")))
        elif kind in ("image_url", "input_image"):
            parts.append("[图片附件]")
        elif kind == "file":
            nested = part.get("file") if isinstance(part.get("file"), dict) else {}
            name = part.get("filename") or nested.get("filename") or "附件"
            parts.append(f"[文件附件：{name}]")
    return "\n".join(part for part in parts if part)


def render_message(message: dict) -> str:
    role = str(message.get("role", "user"))
    body = content_to_text(message.get("content"))
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        rendered = []
        for call in tool_calls:
            fn = call.get("function") if isinstance(call, dict) else None
            fn = fn if isinstance(fn, dict) else {}
            rendered.append(f"{fn.get('name', '?')}({fn.get('arguments', '{}')})")
        suffix = "（调用工具：" + "；".join(rendered) + "）"
        body = (body + "\n" if body else "") + suffix
    if role == "tool":
        name = message.get("name") or message.get("tool_call_id") or ""
        label = f"工具结果：{name}" if name else "工具结果"
        return f"【{label}】\n{body}"
    label = ROLE_LABELS.get(role, role)
    return f"【{label}】\n{body}"


def render_conversation(messages: list[dict]) -> str:
    """把完整对话渲染成一条消息（用于新会话或历史分支）。"""
    chunks = [
        render_message(message)
        for message in messages
        if content_to_text(message.get("content")) or message.get("tool_calls") or message.get("role") == "tool"
    ]
    header = (
        "以下是一段来自本地 API 的对话记录（可能包含系统指令、工具定义与工具结果）。"
        "请基于全部上下文，直接继续回答最后一条消息；不要复述这段说明，也不要提及这是被转发的对话。"
    )
    return header + "\n\n" + "\n\n".join(chunks)


def render_last_turn(messages: list[dict]) -> str:
    """只渲染最后一条用户消息（用于续聊，不重复发送历史）。"""
    for message in reversed(messages):
        if message.get("role") == "user":
            text = content_to_text(message.get("content"))
            if text:
                return text
    if messages:
        return content_to_text(messages[-1].get("content"))
    return ""


def conversation_fingerprint(
    messages: list[dict],
    options: SendOptions | None = None,
    attachments: list[Attachment] | None = None,
) -> str:
    """对消息、开关状态与附件做指纹，用于判断能否复用网页会话。"""
    items = []
    for message in messages:
        calls = []
        for call in message.get("tool_calls") or []:
            if isinstance(call, dict):
                calls.append(json.dumps(call.get("function", {}), sort_keys=True, ensure_ascii=False))
        items.append(
            [
                message.get("role"),
                content_to_text(message.get("content")),
                calls,
                message.get("tool_call_id"),
            ]
        )
    payload = {
        "messages": items,
        "thinking": bool(options.thinking) if options else False,
        "web_search": bool(options.web_search) if options else False,
        "attachments": [[a.filename, a.kind] for a in (attachments or [])],
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def is_continuation(
    prev_messages: list[dict] | None,
    messages: list[dict],
    options: SendOptions | None = None,
) -> bool:
    """判断本次请求是否是上一次请求的自然续聊（客户端在上次回答后追加了新消息）。"""
    state_fp = continuation_state_fingerprint(messages, options)
    if state_fp is None or not prev_messages:
        return False
    return state_fp == conversation_fingerprint(
        [m for m in prev_messages if str(m.get("role")) not in VOLATILE_ROLES], options, []
    )


def continuation_state_fingerprint(
    messages: list[dict],
    options: SendOptions | None = None,
) -> str | None:
    """如果本次请求是在续聊，返回“上一轮完整状态”的指纹，否则返回 None。

    规则：最后一条是用户消息、倒数第二条是助手消息；指纹只覆盖用户/助手/工具消息
    （system/developer 常被客户端注入时间戳等易变内容，因此忽略）。
    """
    if not messages:
        return None
    if str(messages[-1].get("role")) != "user":
        return None
    core = [m for m in messages if str(m.get("role")) not in VOLATILE_ROLES]
    if len(core) < 2 or str(core[-1].get("role")) != "user" or str(core[-2].get("role")) != "assistant":
        return None
    return conversation_fingerprint(core[:-2], options, [])
