import logging
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bridge.fake import FakeBackend  # noqa: E402
from app.config import AppConfig, Paths  # noqa: E402
from app.main import create_app  # noqa: E402

AUTH = {"Authorization": "Bearer test-key"}


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    paths = Paths(tmp_path / "data")
    paths.ensure()
    return paths


@pytest.fixture
def config(paths: Paths) -> AppConfig:
    cfg = AppConfig(
        api_key="test-key",
        admin_token="test-admin",
        launch_browser_on_start=False,
        max_queue=2,
    )
    cfg.save(paths.config_path)
    return cfg


@pytest.fixture
def fake() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def app(config: AppConfig, paths: Paths, fake: FakeBackend):
    return create_app(config, paths, backend=fake)


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as async_client:
        yield async_client


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("dsb-test")


def sse_events(text: str) -> list[str]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data: "):
            events.append(line[6:])
    return events
