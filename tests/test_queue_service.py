import asyncio

import pytest

from app.bridge.base import Failed, SendOptions
from app.service import BridgeService, QueueFullError


@pytest.mark.asyncio
async def test_service_serializes_and_keeps_order(config, fake, logger):
    config.max_queue = 10
    service = BridgeService(fake, config, logger)
    fake.delay = 0.02
    jobs = [
        service.new_job([{"role": "user", "content": f"m{i}"}], SendOptions(), [])
        for i in range(3)
    ]

    async def run(job):
        async for _event in service.iter_events(job):
            pass

    await asyncio.gather(*(run(job) for job in jobs))
    assert fake.max_active == 1
    assert [call["messages"][0]["content"] for call in fake.calls] == ["m0", "m1", "m2"]
    assert all(job.state == "done" for job in jobs)


@pytest.mark.asyncio
async def test_cancel_running_job(config, fake, logger):
    service = BridgeService(fake, config, logger)
    gate = asyncio.Event()
    fake.gate = gate
    job = service.new_job([{"role": "user", "content": "hi"}], SendOptions(), [])
    events = []

    async def consume():
        async for event in service.iter_events(job):
            events.append(event)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    job.cancel_event.set()
    gate.set()
    await task
    assert fake.cancelled is True
    assert any(isinstance(event, Failed) and event.code == "cancelled" for event in events)
    assert job.state == "cancelled"


@pytest.mark.asyncio
async def test_cancel_queued_job_skips_backend(config, fake, logger):
    service = BridgeService(fake, config, logger)
    gate = asyncio.Event()
    fake.gate = gate
    first = service.new_job([{"role": "user", "content": "first"}], SendOptions(), [])
    second = service.new_job([{"role": "user", "content": "second"}], SendOptions(), [])

    async def consume(job):
        collected = []
        async for event in service.iter_events(job):
            collected.append(event)
        return collected

    first_task = asyncio.create_task(consume(first))
    await asyncio.sleep(0.05)
    second.cancel_event.set()
    gate.set()
    await first_task
    events = await consume(second)
    assert any(isinstance(event, Failed) and event.code == "cancelled" for event in events)
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_queue_full(config, fake, logger):
    config.max_queue = 1
    service = BridgeService(fake, config, logger)
    gate = asyncio.Event()
    fake.gate = gate
    service.new_job([{"role": "user", "content": "a"}], SendOptions(), [])
    with pytest.raises(QueueFullError):
        service.new_job([{"role": "user", "content": "b"}], SendOptions(), [])
    gate.set()


@pytest.mark.asyncio
async def test_queue_full_over_http(client, app, fake):
    app.state.config.max_queue = 1
    gate = asyncio.Event()
    fake.gate = gate
    auth = {"Authorization": "Bearer test-key"}
    payload = {"messages": [{"role": "user", "content": "hi"}], "stream": True}

    # httpx 的 ASGI 传输会缓冲整个响应，因此第一个请求必须放在后台任务里。
    first_task = asyncio.create_task(
        client.post("/v1/chat/completions", json=payload, headers=auth)
    )
    for _ in range(200):
        if app.state.service.snapshot()["waiting"] >= 1:
            break
        await asyncio.sleep(0.02)
    assert app.state.service.snapshot()["waiting"] == 1

    second = await client.post("/v1/chat/completions", json=payload, headers=auth)
    assert second.status_code == 429
    assert "队列已满" in second.json()["error"]["message"]

    gate.set()
    first = await asyncio.wait_for(first_task, timeout=15)
    assert first.status_code == 200
    assert "data: [DONE]" in first.text
