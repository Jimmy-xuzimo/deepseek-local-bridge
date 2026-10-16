"""可在运行时开关的 CORS 中间件（纯 ASGI 实现，不干扰流式响应）。"""

from __future__ import annotations

from starlette.datastructures import Headers


class DynamicCORSMiddleware:
    def __init__(self, app, config) -> None:
        self.app = app
        self.config = config

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or not getattr(self.config, "cors_enabled", True):
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        if not origin:
            await self.app(scope, receive, send)
            return

        if scope["method"] == "OPTIONS" and headers.get("access-control-request-method"):
            allow_headers = headers.get("access-control-request-headers") or "*"
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"access-control-allow-origin", b"*"),
                        (b"access-control-allow-methods", b"*"),
                        (b"access-control-allow-headers", allow_headers.encode("latin-1")),
                        (b"access-control-max-age", b"600"),
                        (b"content-length", b"0"),
                        (b"vary", b"origin"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": b""})
            return

        async def send_with_cors_headers(message) -> None:
            if message["type"] == "http.response.start":
                message = dict(message)
                raw = list(message.get("headers") or [])
                raw.append((b"access-control-allow-origin", b"*"))
                raw.append((b"vary", b"origin"))
                message["headers"] = raw
            await send(message)

        await self.app(scope, receive, send_with_cors_headers)
