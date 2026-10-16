import base64

import pytest

from app.bridge.base import Completed, ContentDelta

from .conftest import AUTH

TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.mark.asyncio
async def test_upload_list_delete(client):
    response = await client.post(
        "/v1/files",
        headers=AUTH,
        files={"file": ("notes.txt", b"hello bridge", "text/plain")},
        data={"purpose": "assistants"},
    )
    assert response.status_code == 200
    stored = response.json()
    assert stored["id"].startswith("file-")
    assert stored["bytes"] == len(b"hello bridge")

    listing = await client.get("/v1/files", headers=AUTH)
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()["data"]] == [stored["id"]]

    detail = await client.get(f"/v1/files/{stored['id']}", headers=AUTH)
    assert detail.status_code == 200

    deleted = await client.delete(f"/v1/files/{stored['id']}", headers=AUTH)
    assert deleted.status_code == 200
    missing = await client.get(f"/v1/files/{stored['id']}", headers=AUTH)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_reject_unsupported_extension(client):
    response = await client.post(
        "/v1/files",
        headers=AUTH,
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "不支持" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_chat_with_uploaded_file(client, fake):
    upload = await client.post(
        "/v1/files",
        headers=AUTH,
        files={"file": ("magic.txt", "密语：蓝鲸-73".encode("utf-8"), "text/plain")},
    )
    file_id = upload.json()["id"]
    fake.script = [[ContentDelta("蓝鲸-73"), Completed()]]

    response = await client.post(
        "/v1/chat/completions",
        headers=AUTH,
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请读取附件中的密语"},
                        {"type": "file", "file_id": file_id},
                    ],
                }
            ]
        },
    )
    assert response.status_code == 200
    attachments = fake.calls[0]["attachments"]
    assert len(attachments) == 1
    assert attachments[0].path.read_text(encoding="utf-8") == "密语：蓝鲸-73"
    sent_content = fake.calls[0]["messages"][0]["content"]
    assert any(part.get("type") == "text" and "文件附件" in part.get("text", "") for part in sent_content)


@pytest.mark.asyncio
async def test_chat_with_inline_image(client, fake):
    fake.script = [[ContentDelta("红色"), Completed()]]
    response = await client.post(
        "/v1/chat/completions",
        headers=AUTH,
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "这是什么颜色"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{TINY_PNG_B64}"},
                        },
                    ],
                }
            ]
        },
    )
    assert response.status_code == 200
    attachments = fake.calls[0]["attachments"]
    assert attachments[0].kind == "image"
    assert base64.b64decode(TINY_PNG_B64) == attachments[0].path.read_bytes()


@pytest.mark.asyncio
async def test_unknown_file_id_rejected(client):
    response = await client.post(
        "/v1/chat/completions",
        headers=AUTH,
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "file", "file_id": "file-doesnotexist"}],
                }
            ]
        },
    )
    assert response.status_code == 400
