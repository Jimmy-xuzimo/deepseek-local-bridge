import pytest

from .conftest import AUTH


@pytest.mark.asyncio
async def test_cors_preflight_enabled(client):
    response = await client.options(
        "/v1/chat/completions",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "authorization" in response.headers["access-control-allow-headers"]
    assert response.headers["access-control-allow-methods"] == "*"


@pytest.mark.asyncio
async def test_cors_headers_on_normal_request(client):
    response = await client.get(
        "/v1/models", headers={**AUTH, "Origin": "http://localhost:3000"}
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


@pytest.mark.asyncio
async def test_no_cors_headers_without_origin(client):
    response = await client.get("/v1/models", headers=AUTH)
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_cors_can_be_disabled_at_runtime(client, app):
    app.state.config.cors_enabled = False
    response = await client.get(
        "/v1/models", headers={**AUTH, "Origin": "http://example.com"}
    )
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    preflight = await client.options(
        "/v1/chat/completions",
        headers={"Origin": "http://example.com", "Access-Control-Request-Method": "POST"},
    )
    assert preflight.status_code != 200
