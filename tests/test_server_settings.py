import pytest

from app.netinfo import list_local_ipv4


def test_list_local_ipv4_shape():
    ips = list_local_ipv4()
    assert isinstance(ips, list)
    for ip in ips:
        assert isinstance(ip, str)
        assert not ip.startswith("127.")


@pytest.mark.asyncio
async def test_admin_state_includes_server_urls(client):
    client.cookies.set("dsb_admin", "test-admin")
    state = (await client.get("/admin/api/state")).json()
    server = state["server"]
    assert server["local_url"].startswith("http://127.0.0.1:")
    assert server["local_url"].endswith("/v1")
    assert isinstance(server["lan_urls"], list)
    assert set(server) >= {"bind_host", "port", "serve_on_lan", "cors_enabled"}
    assert state["config"]["serve_on_lan"] is True
    assert state["config"]["cors_enabled"] is True


@pytest.mark.asyncio
async def test_lan_urls_use_port(client):
    client.cookies.set("dsb_admin", "test-admin")
    await client.post(
        "/admin/api/action",
        json={"action": "save_settings", "settings": {"port": 9000}},
    )
    state = (await client.get("/admin/api/state")).json()
    assert state["server"]["port"] == 9000
    assert state["server"]["local_url"] == "http://127.0.0.1:9000/v1"
    for url in state["server"]["lan_urls"]:
        assert url.endswith(":9000/v1")


@pytest.mark.asyncio
async def test_port_validation(client):
    client.cookies.set("dsb_admin", "test-admin")
    too_big = await client.post(
        "/admin/api/action", json={"action": "save_settings", "settings": {"port": 70000}}
    )
    assert too_big.json()["ok"] is False
    not_number = await client.post(
        "/admin/api/action",
        json={"action": "save_settings", "settings": {"port": "abc"}},
    )
    assert not_number.json()["ok"] is False


@pytest.mark.asyncio
async def test_lan_toggle_requires_restart_note(client):
    client.cookies.set("dsb_admin", "test-admin")
    response = await client.post(
        "/admin/api/action",
        json={"action": "save_settings", "settings": {"serve_on_lan": False, "cors_enabled": False}},
    )
    body = response.json()
    assert body["ok"] is True
    assert "重启服务" in body["message"]
    assert "CORS 立即生效" in body["message"]
