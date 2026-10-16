from app.bridge.base import SendOptions
from app.bridge.conversations import ConversationRegistry
from app.bridge.prompt import continuation_state_fingerprint, conversation_fingerprint


def test_registry_upsert_find_and_persist(tmp_path):
    path = tmp_path / "conversations.json"
    registry = ConversationRegistry(path)
    assert registry.find("fp1") is None

    registry.upsert("https://chat.deepseek.com/a/chat/s/aaa", "fp1")
    entry = registry.find("fp1")
    assert entry is not None and entry.url.endswith("aaa")

    registry.upsert("https://chat.deepseek.com/a/chat/s/aaa", "fp2")
    assert registry.find("fp1") is None
    assert registry.find("fp2") is not None

    reloaded = ConversationRegistry(path)
    assert reloaded.find("fp2") is not None
    assert len(reloaded.entries()) == 1


def test_registry_trims_to_limit(tmp_path):
    registry = ConversationRegistry(tmp_path / "c.json", limit=2)
    registry.upsert("u1", "f1")
    registry.upsert("u2", "f2")
    registry.upsert("u3", "f3")
    assert len(registry.entries()) == 2


def test_continuation_state_fingerprint_matches_registry_state():
    options = SendOptions()
    first = {"role": "user", "content": "第一句"}
    answer = {"role": "assistant", "content": "回答一"}
    second = {"role": "user", "content": "第二句"}

    # 注册表保存的是“已处理过的消息列表”（不含客户端保存的助手回答）
    state_fp = conversation_fingerprint([first], options, [])
    request = [dict(first), dict(answer), dict(second)]
    assert continuation_state_fingerprint(request, options) == state_fp

    with_volatile_system = [
        {"role": "system", "content": "current time 21:05"},
        *request,
    ]
    assert continuation_state_fingerprint(with_volatile_system, options) == state_fp


def test_continuation_state_fingerprint_rejects_non_continuations():
    options = SendOptions()
    assert continuation_state_fingerprint([{"role": "user", "content": "只有一句"}], options) is None
    tool_tail = [
        {"role": "user", "content": "问题"},
        {"role": "assistant", "content": "答"},
        {"role": "tool", "content": "工具结果", "tool_call_id": "c1"},
    ]
    assert continuation_state_fingerprint(tool_tail, options) is None
