import logging
from pathlib import Path

import pytest

from app import config as config_module
from app.bridge import deepseek as deepseek_module
from app.bridge.base import BackendError
from app.bridge.deepseek import DeepSeekWebBackend
from app.config import AppConfig, Paths, resolve_data_dir


def test_data_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("DSB_DATA_DIR", str(tmp_path / "custom"))
    assert resolve_data_dir() == tmp_path / "custom"


def test_data_dir_on_windows(monkeypatch, tmp_path):
    monkeypatch.delenv("DSB_DATA_DIR", raising=False)
    monkeypatch.setattr(config_module.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert resolve_data_dir() == tmp_path / "DeepSeekBridge"


def test_data_dir_on_macos(monkeypatch):
    monkeypatch.delenv("DSB_DATA_DIR", raising=False)
    monkeypatch.setattr(config_module.sys, "platform", "darwin")
    expected = Path.home() / "Library" / "Application Support" / "DeepSeekBridge"
    assert resolve_data_dir() == expected


def test_data_dir_on_linux_prefers_xdg(monkeypatch, tmp_path):
    monkeypatch.delenv("DSB_DATA_DIR", raising=False)
    monkeypatch.setattr(config_module.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert resolve_data_dir() == tmp_path / "DeepSeekBridge"


def test_find_browser_prefers_existing_file(monkeypatch, tmp_path):
    fake = tmp_path / "msedge"
    fake.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        deepseek_module,
        "_browser_candidates",
        lambda: [("msedge", [str(fake)], []), ("chrome", ["/nope/chrome"], [])],
    )
    assert deepseek_module.find_browser() == ("msedge", str(fake))


def test_find_browser_uses_path_lookup(monkeypatch):
    monkeypatch.setattr(
        deepseek_module, "_browser_candidates", lambda: [("chrome", [], ["google-chrome"])]
    )
    monkeypatch.setattr(
        deepseek_module.shutil, "which", lambda name: "/usr/bin/google-chrome"
    )
    assert deepseek_module.find_browser() == ("chrome", "/usr/bin/google-chrome")


def test_find_browser_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(
        deepseek_module, "_browser_candidates", lambda: [("msedge", ["/nope"], ["nope"])]
    )
    monkeypatch.setattr(deepseek_module.shutil, "which", lambda name: None)
    assert deepseek_module.find_browser() is None


def test_bundled_chromium_available(monkeypatch, tmp_path):
    (tmp_path / "chromium-1234").mkdir()
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    assert deepseek_module.bundled_chromium_available() is True
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "missing"))
    assert deepseek_module.bundled_chromium_available() is False


def _make_backend(tmp_path: Path, channel: str) -> DeepSeekWebBackend:
    paths = Paths(tmp_path / "data")
    paths.ensure()
    config = AppConfig(browser_channel=channel, launch_browser_on_start=False)
    return DeepSeekWebBackend(config, paths, logging.getLogger("dsb-test"))


def test_pick_channel_explicit_modes(tmp_path):
    backend = _make_backend(tmp_path, "chrome")
    assert backend._pick_channel() == "chrome"
    backend._cfg.browser_channel = "msedge"
    assert backend._pick_channel() == "msedge"
    backend._cfg.browser_channel = "chromium"
    assert backend._pick_channel() is None


def test_pick_channel_falls_back_to_bundled(monkeypatch, tmp_path):
    backend = _make_backend(tmp_path, "auto")
    monkeypatch.setattr(deepseek_module, "find_browser", lambda: None)
    monkeypatch.setattr(deepseek_module, "bundled_chromium_available", lambda: True)
    assert backend._pick_channel() is None


def test_pick_channel_raises_without_any_browser(monkeypatch, tmp_path):
    backend = _make_backend(tmp_path, "auto")
    monkeypatch.setattr(deepseek_module, "find_browser", lambda: None)
    monkeypatch.setattr(deepseek_module, "bundled_chromium_available", lambda: False)
    with pytest.raises(BackendError) as excinfo:
        backend._pick_channel()
    assert excinfo.value.code == "browser_missing"
