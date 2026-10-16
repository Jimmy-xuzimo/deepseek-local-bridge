"""OpenAI 兼容接口：/v1/models、/v1/chat/completions、/v1/files。"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .bridge.base import Attachment, Failed, SendOptions, ThinkingDelta, ContentDelta, Completed
from .bridge.toolcall import build_tool_instructions, parse_tool_calls
from .files_store import MIME_EXTENSIONS, FileStore
from .service import BridgeService, QueueFullError

ERROR_STATUS = {
    "login_required": 503,
    "browser_start_failed": 503,
    "browser_missing": 503,
    "browser_stopped": 503,
    "rate_limited": 429,
    "timeout": 504,
    "no_response": 504,
    "queue_full": 429,
    "cancelled": 499,
    "context_too_long": 413,
    "upload_failed": 502,
    "send_failed": 502,
    "input_not_found": 502,
    "empty_response": 502,
}


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: str = "user"
    content: Any = None
    name: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    stream: bool = False
    stream_options: dict | None = None
    tools: list[dict] | None = None
    tool_choice: Any = None
    thinking: bool | None = None
    web_search: bool | None = None


@dataclass
class ChatResult:
    content: str = ""
    thinking: str = ""
    tool_calls: list | None = None
    finish_reason: str = "stop"
    error_code: str | None = None
    error_message: str | None = None


def require_api_key(request: Request) -> None:
    config = request.app.state.config
    header = request.headers.get("authorization", "")
    token = ""
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
    if not token:
        token = request.headers.get("x-api-key", "").strip()
    if not token or not secrets.compare_digest(token, config.api_key):
        raise HTTPException(
            status_code=401,
            detail="API Key 无效或缺失：请在请求头中携带 Authorization: Bearer <你的 API Key>（设置页可复制）。",
        )


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def _extract_attachments(messages: list[dict], files: FileStore) -> tuple[list[dict], list[Attachment]]:
    attachments: list[Attachment] = []
    for message in messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        new_parts: list[Any] = []
        for part in content:
            if not isinstance(part, dict):
                new_parts.append(part)
                continue
            kind = part.get("type")
            if kind in ("image_url", "input_image"):
                source = part.get("image_url")
                url = source.get("url") if isinstance(source, dict) else source
                if isinstance(url, str) and url.startswith("data:"):
                    stored = _store_data_url(url, files, "image")
                    attachments.append(Attachment(path=stored.path, filename=stored.filename, kind="image"))
                    new_parts.append({"type": "text", "text": f"[图片附件：{stored.filename}]"})
                    continue
                if isinstance(url, str) and url:
                    new_parts.append({"type": "text", "text": f"[图片链接：{url}]"})
                    continue
            if kind == "file":
                nested = part.get("file") if isinstance(part.get("file"), dict) else {}
                file_id = part.get("file_id") or nested.get("file_id")
                file_data = part.get("file_data") or nested.get("file_data")
                filename = part.get("filename") or nested.get("filename") or "attachment.bin"
                if file_id:
                    stored = files.get(str(file_id))
                    if stored is None:
                        raise HTTPException(status_code=400, detail=f"未找到文件 {file_id}，请先通过 /v1/files 上传。")
                    attachments.append(Attachment(path=stored.path, filename=stored.filename, kind="file"))
                    new_parts.append({"type": "text", "text": f"[文件附件：{stored.filename}]"})
                    continue
                if file_data:
                    try:
                        raw = base64.b64decode(str(file_data), validate=False)
                    except (binascii.Error, ValueError) as exc:
                        raise HTTPException(status_code=400, detail="file_data 不是合法的 base64 数据。") from exc
                    stored = _save_bytes(raw, filename, files)
                    attachments.append(Attachment(path=stored.path, filename=stored.filename, kind="file"))
                    new_parts.append({"type": "text", "text": f"[文件附件：{stored.filename}]"})
                    continue
            new_parts.append(part)
        message["content"] = new_parts
    if len(attachments) > 5:
        raise HTTPException(status_code=400, detail="单次请求最多 5 个附件。")
    return messages, attachments


def _store_data_url(url: str, files: FileStore, kind: str):
    try:
        header, encoded = url.split(",", 1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="图片 data URL 格式不正确。") from exc
    mime = header[5:].split(";")[0].strip().lower() if header.startswith("data:") else ""
    extension = MIME_EXTENSIONS.get(mime, ".png" if kind == "image" else ".bin")
    try:
        data = base64.b64decode(encoded, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="data URL 不是合法的 base64 数据。") from exc
    return files.save_bytes(data, f"inline{extension}", kind=kind)


def _save_bytes(data: bytes, filename: str, files: FileStore):
    try:
        return files.save_bytes(data, filename, kind="file")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _build_options(request: Request, payload: ChatCompletionRequest) -> SendOptions:
    config = request.app.state.config
    return SendOptions(
        thinking=config.thinking if payload.thinking is None else bool(payload.thinking),
        web_search=config.web_search if payload.web_search is None else bool(payload.web_search),
        idle_seconds=float(config.idle_seconds),
        timeout_seconds=float(config.request_timeout_seconds),
    )


async def _collect(service: BridgeService, job, tools: list[dict]) -> ChatResult:
    result = ChatResult()
    content_parts: list[str] = []
    thinking_parts: list[str] = []
    async for event in service.iter_events(job):
        if isinstance(event, ThinkingDelta):
            thinking_parts.append(event.text)
        elif isinstance(event, ContentDelta):
            content_parts.append(event.text)
        elif isinstance(event, Completed):
            result.finish_reason = event.finish_reason
        elif isinstance(event, Failed):
            result.error_code = event.code
            result.error_message = event.message
    result.content = "".join(content_parts)
    result.thinking = "".join(thinking_parts)
    if tools:
        calls = parse_tool_calls(result.content, tools)
        if calls:
            result.tool_calls = calls
            result.finish_reason = "tool_calls"
    return result


def _error_response(code: str, message: str) -> JSONResponse:
    status = ERROR_STATUS.get(code, 502)
    return JSONResponse(
        status_code=status,
        content={
            "error": {"message": message, "type": "bridge_error", "code": code},
            "detail": message,
        },
    )


def _completion_payload(result: ChatResult, model: str, prompt_text: str) -> dict:
    message: dict[str, Any] = {"role": "assistant"}
    if result.tool_calls:
        message["content"] = result.content or None
        message["tool_calls"] = [
            {
                "id": call.call_id or f"call_{secrets.token_hex(8)}",
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                },
            }
            for call in result.tool_calls
        ]
    else:
        message["content"] = result.content
    if result.thinking:
        message["reasoning_content"] = result.thinking
    prompt_tokens = _estimate_tokens(prompt_text)
    completion_tokens = _estimate_tokens(result.content + result.thinking)
    return {
        "id": "chatcmpl-" + secrets.token_hex(12),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": result.finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


async def _sse_stream(
    service: BridgeService,
    job,
    tools: list[dict],
    include_usage: bool,
    model: str,
    prompt_text: str,
) -> AsyncIterator[str]:
    chunk_id = "chatcmpl-" + secrets.token_hex(12)
    created = int(time.time())

    def chunk(delta: dict, finish_reason: str | None = None, usage: dict | None = None) -> str:
        payload: dict[str, Any] = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        if usage is not None:
            payload["usage"] = usage
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    yield chunk({"role": "assistant"})
    queue: asyncio.Queue = asyncio.Queue()

    async def pump() -> None:
        try:
            async for event in service.iter_events(job):
                await queue.put(event)
        except Exception as exc:  # noqa: BLE001
            await queue.put(Failed(f"内部错误：{exc}", code="internal_error"))
        finally:
            await queue.put(None)

    task = asyncio.create_task(pump())
    buffered: list[str] = []
    emitted_content = ""
    emitted_thinking = ""
    finish_reason = "stop"
    error: Failed | None = None
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if event is None:
                break
            if isinstance(event, ThinkingDelta):
                emitted_thinking += event.text
                yield chunk({"reasoning_content": event.text})
            elif isinstance(event, ContentDelta):
                if tools:
                    buffered.append(event.text)
                else:
                    emitted_content += event.text
                    yield chunk({"content": event.text})
            elif isinstance(event, Completed):
                finish_reason = event.finish_reason
            elif isinstance(event, Failed):
                error = event
        if tools and buffered:
            text = "".join(buffered)
            calls = parse_tool_calls(text, tools)
            if calls:
                for index, call in enumerate(calls):
                    yield chunk(
                        {
                            "tool_calls": [
                                {
                                    "index": index,
                                    "id": call.call_id or f"call_{secrets.token_hex(8)}",
                                    "type": "function",
                                    "function": {
                                        "name": call.name,
                                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                                    },
                                }
                            ]
                        }
                    )
                finish_reason = "tool_calls"
                emitted_content = text
            else:
                emitted_content = text
                yield chunk({"content": text})
        if error is not None:
            yield "data: " + json.dumps(
                {"error": {"message": error.message, "code": error.code, "type": "bridge_error"}},
                ensure_ascii=False,
            ) + "\n\n"
            finish_reason = "stop"
        usage = None
        if include_usage:
            prompt_tokens = _estimate_tokens(prompt_text)
            completion_tokens = _estimate_tokens(emitted_content + emitted_thinking)
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }
        yield chunk({}, finish_reason=finish_reason, usage=usage)
        yield "data: [DONE]\n\n"
    finally:
        if not task.done():
            job.cancel_event.set()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=8)
            except BaseException:  # noqa: BLE001
                task.cancel()


def build_openai_router() -> APIRouter:
    router = APIRouter()

    @router.get("/models")
    async def list_models(request: Request) -> dict:
        require_api_key(request)
        config = request.app.state.config
        return {
            "object": "list",
            "data": [
                {
                    "id": config.model_name,
                    "object": "model",
                    "created": 0,
                    "owned_by": "deepseek-web-bridge",
                }
            ],
        }

    @router.get("/status")
    async def status(request: Request) -> dict:
        require_api_key(request)
        backend = request.app.state.backend
        service: BridgeService = request.app.state.service
        return {
            "backend": backend.info().__dict__,
            "queue": service.snapshot(),
        }

    @router.post("/chat/completions")
    async def chat_completions(payload: ChatCompletionRequest, request: Request):
        require_api_key(request)
        config = request.app.state.config
        service: BridgeService = request.app.state.service
        files: FileStore = request.app.state.files

        if not payload.messages:
            raise HTTPException(status_code=400, detail="messages 不能为空。")
        extra = payload.model_extra or {}
        if extra.get("n") and int(extra["n"]) > 1:
            raise HTTPException(status_code=400, detail="暂不支持 n>1（网页版一次只生成一条回答）。")

        messages = [message.model_dump(exclude_none=True) for message in payload.messages]
        messages, attachments = _extract_attachments(messages, files)
        tools = payload.tools or []
        if tools:
            messages.append({"role": "system", "content": build_tool_instructions(tools)})

        options = _build_options(request, payload)
        prompt_text = json.dumps(messages, ensure_ascii=False)

        try:
            job = service.new_job(messages, options, attachments)
        except QueueFullError as exc:
            return _error_response("queue_full", f"请求队列已满（上限 {exc.limit}），请稍后重试。")

        if payload.stream:
            include_usage = bool(
                payload.stream_options and payload.stream_options.get("include_usage")
            )
            return StreamingResponse(
                _sse_stream(service, job, tools, include_usage, config.model_name, prompt_text),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                    "Connection": "keep-alive",
                },
            )

        result = await _collect(service, job, tools)
        if result.error_code and not result.content and not result.tool_calls:
            return _error_response(result.error_code, result.error_message or "后端错误")
        return JSONResponse(_completion_payload(result, config.model_name, prompt_text))

    @router.post("/files")
    async def upload_file(
        request: Request,
        file: UploadFile = File(...),
        purpose: str = Form(default="assistants"),
    ) -> dict:
        require_api_key(request)
        files: FileStore = request.app.state.files
        data = await file.read()
        filename = file.filename or "upload.bin"
        try:
            stored = files.save_bytes(data, filename, kind="file")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        stored.purpose = purpose
        return stored.to_public()

    @router.get("/files")
    async def list_files(request: Request) -> dict:
        require_api_key(request)
        files: FileStore = request.app.state.files
        return {"object": "list", "data": [item.to_public() for item in files.list()]}

    @router.get("/files/{file_id}")
    async def get_file(file_id: str, request: Request) -> dict:
        require_api_key(request)
        files: FileStore = request.app.state.files
        stored = files.get(file_id)
        if stored is None:
            raise HTTPException(status_code=404, detail=f"文件 {file_id} 不存在。")
        return stored.to_public()

    @router.delete("/files/{file_id}")
    async def delete_file(file_id: str, request: Request) -> dict:
        require_api_key(request)
        files: FileStore = request.app.state.files
        if not files.delete(file_id):
            raise HTTPException(status_code=404, detail=f"文件 {file_id} 不存在。")
        return {"id": file_id, "object": "file", "deleted": True}

    return router
