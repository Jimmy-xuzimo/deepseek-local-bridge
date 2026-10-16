"""真实链路验收脚本：登录后对运行中的服务逐项检查。

用法（在项目根目录）：
    .venv\\Scripts\\python.exe verify\\real_check.py
可选参数：
    --base-url http://127.0.0.1:8317
    --api-key sk-dsb-xxx        （默认从数据目录 config.json 读取）
    --data-dir C:\\path         （默认 %LOCALAPPDATA%\\DeepSeekBridge）
    --quick                     只检查服务与登录状态
退出码：0 全部通过；1 存在失败；2 未登录或服务不可用。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import struct
import sys
import tempfile
import time
import zipfile
import zlib
from pathlib import Path

import httpx

TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

TEST_DELAY = 3.0  # 每次真实请求之间的间隔，避免触发网页限流（--delay 可调）


def default_data_dir() -> Path:
    env = os.environ.get("DSB_DATA_DIR", "").strip()
    if env:
        return Path(env)
    base = os.environ.get("LOCALAPPDATA", "").strip()
    return (Path(base) if base else Path.home() / ".local" / "share") / "DeepSeekBridge"


def make_docx(path: Path) -> None:
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>密语是 蓝鲸-73</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)


def make_pdf(path: Path) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length 44 >>\nstream\nBT /F1 14 Tf 30 100 Td (MAGIC-91) Tj ET\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


def make_solid_png(path: Path, width: int = 64, height: int = 64, rgb: tuple[int, int, int] = (220, 40, 40)) -> None:
    """生成一张纯色 PNG（不依赖 Pillow）。"""
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


class Reporter:
    def __init__(self) -> None:
        self.results: list[tuple[str, str, str]] = []

    def record(self, name: str, status: str, detail: str = "") -> None:
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "➖"}[status]
        print(f"{icon} {name}" + (f" — {detail}" if detail else ""), flush=True)
        self.results.append((name, status, detail))

    def summary(self) -> int:
        fails = [item for item in self.results if item[1] == "FAIL"]
        warns = [item for item in self.results if item[1] == "WARN"]
        print("\n" + "=" * 56)
        print(f"共 {len(self.results)} 项：通过 {len(self.results) - len(fails) - len(warns)}，"
              f"警告 {len(warns)}，失败 {len(fails)}")
        for name, status, detail in self.results:
            if status in ("FAIL", "WARN"):
                print(f"  [{status}] {name}: {detail}")
        print("=" * 56)
        return 1 if fails else 0


def chat(client: httpx.Client, reporter: Reporter, name: str, payload: dict, expect: str | None = None,
         status: str = "PASS", delay: float | None = None) -> dict | None:
    wait = TEST_DELAY if delay is None else delay
    if wait:
        time.sleep(wait)
    started = time.monotonic()
    response = client.post("/v1/chat/completions", json=payload)
    elapsed = time.monotonic() - started
    if response.status_code != 200:
        hint = "（网页限流：稍等几分钟再试，或调大设置页的“请求最小间隔”）" if response.status_code == 429 else ""
        reporter.record(name, "FAIL", f"HTTP {response.status_code}{hint}: {response.text[:200]}")
        return None
    body = response.json()
    content = (body["choices"][0]["message"].get("content") or "")
    if expect and expect not in content:
        reporter.record(name, "FAIL", f"{elapsed:.1f}s 内未在回答中找到“{expect}”，实际回答：{content[:120]}")
        return body
    reporter.record(name, status, f"{elapsed:.1f}s，{len(content)} 字")
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepSeek Local Bridge 真实验收")
    parser.add_argument("--base-url", default="http://127.0.0.1:8317")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--only-attachments", action="store_true", help="只检查附件相关项目")
    parser.add_argument("--only-tools", action="store_true", help="只检查工具调用相关项目")
    parser.add_argument("--delay", type=float, default=3.0, help="每个测试之间的间隔秒数（避免触发网页限流）")
    args = parser.parse_args()
    global TEST_DELAY
    TEST_DELAY = max(0.0, float(args.delay))

    data_dir = Path(args.data_dir) if args.data_dir else default_data_dir()
    api_key = args.api_key
    if not api_key:
        config_path = data_dir / "config.json"
        if not config_path.exists():
            print(f"找不到配置文件 {config_path}；请先启动服务或用 --api-key 指定。")
            return 2
        api_key = json.loads(config_path.read_text(encoding="utf-8"))["api_key"]

    reporter = Reporter()
    headers = {"Authorization": f"Bearer {api_key}"}
    timeout = httpx.Timeout(600.0, connect=10.0)

    with httpx.Client(base_url=args.base_url.rstrip("/"), headers=headers, timeout=timeout) as client:
        try:
            health = client.get("/healthz")
        except httpx.HTTPError as exc:
            print(f"无法连接服务 {args.base_url}：{exc}")
            return 2
        if health.status_code != 200:
            reporter.record("服务健康检查", "FAIL", health.text[:200])
            return reporter.summary()
        reporter.record("服务健康检查", "PASS", health.json().get("version", ""))

        status = client.get("/v1/status")
        if status.status_code != 200:
            reporter.record("登录状态", "FAIL", f"HTTP {status.status_code}")
            return reporter.summary()
        backend = status.json()["backend"]
        if not backend.get("logged_in"):
            reporter.record("登录状态", "FAIL", f"{backend.get('detail', '')}；请先在设置页完成登录后重试。")
            reporter.summary()
            return 2
        reporter.record("登录状态", "PASS", backend.get("channel", ""))

        models = client.get("/v1/models")
        model_id = models.json()["data"][0]["id"] if models.status_code == 200 else "deepseek-web"
        reporter.record("模型列表", "PASS" if models.status_code == 200 else "FAIL", model_id)
        if args.quick:
            return reporter.summary()

        if not (args.only_attachments or args.only_tools):
            _check_chat_and_options(client, reporter, model_id)

        if not args.only_tools:
            _check_attachments(client, reporter, model_id)

        if not args.only_attachments:
            _check_tools(client, reporter, model_id)

    return reporter.summary()


def _check_chat_and_options(client: httpx.Client, reporter: Reporter, model_id: str) -> None:
    chat(client, reporter, "普通聊天（非流式）", {
        "model": model_id,
        "messages": [{"role": "user", "content": "请只回复四个字：桥接正常"}],
    })

    started = time.monotonic()
    first_token_at = None
    collected: list[str] = []
    time.sleep(TEST_DELAY)
    with client.stream("POST", "/v1/chat/completions", json={
        "model": model_id,
        "messages": [{"role": "user", "content": "请从 1 数到 5，用逗号分隔"}],
        "stream": True,
    }) as response:
        if response.status_code != 200:
            reporter.record("流式聊天", "FAIL", f"HTTP {response.status_code}")
        else:
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                try:
                    delta = json.loads(payload)["choices"][0]["delta"]
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta.get("content"):
                    if first_token_at is None:
                        first_token_at = time.monotonic() - started
                    collected.append(delta["content"])
            text = "".join(collected)
            if text.strip():
                ttft = f"{first_token_at:.1f}s" if first_token_at else "?"
                reporter.record("流式聊天", "PASS", f"首字 {ttft}，共 {len(text)} 字")
            else:
                reporter.record("流式聊天", "FAIL", "没有收到任何内容")

    thinking = chat(client, reporter, "深度思考开关", {
        "model": model_id,
        "thinking": True,
        "messages": [{"role": "user", "content": "9.11 和 9.9 哪个大？请简要说明"}],
    })
    if thinking is not None:
        reasoning = thinking["choices"][0]["message"].get("reasoning_content") or ""
        if not reasoning:
            reporter.record("思考内容回传", "WARN", "本次回答未返回 reasoning_content（网页可能未展示思考过程）")
        else:
            reporter.record("思考内容回传", "PASS", f"{len(reasoning)} 字")

    search = chat(client, reporter, "联网搜索开关", {
        "model": model_id,
        "web_search": True,
        "messages": [{"role": "user", "content": "请联网搜索 DeepSeek 官方网站首页标题是什么"}],
    }, status="WARN")
    if search is not None:
        content = search["choices"][0]["message"].get("content") or ""
        if "参考链接" in content or "http" in content:
            reporter.record("联网引用链接", "PASS", "回答中包含链接")
        else:
            reporter.record("联网引用链接", "WARN", "回答中没有链接，可能未触发联网或未展示来源")


def _check_attachments(client: httpx.Client, reporter: Reporter, model_id: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            note = tmp_dir / "note.txt"
            note.write_text("密语是 蓝鲸-73", encoding="utf-8")
            docx = tmp_dir / "sample.docx"
            make_docx(docx)
            pdf = tmp_dir / "sample.pdf"
            make_pdf(pdf)
            png = tmp_dir / "pixel.png"
            make_solid_png(png, 64, 64, (220, 40, 40))

            for name, path, expect in (
                ("附件 TXT", note, "蓝鲸-73"),
                ("附件 DOCX", docx, "蓝鲸-73"),
                ("附件 PDF", pdf, "MAGIC-91"),
            ):
                upload = client.post(
                    "/v1/files",
                    files={"file": (path.name, path.read_bytes(), "application/octet-stream")},
                )
                if upload.status_code != 200:
                    reporter.record(name, "FAIL", upload.text[:200])
                    continue
                file_id = upload.json()["id"]
                chat(client, reporter, name, {
                    "model": model_id,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "请读取附件内容，只回复其中的密语"},
                            {"type": "file", "file_id": file_id},
                        ],
                    }],
                }, expect=expect)
                client.delete(f"/v1/files/{file_id}")

            inline_image = tmp_dir / "red-inline.png"
            make_solid_png(inline_image, 64, 64, (220, 40, 40))
            image_b64 = base64.b64encode(inline_image.read_bytes()).decode()
            image_payload = {
                "model": model_id,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "这张图片主要是什么颜色？只回答颜色名称"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + image_b64}},
                    ],
                }],
            }
            body = chat(client, reporter, "附件 PNG（图片）", image_payload, status="WARN")
            if body is not None:
                content = body["choices"][0]["message"].get("content") or ""
                if "红" not in content:
                    reporter.record("图片内容识别", "WARN", f"回答未提到红色：{content[:100]}")
                else:
                    reporter.record("图片内容识别", "PASS", content[:40])


def _check_tools(client: httpx.Client, reporter: Reporter, model_id: str) -> None:
    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的实时天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "城市名"}},
                "required": ["city"],
            },
        },
    }]
    time.sleep(TEST_DELAY)
    response = client.post("/v1/chat/completions", json={
            "model": model_id,
            "messages": [{"role": "user", "content": "北京现在天气怎么样？请调用工具查询"}],
            "tools": tools,
    })
    if response.status_code != 200:
        reporter.record("工具调用", "FAIL", response.text[:200])
        return
    choice = response.json()["choices"][0]
    calls = choice["message"].get("tool_calls") or []
    if choice["finish_reason"] != "tool_calls" or not calls:
        reporter.record("工具调用", "FAIL", f"未返回 tool_calls，回答：{str(choice['message'].get('content'))[:120]}")
        return
    reporter.record("工具调用", "PASS", f"{calls[0]['function']['name']}({calls[0]['function']['arguments']})")
    time.sleep(TEST_DELAY)
    follow_up = client.post("/v1/chat/completions", json={
                    "model": model_id,
                    "messages": [
                        {"role": "user", "content": "北京现在天气怎么样？请调用工具查询"},
                        {
                            "role": "assistant",
                            "tool_calls": calls,
                        },
                        {
                            "role": "tool",
                            "tool_call_id": calls[0]["id"],
                            "content": '{"temperature": "25°C", "weather": "晴"}',
                        },
                    ],
                    "tools": tools,
                })
    if follow_up.status_code != 200:
        reporter.record("工具结果续答", "FAIL", follow_up.text[:200])
        return
    content = follow_up.json()["choices"][0]["message"].get("content") or ""
    if content.strip():
        reporter.record("工具结果续答", "PASS", content[:60])
    else:
        reporter.record("工具结果续答", "FAIL", "模型没有给出最终回答")


if __name__ == "__main__":
    sys.exit(main())
