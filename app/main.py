"""应用装配：FastAPI 实例、路由与生命周期。"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .admin_ui import build_admin_router, mount_admin_static
from .bridge.base import ChatBackend
from .bridge.deepseek import DeepSeekWebBackend
from .config import APP_VERSION, AppConfig, Paths, resolve_data_dir
from .cors import DynamicCORSMiddleware
from .files_store import FileStore
from .logging_setup import setup_logging
from .openai_api import build_openai_router
from .service import BridgeService


def create_app(
    config: AppConfig | None = None,
    paths: Paths | None = None,
    backend: ChatBackend | None = None,
) -> FastAPI:
    paths = paths or Paths(resolve_data_dir())
    paths.ensure()
    cfg = config or AppConfig.load(paths.config_path)
    logger = setup_logging(paths.logs_dir, cfg.log_level)
    backend = backend or DeepSeekWebBackend(cfg, paths, logger)
    service = BridgeService(backend, cfg, logger)
    files = FileStore(paths.uploads_dir)

    async def _auto_start() -> None:
        try:
            await backend.start()
        except Exception as exc:  # noqa: BLE001
            logger.warning("自动启动浏览器失败：%s", exc)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        files.cleanup_tmp()
        task = None
        if cfg.launch_browser_on_start:
            task = asyncio.create_task(_auto_start())
        try:
            yield
        finally:
            if task is not None and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=3)
                except (TimeoutError, asyncio.CancelledError):
                    pass
            try:
                await backend.stop()
            except Exception:  # noqa: BLE001
                pass

    app = FastAPI(
        title="DeepSeek Local Bridge",
        version=APP_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.config = cfg
    app.state.paths = paths
    app.state.backend = backend
    app.state.service = service
    app.state.files = files
    app.state.logger = logger

    # CORS 开关在设置页可即时切换，因此使用自定义中间件（读取运行时配置）。
    app.add_middleware(DynamicCORSMiddleware, config=cfg)

    async def _http_error_handler(request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        message = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False)
        error_type = "invalid_request_error" if exc.status_code < 500 else "server_error"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {"message": message, "type": error_type, "code": exc.status_code},
                "detail": message,
            },
        )

    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.include_router(build_openai_router(), prefix="/v1")
    app.include_router(build_admin_router())
    mount_admin_static(app)

    @app.get("/healthz")
    async def healthz() -> dict:
        info = app.state.backend.info()
        return {
            "status": "ok",
            "version": APP_VERSION,
            "backend": info.state.value,
            "logged_in": info.logged_in,
        }

    return app
