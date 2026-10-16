"""配置与路径管理。"""

from __future__ import annotations

import json
import os
import secrets
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_NAME = "DeepSeekBridge"
APP_VERSION = "0.1.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8317
DEFAULT_MODEL = "deepseek-web"


def resolve_data_dir() -> Path:
    """返回数据目录：环境变量 DSB_DATA_DIR 优先，否则按平台选择默认位置。"""
    env = os.environ.get("DSB_DATA_DIR", "").strip()
    if env:
        return Path(env).expanduser()
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA", "").strip()
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    base = os.environ.get("XDG_DATA_HOME", "").strip()
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / APP_NAME


@dataclass
class AppConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    model_name: str = DEFAULT_MODEL
    api_key: str = ""
    admin_token: str = ""
    thinking: bool = False
    web_search: bool = False
    browser_channel: str = "auto"
    serve_on_lan: bool = True
    cors_enabled: bool = True
    idle_seconds: float = 2.5
    min_request_interval_seconds: float = 2.0
    request_timeout_seconds: float = 600.0
    send_timeout_seconds: float = 90.0
    max_queue: int = 32
    compose_char_limit: int = 200_000
    launch_browser_on_start: bool = True
    log_level: str = "INFO"

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        data: dict = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
        known = {f.name for f in fields(cls)}
        cfg = cls(**{k: v for k, v in data.items() if k in known})
        if not cfg.api_key:
            cfg.api_key = "sk-dsb-" + secrets.token_hex(20)
        if not cfg.admin_token:
            cfg.admin_token = secrets.token_urlsafe(24)
        cfg.save(path)
        return cfg

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)

    def apply_updates(self, updates: dict) -> list[str]:
        """从管理页更新受控字段，返回实际变更的字段名。"""
        changed: list[str] = []
        for key, value in updates.items():
            if key not in {f.name for f in fields(self)}:
                continue
            if key in {"api_key", "admin_token", "host", "model_name"}:
                continue
            current = getattr(self, key)
            try:
                if isinstance(current, bool):
                    if not isinstance(value, bool):
                        value = str(value).strip().lower() in {"1", "true", "yes", "on"}
                    value = bool(value)
                elif isinstance(current, int):
                    value = int(value)
                elif isinstance(current, float):
                    value = float(value)
                elif isinstance(current, str):
                    value = str(value)
            except (TypeError, ValueError):
                continue
            if value != current:
                setattr(self, key, value)
                changed.append(key)
        return changed


@dataclass
class Paths:
    data_dir: Path

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.json"

    @property
    def profile_dir(self) -> Path:
        return self.data_dir / "browser-profile"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def diag_dir(self) -> Path:
        return self.data_dir / "diagnostics"

    @property
    def pid_path(self) -> Path:
        return self.data_dir / "service.pid"

    @property
    def selectors_path(self) -> Path:
        return self.data_dir / "selectors.json"

    def ensure(self) -> None:
        for path in (
            self.data_dir,
            self.profile_dir,
            self.uploads_dir,
            self.logs_dir,
            self.diag_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


def load_config(data_dir: Path | None = None) -> tuple[AppConfig, Paths]:
    paths = Paths(data_dir or resolve_data_dir())
    paths.ensure()
    cfg = AppConfig.load(paths.config_path)
    return cfg, paths
