import json

import pytest

from app.bridge.base import Completed, ContentDelta, Failed, ThinkingDelta

from .conftest import AUTH, sse_events


@pytest.mark.asyncio
async def test_models_requires_key(client):
    response = await client.get("/v1/models")
    assert response.status_code == 401
    body = response.json()
    assert "error" in body and "message" in body["error"]


@pytest.mark.asyncio
async def test_models_ok(client):
    response = await client.get("/v1/models", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert data["data"][0]["id"] == "deepseek-web"


@pytest.mark.asyncio
async def test_chat_requires_key(client):
    response = await client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "你好"}]},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_non_stream(client, fake):
    fake.script = [[ContentDelta("你好"), ContentDelta("，世界"), Completed()]]
    response = await client.post(
        "/v1/chat/completions",
        headers=AUTH,
        json={"model": "deepseek-web", "messages": [{"role": "user", "content": "你好"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    choice = body["choices"][0]
    assert choice["message"]["content"] == "你好，世界"
    assert choice["finish_reason"] == "stop"
    assert body["usage"]["total_tokens"] > 0
    assert fake.calls[0]["options"].thinking is False
    assert fake.calls[0]["options"].web_search is False


@pytest.mark.asyncio
async def test_chat_request_overrides_toggles(client, fake):
    fake.script = [[ContentDelta("ok"), Completed()]]
    await client.post(
        "/v1/chat/completions",
        headers=AUTH,
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "thinking": True,
            "web_search": True,
        },
    )
    assert fake.calls[0]["options"].thinking is True
    assert fake.calls[0]["options"].web_search is True


@pytest.mark.asyncio
async def test_chat_stream(client, fake):
    fake.script = [[ContentDelta("第一段"), ContentDelta("第二段"), Completed()]]
    async with client.stream(
        "POST",
        "/v1/chat/completions",
        headers=AUTH,
        json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
    ) as response:
        assert response.status_code == 200
        text = "".join([chunk async for chunk in response.aiter_text()])
    events = sse_events(text)
    assert events[-1] == "[DONE]"
    payloads = [json.loads(item) for item in events[:-1]]
    content = "".join(
        item["choices"][0]["delta"].get("content", "")
        for item in payloads
        if item.get("choices")
    )
    assert content == "第一段第二段"
    assert payloads[-1]["choices"][0]["finish_reason"] == "stop"
    assert payloads[0]["choices"][0]["delta"]["role"] == "assistant"


@pytest.mark.asyncio
async def test_chat_stream_include_usage(client, fake):
    fake.script = [[ContentDelta("x"), Completed()]]
    async with client.stream(
        "POST",
        "/v1/chat/completions",
        headers=AUTH,
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
            "stream_options": {"include_usage": True},
        },
    ) as response:
        text = "".join([chunk async for chunk in response.aiter_text()])
    payloads = [json.loads(item) for item in sse_events(text)[:-1]]
    assert payloads[-1]["usage"]["total_tokens"] >= 1


@pytest.mark.asyncio
async def test_thinking_returned_as_reasoning_content(client, fake):
    fake.script = [[ThinkingDelta("先想一想"), ContentDelta("答案"), Completed()]]
    response = await client.post(
        "/v1/chat/completions",
        headers=AUTH,
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    message = response.json()["choices"][0]["message"]
    assert message["reasoning_content"] == "先想一想"
    assert message["content"] == "答案"


@pytest.mark.asyncio
async def test_tool_call_parsed(client, fake):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "查询城市天气",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
            },
        }
    ]
    fake.script = [
        [
            ContentDelta('{"tool_calls": [{"name": "get_weather", "arguments": {"city": "北京"}}]}'),
            Completed(),
        ]
    ]
    response = await client.post(
        "/v1/chat/completions",
        headers=AUTH,
        json={"messages": [{"role": "user", "content": "北京天气"}], "tools": tools},
    )
    choice = response.json()["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    call = choice["message"]["tool_calls"][0]
    assert call["type"] == "function"
    assert call["function"]["name"] == "get_weather"
    assert json.loads(call["function"]["arguments"]) == {"city": "北京"}
    assert call["id"].startswith("call_")
    sent = fake.calls[0]["messages"]
    assert sent[-1]["role"] == "system"
    assert "工具调用协议" in sent[-1]["content"]


@pytest.mark.asyncio
async def test_tool_call_stream(client, fake):
    tools = [{"type": "function", "function": {"name": "ping", "parameters": {}}}]
    fake.script = [[ContentDelta('{"tool_calls": [{"name": "ping", "arguments": {}}]}'), Completed()]]
    async with client.stream(
        "POST",
        "/v1/chat/completions",
        headers=AUTH,
        json={
            "messages": [{"role": "user", "content": "ping"}],
            "tools": tools,
            "stream": True,
        },
    ) as response:
        text = "".join([chunk async for chunk in response.aiter_text()])
    payloads = [json.loads(item) for item in sse_events(text)[:-1]]
    tool_deltas = [
        delta
        for item in payloads
        for delta in [item["choices"][0]["delta"]]
        if "tool_calls" in delta
    ]
    assert tool_deltas[0]["tool_calls"][0]["function"]["name"] == "ping"
    assert payloads[-1]["choices"][0]["finish_reason"] == "tool_calls"


@pytest.mark.asyncio
async def test_tool_call_invalid_falls_back_to_content(client, fake):
    tools = [{"type": "function", "function": {"name": "ping", "parameters": {}}}]
    fake.script = [[ContentDelta("今天天气不错"), Completed()]]
    response = await client.post(
        "/v1/chat/completions",
        headers=AUTH,
        json={"messages": [{"role": "user", "content": "hi"}], "tools": tools},
    )
    choice = response.json()["choices"][0]
    assert choice["finish_reason"] == "stop"
    assert choice["message"]["content"] == "今天天气不错"


@pytest.mark.asyncio
async def test_tool_result_messages_passed_through(client, fake):
    fake.script = [[ContentDelta("好的"), Completed()]]
    messages = [
        {"role": "user", "content": "北京天气"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"city":"北京"}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "25°C 晴"},
    ]
    await client.post(
        "/v1/chat/completions",
        headers=AUTH,
        json={"messages": messages, "tools": [{"type": "function", "function": {"name": "get_weather"}}]},
    )
    sent = fake.calls[0]["messages"]
    assert sent[-2]["role"] == "tool"
    assert sent[-2]["content"] == "25°C 晴"


@pytest.mark.asyncio
async def test_backend_error_maps_to_status(client, fake):
    fake.script = [[Failed("网页未登录", code="login_required")]]
    response = await client.post(
        "/v1/chat/completions",
        headers=AUTH,
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 503
    assert "未登录" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_stream_error_event(client, fake):
    fake.script = [[Failed("网页繁忙", code="web_error")]]
    async with client.stream(
        "POST",
        "/v1/chat/completions",
        headers=AUTH,
        json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
    ) as response:
        text = "".join([chunk async for chunk in response.aiter_text()])
    events = sse_events(text)
    assert events[-1] == "[DONE]"
    assert any("网页繁忙" in item for item in events[:-1])


@pytest.mark.asyncio
async def test_empty_messages_rejected(client):
    response = await client.post("/v1/chat/completions", headers=AUTH, json={"messages": []})
    assert response.status_code == 400
