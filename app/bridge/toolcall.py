"""工具调用桥接：把 OpenAI tools 转成网页提示词，并解析模型输出的工具调用。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

TOOL_PROTOCOL_TEMPLATE = """【工具调用协议】
你可以调用下面定义的工具来完成任务。当且仅当需要调用工具时，请只输出一个 JSON 对象，不要输出任何其他文字、解释或 Markdown 代码块标记。格式必须严格为：
{{"tool_calls": [{{"name": "工具名称", "arguments": {{参数对象}}}}]}}
如果不需要调用工具，就只输出正常的文字回答，不要输出 JSON。
可用工具定义（JSON Schema）：
{tools_json}"""


@dataclass
class ToolCallRequest:
    name: str
    arguments: dict
    call_id: str = ""


def build_tool_instructions(tools: list[dict]) -> str:
    rendered = json.dumps(
        [
            {
                "name": (tool.get("function") or {}).get("name"),
                "description": (tool.get("function") or {}).get("description", ""),
                "parameters": (tool.get("function") or {}).get("parameters", {}),
            }
            for tool in tools
            if isinstance(tool, dict)
        ],
        ensure_ascii=False,
        indent=2,
    )
    return TOOL_PROTOCOL_TEMPLATE.format(tools_json=rendered)


def extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def parse_tool_calls(text: str, tools: list[dict]) -> list[ToolCallRequest] | None:
    """尝试把模型输出解析为工具调用；无法解析时返回 None（按普通回答处理）。"""
    if not text or not text.strip() or not tools:
        return None
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.S)
    candidate = fence.group(1).strip() if fence else stripped
    data = None
    try:
        data = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        obj = extract_first_json_object(candidate)
        if obj is not None:
            try:
                data = json.loads(obj)
            except (json.JSONDecodeError, ValueError):
                return None
    if not isinstance(data, dict):
        return None
    raw_calls = data.get("tool_calls")
    if raw_calls is None and "name" in data:
        raw_calls = [data]
    if not isinstance(raw_calls, list) or not raw_calls:
        return None
    allowed = {
        (tool.get("function") or {}).get("name")
        for tool in tools
        if isinstance(tool, dict)
    }
    allowed.discard(None)
    calls: list[ToolCallRequest] = []
    for item in raw_calls:
        if not isinstance(item, dict):
            return None
        nested = item.get("function") if isinstance(item.get("function"), dict) else {}
        name = item.get("name") or nested.get("name")
        args = item.get("arguments", nested.get("arguments")) if ("arguments" in item or "arguments" in nested) else None
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, ValueError):
                return None
        if args is None:
            args = {}
        if not isinstance(name, str) or name not in allowed:
            return None
        if not isinstance(args, dict):
            return None
        calls.append(ToolCallRequest(name=name, arguments=args))
    return calls or None
