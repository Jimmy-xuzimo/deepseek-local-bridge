import pytest


@pytest.mark.asyncio
async def test_admin_opens_from_localhost_without_token(client):
    """本机访问设置页不再要求令牌（控制台打印的地址可直接打开）。"""
    response = await client.get("/admin/")
    assert response.status_code == 200
    assert "DeepSeek Local Bridge" in response.text


@pytest.mark.asyncio
async def test_admin_blocks_foreign_host(client):
    response = await client.get("/admin/", headers={"host": "evil.example"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_blocks_cross_site_origin(client):
    """跨站请求被拒绝，防止恶意网页 CSRF 调用管理接口。"""
    page = await client.get("/admin/", headers={"origin": "https://evil.example"})
    assert page.status_code == 401
    action = await client.post(
        "/admin/api/action",
        json={"action": "regenerate_api_key"},
        headers={"origin": "https://evil.example", "sec-fetch-site": "cross-site"},
    )
    assert action.status_code == 401


@pytest.mark.asyncio
async def test_admin_allows_same_origin_action(client):
    action = await client.post(
        "/admin/api/action",
        json={"action": "recheck_login"},
        headers={
            "origin": "http://127.0.0.1",
            "sec-fetch-site": "same-origin",
        },
    )
    assert action.status_code == 200


@pytest.mark.asyncio
async def test_admin_token_sets_cookie(client):
    response = await client.get("/admin/", params={"token": "test-admin"})
    assert response.status_code == 303
    assert response.cookies.get("dsb_admin") == "test-admin"


@pytest.mark.asyncio
async def test_admin_state_and_actions(client):
    client.cookies.set("dsb_admin", "test-admin")
    state = await client.get("/admin/api/state")
    assert state.status_code == 200
    body = state.json()
    assert body["config"]["api_key"] == "test-key"
    assert body["backend"]["state"]

    action = await client.post("/admin/api/action", json={"action": "recheck_login"})
    assert action.status_code == 200

    save = await client.post(
        "/admin/api/action",
        json={"action": "save_settings", "settings": {"thinking": True, "idle_seconds": 3.5}},
    )
    assert save.status_code == 200
    assert set(save.json()["changed"]) == {"thinking", "idle_seconds"}

    regen = await client.post("/admin/api/action", json={"action": "regenerate_api_key"})
    assert regen.json()["api_key"].startswith("sk-dsb-")
