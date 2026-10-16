"""设置页（管理界面）与本地管理接口。"""

from __future__ import annotations

import asyncio
import json
import secrets
import shutil
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import APP_VERSION
from .netinfo import list_local_ipv4

STATIC_DIR = Path(__file__).resolve().parent / "static"
COOKIE_NAME = "dsb_admin"
SETTING_KEYS = {
    "thinking",
    "web_search",
    "serve_on_lan",
    "cors_enabled",
    "port",
    "idle_seconds",
    "min_request_interval_seconds",
    "request_timeout_seconds",
    "browser_channel",
    "launch_browser_on_start",
}


def _host_allowed(request: Request) -> bool:
    host = (request.headers.get("host") or "").split(":")[0].strip("[]").lower()
    return host in {"", "127.0.0.1", "localhost", "::1"}


def _is_authed(request: Request) -> bool:
    config = request.app.state.config
    token = request.cookies.get(COOKIE_NAME) or request.headers.get("x-admin-token", "")
    return bool(token) and secrets.compare_digest(token, config.admin_token)


def _read_log_tail(path: Path, lines: int = 40) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(content.splitlines()[-lines:])


def build_admin_router() -> APIRouter:
    router = APIRouter()

    def _entry(request: Request, token: str | None):
        if not _host_allowed(request):
            return JSONResponse(status_code=403, content={"detail": "仅允许本机访问。"})
        if token and secrets.compare_digest(token, request.app.state.config.admin_token):
            response = RedirectResponse(url="/admin/", status_code=303)
            response.set_cookie(
                COOKIE_NAME, token, httponly=True, samesite="lax", max_age=30 * 24 * 3600
            )
            return response
        if not _is_authed(request):
            return HTMLResponse(
                "<html><meta charset='utf-8'><body style='font-family:sans-serif;padding:40px'>"
                "<h2>需要管理员令牌</h2>"
                "<p>请通过带 <code>?token=</code> 的地址打开本页（启动脚本会自动打开）。</p>"
                "<p>令牌保存在数据目录的 config.json 中（字段 admin_token）。</p>"
                "</body></html>",
                status_code=401,
            )
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @router.get("/admin", include_in_schema=False)
    async def admin_redirect(request: Request, token: str | None = None):
        return _entry(request, token)

    @router.get("/admin/", include_in_schema=False)
    async def admin_page(request: Request, token: str | None = None):
        return _entry(request, token)

    @router.get("/admin/api/state")
    async def admin_state(request: Request):
        if not _host_allowed(request) or not _is_authed(request):
            return JSONResponse(status_code=401, content={"detail": "未授权。"})
        state = request.app.state
        try:
            info = await asyncio.wait_for(state.backend.refresh_state(), timeout=6.0)
        except Exception:  # noqa: BLE001 - 页面无响应时回退到缓存状态，避免设置页卡死
            info = state.backend.info()
        config = state.config
        return {
            "version": APP_VERSION,
            "backend": info.__dict__,
            "queue": state.service.snapshot(),
            "config": {
                "thinking": config.thinking,
                "web_search": config.web_search,
                "serve_on_lan": config.serve_on_lan,
                "cors_enabled": config.cors_enabled,
                "idle_seconds": config.idle_seconds,
                "min_request_interval_seconds": config.min_request_interval_seconds,
                "request_timeout_seconds": config.request_timeout_seconds,
                "browser_channel": config.browser_channel,
                "launch_browser_on_start": config.launch_browser_on_start,
                "model_name": config.model_name,
                "host": config.host,
                "port": config.port,
                "api_key": config.api_key,
                "max_queue": config.max_queue,
            },
            "server": {
                "bind_host": "0.0.0.0" if config.serve_on_lan else config.host,
                "port": config.port,
                "serve_on_lan": config.serve_on_lan,
                "cors_enabled": config.cors_enabled,
                "local_url": f"http://127.0.0.1:{config.port}/v1",
                "lan_urls": [f"http://{ip}:{config.port}/v1" for ip in list_local_ipv4()],
            },
            "paths": {
                "data_dir": str(state.paths.data_dir),
                "logs": str(state.paths.logs_dir / "app.log"),
                "diagnostics": str(state.paths.diag_dir),
            },
            "logs": _read_log_tail(state.paths.logs_dir / "app.log", 30),
        }

    @router.post("/admin/api/action")
    async def admin_action(request: Request):
        if not _host_allowed(request) or not _is_authed(request):
            return JSONResponse(status_code=401, content={"detail": "未授权。"})
        state = request.app.state
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError):
            body = {}
        action = str(body.get("action", ""))
        backend = state.backend
        config = state.config

        if action == "browser_start":
            try:
                await backend.start()
            except Exception as exc:  # noqa: BLE001
                return JSONResponse(
                    status_code=200,
                    content={"ok": False, "message": f"启动浏览器失败：{exc}"},
                )
            info = await backend.refresh_state(force=True)
            await backend.focus_browser()
            return {"ok": True, "message": f"浏览器已启动（{info.state.value}）。请在窗口中完成登录。", "backend": info.__dict__}

        if action == "browser_stop":
            await backend.stop()
            return {"ok": True, "message": "浏览器已关闭。"}

        if action == "focus_browser":
            await backend.focus_browser()
            return {"ok": True, "message": "已尝试将浏览器窗口置前。"}

        if action == "recheck_login":
            info = await backend.refresh_state(force=True)
            return {
                "ok": info.logged_in,
                "message": info.detail or info.state.value,
                "backend": info.__dict__,
            }

        if action == "diagnose":
            try:
                result = await backend.diagnose()
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "message": f"生成诊断失败：{exc}"}
            return {"ok": True, "message": f"诊断已保存：{result.get('json')}", "data": result}

        if action == "clear_login":
            await backend.stop()
            profile = state.paths.profile_dir
            data_dir = state.paths.data_dir.resolve()
            target = profile.resolve()
            if data_dir not in target.parents:
                return {"ok": False, "message": "安全检查失败：拒绝删除数据目录之外的路径。"}
            shutil.rmtree(target, ignore_errors=True)
            return {"ok": True, "message": "已清除浏览器登录数据，下次启动需重新登录。"}

        if action == "save_settings":
            raw_updates = {
                key: value
                for key, value in (body.get("settings") or {}).items()
                if key in SETTING_KEYS
            }
            if "port" in raw_updates:
                try:
                    port = int(raw_updates["port"])
                except (TypeError, ValueError):
                    return {"ok": False, "message": "端口必须是数字。"}
                if not 1024 <= port <= 65535:
                    return {"ok": False, "message": "端口需在 1024-65535 之间。"}
                raw_updates["port"] = port
            changed = config.apply_updates(raw_updates)
            config.save(state.paths.config_path)
            notes = ["设置已保存。"]
            if {"port", "serve_on_lan"} & set(changed):
                notes.append("端口与局域网访问需要重启服务后生效（运行 scripts\\restart.ps1 或重新 start.bat）。")
            if "browser_channel" in changed:
                notes.append("浏览器类型将在下次启动浏览器时生效。")
            if "cors_enabled" in changed:
                notes.append("CORS 立即生效。")
            return {"ok": True, "message": " ".join(notes), "changed": changed}

        if action == "regenerate_api_key":
            config.api_key = "sk-dsb-" + secrets.token_hex(20)
            config.save(state.paths.config_path)
            return {"ok": True, "message": "已重新生成 API Key，请更新客户端配置。", "api_key": config.api_key}

        if action == "test_message":
            text = str(body.get("text") or "你好，请只回复：桥接正常").strip()
            try:
                result = await backend.test_message(text)
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "message": f"测试失败：{exc}"}
            return {"ok": bool(result.get("ok")), "message": "测试消息已发送。", "data": result}

        return {"ok": False, "message": f"未知操作：{action}"}

    return router


def mount_admin_static(app) -> None:
    if STATIC_DIR.exists():
        app.mount("/admin/static", StaticFiles(directory=str(STATIC_DIR)), name="admin-static")
