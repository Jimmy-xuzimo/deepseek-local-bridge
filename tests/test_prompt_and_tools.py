from app.bridge.base import SendOptions
from app.bridge.prompt import (
    content_to_text,
    conversation_fingerprint,
    is_continuation,
    render_conversation,
    render_last_turn,
)
from app.bridge.toolcall import build_tool_instructions, parse_tool_calls

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "运行测试",
            "parameters": {"type": "object", "properties": {}},
        },
    }
]


def test_content_to_text_handles_parts():
    parts = [
        {"type": "text", "text": "看看这张图"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
        {"type": "file", "filename": "report.pdf"},
    ]
    text = content_to_text(parts)
    assert "看看这张图" in text
    assert "[图片附件]" in text
    assert "report.pdf" in text


def test_render_conversation_includes_roles_and_tools():
    messages = [
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": "帮我跑测试"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"function": {"name": "run_tests", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "content": "全部通过", "tool_call_id": "call_1"},
    ]
    rendered = render_conversation(messages)
    assert "【系统指令】" in rendered
    assert "【用户】" in rendered
    assert "run_tests" in rendered
    assert "【工具结果" in rendered
    assert "全部通过" in rendered


def test_render_last_turn_returns_last_user_message():
    messages = [
        {"role": "user", "content": "第一句"},
        {"role": "assistant", "content": "好的"},
        {"role": "user", "content": "第二句"},
    ]
    assert render_last_turn(messages) == "第二句"


def test_fingerprint_enables_continuation_detection():
    options = SendOptions()
    first = [{"role": "user", "content": "第一句"}]
    second = first + [{"role": "assistant", "content": "好的"}, {"role": "user", "content": "第二句"}]
    stored = conversation_fingerprint(first, options)
    assert conversation_fingerprint(second[:-2], options, []) == stored
    assert conversation_fingerprint(second, options) != stored
    assert is_continuation(first, second, options) is True
    assert is_continuation(first, first, options) is False
    assert is_continuation(None, second, options) is False


def test_continuation_requires_assistant_in_between():
    options = SendOptions()
    prev = [{"role": "user", "content": "第一句"}]
    messages = prev + [{"role": "user", "content": "第二句"}, {"role": "user", "content": "第三句"}]
    assert is_continuation(prev, messages, options) is False


def test_continuation_ignores_volatile_system_messages():
    """Chatbox 每次都会注入带时间戳的 system-reminder，不应因此重建对话。"""
    options = SendOptions()
    first = [
        {"role": "system", "content": "system-reminder: 当前时间 2026-10-16 21:00"},
        {"role": "user", "content": "你好"},
    ]
    second = [
        {"role": "system", "content": "system-reminder: 当前时间 2026-10-16 21:05"},
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么可以帮你的吗？"},
        {"role": "user", "content": "你是谁"},
    ]
    assert is_continuation(first, second, options) is True


def test_continuation_rejects_changed_history():
    options = SendOptions()
    first = [{"role": "user", "content": "你好"}]
    second = [
        {"role": "user", "content": "完全不同的开头"},
        {"role": "assistant", "content": "回答"},
        {"role": "user", "content": "你是谁"},
    ]
    assert is_continuation(first, second, options) is False


def test_continuation_rejects_tool_loop_tail():
    """工具调用轮次最后一条是 tool 结果，必须重建上下文而不是把旧消息重发一次。"""
    options = SendOptions()
    first = [{"role": "user", "content": "北京天气"}]
    second = [
        {"role": "user", "content": "北京天气"},
        {"role": "assistant", "content": None, "tool_calls": [{"function": {"name": "get_weather", "arguments": "{}"}}]},
        {"role": "tool", "content": "25°C", "tool_call_id": "call_1"},
    ]
    assert is_continuation(first, second, options) is False


def test_fingerprint_differs_when_toggles_change():
    messages = [{"role": "user", "content": "hi"}]
    assert conversation_fingerprint(messages, SendOptions(thinking=False)) != conversation_fingerprint(
        messages, SendOptions(thinking=True)
    )


def test_build_tool_instructions_lists_names():
    text = build_tool_instructions(TOOLS)
    assert "工具调用协议" in text
    assert "run_tests" in text


def test_parse_tool_calls_plain_json():
    calls = parse_tool_calls('{"tool_calls": [{"name": "run_tests", "arguments": {}}]}', TOOLS)
    assert calls and calls[0].name == "run_tests"


def test_parse_tool_calls_code_fence():
    text = '好的：\n```json\n{"tool_calls": [{"name": "run_tests", "arguments": {}}]}\n```'
    calls = parse_tool_calls(text, TOOLS)
    assert calls and calls[0].name == "run_tests"


def test_parse_tool_calls_rejects_unknown_tool():
    assert parse_tool_calls('{"tool_calls": [{"name": "rm_rf", "arguments": {}}]}', TOOLS) is None


def test_parse_tool_calls_rejects_bad_arguments():
    assert parse_tool_calls('{"tool_calls": [{"name": "run_tests", "arguments": "not-json"}]}', TOOLS) is None


def test_parse_tool_calls_plain_text_returns_none():
    assert parse_tool_calls("今天天气不错", TOOLS) is None
