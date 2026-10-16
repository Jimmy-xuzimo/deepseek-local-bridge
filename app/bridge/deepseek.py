"""Playwright 适配器：驱动专用浏览器中的 DeepSeek 网页完成发送与读取回答。"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from .base import (
    Attachment,
    BackendError,
    BackendEvent,
    BackendInfo,
    BackendState,
    ChatBackend,
    Completed,
    ContentDelta,
    Failed,
    SendOptions,
    ThinkingDelta,
)
from .conversations import ConversationRegistry
from .prompt import (
    conversation_fingerprint,
    continuation_state_fingerprint,
    render_conversation,
    render_last_turn,
)
from .selectors import load_selectors

CHAT_URL = "https://chat.deepseek.com/"
POLL_INTERVAL = 0.25
NO_OUTPUT_LIMIT = 75.0
ERROR_KEYWORDS = ("失败", "繁忙", "上限", "网络异常", "错误", "稍后重试", "频繁", "无法")
RATE_LIMIT_KEYWORDS = (
    "发送过于频繁",
    "请求过于频繁",
    "操作频繁",
    "过于频繁",
    "请稍后重试",
    "频率过快",
    "达到上限",
    "已达上限",
)

# 直接从页面提取“思考块”和“回答块”，并排除思考块内部的节点，避免两者串扰。
LIVE_TEXT_JS = """() => {
    const visible = (el) => {
        const rect = el.getBoundingClientRect();
        return rect.width > 1 && rect.height > 1;
    };
    const inThinking = (el) => !!el.closest("[class*='think'],[class*='reason']");
    const thinkEls = Array.from(document.querySelectorAll("[class*='think'],[class*='reason']"))
        .filter(visible);
    const think = thinkEls.length ? (thinkEls[thinkEls.length - 1].innerText || '') : '';
    let contentEls = Array.from(document.querySelectorAll('div.ds-markdown'))
        .filter(el => visible(el) && !inThinking(el));
    if (!contentEls.length) {
        contentEls = Array.from(document.querySelectorAll("[class*='markdown']"))
            .filter(el => visible(el) && !inThinking(el));
    }
    const content = contentEls.length ? (contentEls[contentEls.length - 1].innerText || '') : '';
    return {think, content, thinkCount: thinkEls.length, contentCount: contentEls.length};
}"""


def _browser_candidates() -> list[tuple[str, list[str], list[str]]]:
    """按平台列出候选浏览器：[(channel, 可执行文件路径, PATH 中的命令名)]。"""
    home = Path.home()
    if sys.platform.startswith("win"):
        return [
            (
                "msedge",
                [
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                ],
                ["msedge"],
            ),
            (
                "chrome",
                [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                ],
                ["chrome"],
            ),
        ]
    if sys.platform == "darwin":
        return [
            (
                "msedge",
                [
                    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                    str(home / "Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                ],
                [],
            ),
            (
                "chrome",
                [
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    str(home / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                ],
                [],
            ),
        ]
    return [
        (
            "msedge",
            [
                "/usr/bin/microsoft-edge",
                "/usr/bin/microsoft-edge-stable",
                "/opt/microsoft/msedge/microsoft-edge",
            ],
            ["microsoft-edge", "microsoft-edge-stable"],
        ),
        (
            "chrome",
            [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/opt/google/chrome/google-chrome",
            ],
            ["google-chrome", "google-chrome-stable"],
        ),
    ]


def find_browser() -> tuple[str, str] | None:
    """返回 (channel, 可执行文件路径)，优先 Edge；支持 Windows / macOS / Linux。"""
    for channel, paths, commands in _browser_candidates():
        for path in paths:
            if Path(path).exists():
                return channel, path
        for command in commands:
            found = shutil.which(command)
            if found:
                return channel, found
    return None


def bundled_chromium_available() -> bool:
    """检查 Playwright 自带的 Chromium 是否已下载（作为没有 Edge/Chrome 时的兜底）。"""
    override = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    if override and override != "0":
        roots = [Path(override)]
    elif sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA", "").strip()
        roots = [(Path(base) if base else Path.home() / "AppData" / "Local") / "ms-playwright"]
    elif sys.platform == "darwin":
        roots = [Path.home() / "Library" / "Caches" / "ms-playwright"]
    else:
        base = os.environ.get("XDG_CACHE_HOME", "").strip()
        roots = [(Path(base) if base else Path.home() / ".cache") / "ms-playwright"]
    for root in roots:
        try:
            if root.exists() and any(item.name.startswith("chromium") for item in root.iterdir()):
                return True
        except OSError:
            continue
    return False


def _common_prefix_len(a: str, b: str) -> int:
    limit = min(len(a), len(b))
    index = 0
    while index < limit and a[index] == b[index]:
        index += 1
    return index


class DeepSeekWebBackend(ChatBackend):
    def __init__(self, config, paths, logger) -> None:
        self._cfg = config
        self._paths = paths
        self._log = logger
        self._selectors = load_selectors(paths.selectors_path)
        self._pw = None
        self._ctx = None
        self._page = None
        self._state = BackendState.STOPPED
        self._detail = ""
        self._last_error: str | None = None
        self._channel: str | None = None
        self._busy = False
        self._lock = asyncio.Lock()
        self._pending_upload_dir: Path | None = None
        self._last_finished_at = 0.0
        self._registry = ConversationRegistry(paths.data_dir / "conversations.json")
        self._active_core_fp: str | None = None
        self._pending_core: list[dict] | None = None
        self._baselines: dict[str, int] = {"markdown": 0, "thinking": 0}
        self._last_refresh = 0.0

    # ------------------------------------------------------------------ 状态
    def info(self) -> BackendInfo:
        return BackendInfo(
            state=self._state,
            detail=self._detail,
            logged_in=self._state in (BackendState.READY, BackendState.BUSY),
            browser_open=self._ctx is not None,
            last_error=self._last_error,
            channel=self._channel,
        )

    def _set_state(self, state: BackendState, detail: str = "") -> None:
        self._state = state
        self._detail = detail
        if state == BackendState.ERROR:
            self._last_error = detail

    def _on_ctx_closed(self, *_args) -> None:
        self._ctx = None
        self._page = None
        if self._state not in (BackendState.STOPPED,):
            self._set_state(BackendState.STOPPED, "浏览器已关闭")

    # ---------------------------------------------------------------- 生命周期
    def _pick_channel(self) -> str | None:
        """返回 Playwright channel；None 表示使用 Playwright 自带的 Chromium。"""
        wanted = (self._cfg.browser_channel or "auto").strip().lower()
        if wanted in ("msedge", "chrome"):
            return wanted
        if wanted in ("chromium", "bundled"):
            return None
        found = find_browser()
        if found is not None:
            return found[0]
        if bundled_chromium_available():
            self._log.warning("未找到 Edge/Chrome，改用 Playwright 自带的 Chromium。")
            return None
        raise BackendError(
            "未找到可用的浏览器：请安装 Microsoft Edge 或 Google Chrome（推荐）；"
            "也可以运行 `python -m playwright install chromium` 安装 Playwright 自带浏览器。",
            code="browser_missing",
        )

    async def start(self) -> None:
        async with self._lock:
            if self._ctx is not None:
                return
            self._set_state(BackendState.STARTING, "正在启动浏览器…")
            try:
                from playwright.async_api import async_playwright

                self._pw = await async_playwright().start()
                channel = self._pick_channel()
                self._paths.profile_dir.mkdir(parents=True, exist_ok=True)
                self._ctx = await self._pw.chromium.launch_persistent_context(
                    user_data_dir=str(self._paths.profile_dir),
                    channel=channel,
                    headless=False,
                    viewport={"width": 1280, "height": 860},
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ],
                    ignore_default_args=["--enable-automation"],
                )
                self._channel = channel or "chromium（内置）"
                self._ctx.on("close", self._on_ctx_closed)
                await self._ctx.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
                self._page = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
                self._page.set_default_timeout(15000)
                await self._goto_with_retry(CHAT_URL)
                await self._refresh_state_inner()
                self._log.info("浏览器已启动，channel=%s, state=%s", channel, self._state.value)
            except BackendError:
                raise
            except Exception as exc:  # noqa: BLE001
                message = f"浏览器启动失败：{exc}"
                self._set_state(BackendState.ERROR, message)
                raise BackendError(message, code="browser_start_failed") from exc

    async def _goto_with_retry(self, url: str, attempts: int = 2) -> None:
        """打开页面，偶发网络抖动时重试一次。"""
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                await self._page.goto(url, wait_until="domcontentloaded", timeout=60000)
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                self._log.warning("打开 %s 失败（第 %d 次）：%s", url, attempt, exc)
                if attempt < attempts:
                    await asyncio.sleep(2.0)
        raise BackendError(f"无法打开 {url}：{last_error}", code="page_load_failed")

    async def stop(self) -> None:
        async with self._lock:
            context = self._ctx
            playwright = self._pw
            self._ctx = None
            self._page = None
            self._pw = None
            self._active_core_fp = None
            self._pending_core = None
            self._set_state(BackendState.STOPPED, "已停止")
            if context is not None:
                try:
                    await context.close()
                except Exception:  # noqa: BLE001
                    pass
            if playwright is not None:
                try:
                    await playwright.stop()
                except Exception:  # noqa: BLE001
                    pass
            self._log.info("浏览器已关闭")

    async def focus_browser(self) -> None:
        if self._page is not None:
            try:
                await self._page.bring_to_front()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ 登录态
    async def _detect_chat_ready(self, timeout: float) -> bool:
        page = self._page
        if page is None:
            return False
        deadline = time.monotonic() + timeout
        while True:
            try:
                url = page.url or ""
            except Exception:  # noqa: BLE001
                url = ""
            if any(token in url for token in ("sign_in", "login")):
                return False
            for selector in self._selectors.get("chat_input", []):
                try:
                    locator = page.locator(selector).first
                    if await locator.count() > 0 and await locator.is_visible():
                        return True
                except Exception:  # noqa: BLE001
                    continue
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(0.4)

    async def _refresh_state_inner(self) -> BackendInfo:
        if self._page is None:
            self._set_state(BackendState.STOPPED, "浏览器未启动")
            return self.info()
        try:
            logged_in = await self._detect_chat_ready(timeout=3.0)
        except Exception as exc:  # noqa: BLE001
            self._set_state(BackendState.ERROR, f"页面检测失败：{exc}")
            return self.info()
        if logged_in:
            self._set_state(BackendState.BUSY if self._busy else BackendState.READY, "已登录，可以发送消息")
        else:
            self._set_state(BackendState.WAITING_LOGIN, "未登录：请点“打开浏览器并登录”，在浏览器窗口中登录 DeepSeek")
        return self.info()

    async def refresh_state(self, force: bool = False) -> BackendInfo:
        if self._page is None:
            return self.info()
        now = time.monotonic()
        if not force and self._busy:
            return self.info()
        if not force and now - self._last_refresh < 2.0:
            return self.info()
        self._last_refresh = now
        return await self._refresh_state_inner()

    async def ensure_ready(self) -> None:
        if self._ctx is None:
            await self.start()
        # 非强制刷新：refresh_state 内部有节流，连续请求不会重复探测页面
        info = await self.refresh_state()
        if not info.logged_in:
            raise BackendError(
                "DeepSeek 网页未登录。请打开设置页，点击“打开浏览器并登录”，完成登录后再试。",
                code="login_required",
            )

    # ------------------------------------------------------------------ 开关
    TOGGLE_LABELS = {
        "toggle_thinking": ("深度思考", "DeepThink"),
        "toggle_search": ("智能搜索", "联网搜索", "Search"),
    }

    async def _read_toggle_states(self) -> dict[str, bool]:
        """读取网页开关状态：DeepSeek 用 div[aria-pressed] + 文本标签表示。"""
        try:
            raw = await self._page.evaluate(
                """() => {
                    const out = {};
                    for (const el of document.querySelectorAll('[aria-pressed]')) {
                        const text = (el.innerText || '').replace(/\\s+/g, '');
                        if (!text || text.length > 12) continue;
                        out[text] = el.getAttribute('aria-pressed') === 'true';
                    }
                    return out;
                }"""
            )
            return raw if isinstance(raw, dict) else {}
        except Exception:  # noqa: BLE001
            return {}

    async def _click_toggle(self, labels: tuple[str, ...]) -> bool:
        for label in labels:
            try:
                locator = self._page.locator(f"[aria-pressed]:has-text('{label}')").first
                if await locator.count() and await locator.is_visible():
                    await locator.click(timeout=3000)
                    return True
            except Exception:  # noqa: BLE001
                continue
        for label in labels:
            try:
                locator = self._page.get_by_text(label).first
                if await locator.count() and await locator.is_visible():
                    await locator.click(timeout=3000)
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    async def _apply_toggles(self, options: SendOptions) -> None:
        for group, wanted in (("toggle_thinking", options.thinking), ("toggle_search", options.web_search)):
            try:
                await self._set_toggle(group, wanted)
            except Exception as exc:  # noqa: BLE001
                self._log.warning("设置开关 %s 失败：%s", group, exc)
        states = await self._read_toggle_states()
        self._log.info(
            "开关状态：思考=%s 搜索=%s（期望 思考=%s 搜索=%s）",
            states.get("深度思考"),
            states.get("智能搜索"),
            options.thinking,
            options.web_search,
        )

    async def _set_toggle(self, group: str, wanted: bool) -> None:
        labels = self.TOGGLE_LABELS.get(group, ())
        for _attempt in range(3):
            states = await self._read_toggle_states()
            current: bool | None = None
            for key, value in states.items():
                if any(label in key for label in labels):
                    current = value
                    break
            if current is None:
                # 兼容旧结构：按默认选择器文本点击一次
                fallback = tuple(self._selectors.get(group, []))
                if fallback and await self._click_by_selectors(fallback):
                    await self._page.wait_for_timeout(500)
                    continue
                raise BackendError(f"未找到开关控件：{group}", code="toggle_not_found")
            if current == wanted:
                return
            if not await self._click_toggle(labels):
                raise BackendError(f"无法点击开关 {group}。", code="toggle_failed")
            await self._page.wait_for_timeout(500)
        states = await self._read_toggle_states()
        matched = [
            value for key, value in states.items() if any(label in key for label in labels)
        ]
        if matched and matched[0] == wanted:
            return
        raise BackendError(
            f"开关 {group} 未能切换到期望状态（期望 {wanted}，实际 {matched}）。",
            code="toggle_failed",
        )

    async def _click_by_selectors(self, selectors: tuple[str, ...]) -> bool:
        for selector in selectors:
            try:
                if selector.startswith("text="):
                    locator = self._page.get_by_text(selector[5:]).first
                else:
                    locator = self._page.locator(selector).first
                if await locator.count() and await locator.is_visible():
                    await locator.click(timeout=3000)
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    # ---------------------------------------------------------------- 会话管理
    async def _group_locator(self, group: str) -> tuple[str | None, int]:
        best: tuple[str | None, int] = (None, -1)
        for selector in self._selectors.get(group, []):
            try:
                count = await self._page.locator(selector).count()
            except Exception:  # noqa: BLE001
                count = 0
            if count > best[1]:
                best = (selector, count)
        return best

    async def _read_live_texts(self) -> dict:
        try:
            data = await self._page.evaluate(LIVE_TEXT_JS)
        except Exception:  # noqa: BLE001
            return {"think": "", "content": "", "thinkCount": 0, "contentCount": 0}
        if not isinstance(data, dict):
            return {"think": "", "content": "", "thinkCount": 0, "contentCount": 0}
        return {
            "think": str(data.get("think") or ""),
            "content": str(data.get("content") or ""),
            "thinkCount": int(data.get("thinkCount") or 0),
            "contentCount": int(data.get("contentCount") or 0),
        }

    async def _chat_is_empty(self) -> bool:
        _selector, count = await self._group_locator("markdown")
        return count == 0

    async def _new_chat(self) -> None:
        page = self._page
        for selector in self._selectors.get("new_chat", []):
            try:
                locator = page.locator(selector).first
                if await locator.count() and await locator.is_visible():
                    await locator.click(timeout=4000)
                    await page.wait_for_timeout(900)
                    if await self._chat_is_empty():
                        self._log.info("已开启新对话（选择器命中：%s）", selector)
                        return
            except Exception:  # noqa: BLE001
                continue
        try:
            await page.goto(CHAT_URL, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(800)
        except Exception:  # noqa: BLE001
            pass
        if not await self._chat_is_empty():
            self._log.warning("无法确认已开启新对话，可能继续在旧会话中追加消息")

    async def _switch_to_conversation(self, url: str) -> bool:
        """切回已有的网页对话（网页侧会显示该对话之前的消息）。"""
        if not url:
            return False
        try:
            current = self._page.url or ""
        except Exception:  # noqa: BLE001
            return False
        if current == url:
            return True
        try:
            await self._goto_with_retry(url, attempts=2)
            await self._page.wait_for_timeout(800)
            landed = self._page.url or ""
            if "/a/chat/s/" not in landed:
                self._log.warning("切换网页对话失败：页面跳转到 %s", landed)
                return False
            await self._find_input(timeout=10)
            self._log.info("已切回网页对话 %s", url.rsplit("/", 1)[-1])
            return True
        except Exception as exc:  # noqa: BLE001
            self._log.warning("切换网页对话失败：%s", exc)
            return False

    def _remember_conversation(self, core: list[dict], options: SendOptions) -> None:
        """记录本次请求对应的网页对话，便于以后切回同一个对话。

        状态指纹只覆盖“我们已经处理过的消息列表”，不含客户端保存的助手回答，
        因此客户端对助手内容的任何改写都不会影响会话匹配。
        """
        try:
            url = self._page.url or ""
        except Exception:  # noqa: BLE001
            return
        if "/a/chat/s/" not in url:
            return
        fingerprint = conversation_fingerprint(core, options, [])
        self._registry.upsert(url, fingerprint)
        self._log.info(
            "已记录网页对话映射（%s，消息数=%d）", url.rsplit("/", 1)[-1], len(core)
        )

    # ---------------------------------------------------------------- 发送消息
    async def _find_input(self, timeout: float = 15.0):
        deadline = time.monotonic() + timeout
        while True:
            for selector in self._selectors.get("chat_input", []):
                try:
                    locator = self._page.locator(selector).first
                    if await locator.count() > 0 and await locator.is_visible():
                        return locator
                except Exception:  # noqa: BLE001
                    continue
            if time.monotonic() >= deadline:
                raise BackendError("未找到网页输入框（可能未登录或网页结构变化）。", code="input_not_found")
            await asyncio.sleep(0.4)

    @staticmethod
    def _attachment_fragment(item: Attachment) -> str:
        name = item.filename or "file"
        return name[:8] if len(name) > 8 else name

    @staticmethod
    def _safe_filename(name: str) -> str:
        cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name or "file").strip(" .")
        return cleaned[:80] or "file"

    def _prepare_upload_paths(self, attachments: list[Attachment]) -> tuple[list[str], Path | None]:
        """网页芯片显示的是上传文件的 basename，因此临时文件名必须与原始文件名一致。"""
        work_dir: Path | None = None
        prepared: list[str] = []
        for item in attachments:
            if item.path.name == item.filename:
                prepared.append(str(item.path))
                continue
            if work_dir is None:
                work_dir = self._paths.uploads_dir / "tmp" / f"upload-{uuid.uuid4().hex[:8]}"
                work_dir.mkdir(parents=True, exist_ok=True)
            target = work_dir / self._safe_filename(item.filename)
            shutil.copyfile(item.path, target)
            prepared.append(str(target))
        return prepared, work_dir

    def _cleanup_upload_dir(self, work_dir: Path | None) -> None:
        if work_dir is None:
            return
        base = self._paths.uploads_dir.resolve()
        target = work_dir.resolve()
        if base in target.parents or target == base:
            shutil.rmtree(target, ignore_errors=True)

    async def _body_text(self) -> str:
        try:
            return await self._page.inner_text("body")
        except Exception:  # noqa: BLE001
            return ""

    async def _thumbnail_count(self) -> int:
        """统计可见的本地预览缩略图（blob:/data: 图片），用于识别图片附件。"""
        try:
            value = await self._page.evaluate(
                """() => Array.from(document.querySelectorAll('img')).filter(img => {
                    const src = img.src || '';
                    if (!(src.startsWith('blob:') || src.startsWith('data:image'))) return false;
                    const rect = img.getBoundingClientRect();
                    return rect.width > 8 && rect.height > 8;
                }).length"""
            )
            return int(value or 0)
        except Exception:  # noqa: BLE001
            return 0

    async def _file_inputs(self) -> list:
        locators = []
        try:
            count = await self._page.locator("input[type='file']").count()
        except Exception:  # noqa: BLE001
            count = 0
        for index in range(count):
            locators.append(self._page.locator("input[type='file']").nth(index))
        return locators

    async def _wait_attachment_chips(
        self,
        targets: list[tuple[Attachment, str]],
        baseline_counts: dict[str, int],
        baseline_thumbnails: int,
        timeout: float,
    ) -> bool:
        """等待附件芯片出现：文件名出现次数增加、缩略图增加或可见文本判断，三者任一成立。"""
        deadline = time.monotonic() + timeout
        while True:
            body = await self._body_text()
            if all(body.count(fragment) > baseline_counts.get(fragment, 0) for _item, fragment in targets):
                return True
            if await self._thumbnail_count() > baseline_thumbnails:
                return True
            try:
                visible = []
                for _item, fragment in targets:
                    visible.append(await self._page.get_by_text(fragment).first.is_visible())
                if all(visible):
                    return True
            except Exception:  # noqa: BLE001
                pass
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(0.5)

    async def _attach_files(self, attachments: list[Attachment]) -> None:
        page = self._page
        targets = [(item, self._attachment_fragment(item)) for item in attachments]
        upload_paths, work_dir = self._prepare_upload_paths(attachments)

        inputs = await self._file_inputs()
        if not inputs:
            for selector in self._selectors.get("upload_button", []):
                try:
                    locator = page.locator(selector).first
                    if await locator.count() and await locator.is_visible():
                        await locator.click(timeout=3000)
                        await page.wait_for_timeout(600)
                        break
                except Exception:  # noqa: BLE001
                    continue
            inputs = await self._file_inputs()
        if not inputs:
            raise BackendError("未找到网页上传入口（可能网页结构变化）。", code="upload_not_found")

        baseline_body = await self._body_text()
        baseline_counts = {fragment: baseline_body.count(fragment) for _item, fragment in targets}
        baseline_thumbnails = await self._thumbnail_count()
        problems: list[str] = []
        for index, input_locator in enumerate(inputs):
            try:
                await input_locator.set_input_files(upload_paths)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"输入框#{index}：{exc}")
                continue
            if await self._wait_attachment_chips(
                targets, baseline_counts, baseline_thumbnails, timeout=25.0
            ):
                self._log.info("附件已上传（file input #%d，共 %d 个文件）", index, len(attachments))
                # 文档类附件需要网页解析完成后模型才读得到，这里多等一会再发送
                has_document = any(item.kind == "file" for item in attachments)
                await page.wait_for_timeout(2500 if has_document else 1000)
                await self._check_upload_errors()
                await page.wait_for_timeout(800 if has_document else 600)
                self._pending_upload_dir = work_dir
                return
            problems.append(f"输入框#{index}：上传后未检测到附件")
        await self._dump_attachment_failure()
        self._cleanup_upload_dir(work_dir)
        names = "、".join(item.filename for item in attachments)
        raise BackendError(
            f"附件上传失败（{names}）：" + "；".join(problems)[:200],
            code="upload_failed",
        )

    async def _check_upload_errors(self) -> None:
        for keyword in ("解析失败", "上传失败", "不支持"):
            try:
                locator = self._page.get_by_text(keyword).first
                if await locator.is_visible():
                    raise BackendError(f"网页提示：{keyword}", code="upload_failed")
            except BackendError:
                raise
            except Exception:  # noqa: BLE001
                continue

    async def _dump_attachment_failure(self) -> None:
        """上传失败时保存现场，便于定位网页改版。"""
        try:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            png = self._paths.diag_dir / f"upload-failed-{stamp}.png"
            await self._page.screenshot(path=str(png), full_page=False)
            self._log.warning("附件上传失败，现场截图：%s", png)
        except Exception:  # noqa: BLE001
            pass

    async def _set_editor_text(self, editor, text: str) -> None:
        page = self._page
        try:
            tag = await editor.evaluate("el => (el.tagName || '').toLowerCase()")
        except Exception:  # noqa: BLE001
            tag = "textarea"
        if tag == "textarea":
            try:
                await editor.fill(text)
                value = await editor.input_value()
                if value.strip():
                    return
            except Exception:  # noqa: BLE001
                pass
        await editor.click()
        try:
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Delete")
        except Exception:  # noqa: BLE001
            pass
        await page.keyboard.insert_text(text)
        await page.wait_for_timeout(300)
        verified = True
        try:
            verified = bool((await editor.input_value()).strip())
        except Exception:  # noqa: BLE001
            try:
                verified = bool((await editor.inner_text()).strip())
            except Exception:  # noqa: BLE001
                verified = True
        if not verified:
            raise BackendError("无法把消息写入网页输入框（可能网页结构变化）。", code="input_failed")

    async def _editor_cleared(self, editor) -> bool:
        try:
            return not (await editor.input_value()).strip()
        except Exception:  # noqa: BLE001
            try:
                return not (await editor.inner_text()).strip()
            except Exception:  # noqa: BLE001
                return True

    async def _wait_cleared(self, editor, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if await self._editor_cleared(editor):
                return True
            await asyncio.sleep(0.25)
        return False

    async def _submit(self, editor) -> None:
        """发送消息：Enter → 发送按钮 → 稍等再试一次；失败时区分限流与结构变化。"""
        page = self._page

        async def press_enter() -> bool:
            try:
                await page.keyboard.press("Enter")
            except Exception:  # noqa: BLE001
                return False
            return await self._wait_cleared(editor, timeout=4)

        async def click_send_button() -> bool:
            for selector in self._selectors.get("send_button", []):
                try:
                    locator = page.locator(selector).last
                    if await locator.count() == 0 or not await locator.is_visible():
                        continue
                    if await locator.is_disabled():
                        continue
                    await locator.click(timeout=3000)
                    if await self._wait_cleared(editor, timeout=4):
                        return True
                except Exception:  # noqa: BLE001
                    continue
            return False

        if await press_enter():
            return
        if await click_send_button():
            return
        # 图片等附件可能仍在处理中，等一下再重试一次
        await page.wait_for_timeout(2000)
        if await press_enter() or await click_send_button():
            return
        hint = await self._rate_limit_hint()
        if hint:
            raise BackendError(
                f"DeepSeek 网页提示「{hint}」：当前请求过于频繁，请稍后再试。"
                "这是网页版的频率限制，不是本地服务的错误。",
                code="rate_limited",
            )
        raise BackendError(
            "消息发送失败：未检测到网页已发送（可能登录失效或网页结构变化）。",
            code="send_failed",
        )

    async def _send_message(self, text: str, attachments: list[Attachment]) -> None:
        editor = await self._find_input()
        await editor.click()
        if attachments:
            await self._attach_files(attachments)
        await self._set_editor_text(editor, text)
        live = await self._read_live_texts()
        self._baselines = {"markdown": live["contentCount"], "thinking": live["thinkCount"]}
        await self._submit(editor)

    # ------------------------------------------------------------ 读取回答
    async def _stop_button_visible(self) -> bool:
        for selector in self._selectors.get("stop_button", []):
            try:
                locator = self._page.locator(selector).first
                if await locator.count() and await locator.is_visible():
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False

    async def _generating_indicator(self) -> bool:
        if await self._stop_button_visible():
            return True
        try:
            return bool(
                await self._page.evaluate(
                    """() => {
                        const sel = "[class*='loading'],[class*='Loading'],[class*='spinner'],[class*='generating'],[class*='typing']";
                        for (const el of document.querySelectorAll(sel)) {
                            if (el.offsetParent !== null) return true;
                        }
                        const text = (document.body && document.body.innerText) || "";
                        return /正在(搜索|思考|生成|分析|回答|阅读)/.test(text);
                    }"""
                )
            )
        except Exception:  # noqa: BLE001
            return False

    async def _read_error_banner(self) -> str | None:
        for selector in self._selectors.get("error_toast", []):
            try:
                locator = self._page.locator(selector).first
                if await locator.count() == 0 or not await locator.is_visible():
                    continue
                text = (await locator.inner_text()).strip()
            except Exception:  # noqa: BLE001
                continue
            if text and len(text) < 200 and any(keyword in text for keyword in ERROR_KEYWORDS):
                return text
        return None

    async def _rate_limit_hint(self) -> str | None:
        """检查页面尾部是否出现“发送过于频繁”等频率限制提示。"""
        body = await self._body_text()
        tail = body[-600:] if len(body) > 600 else body
        for keyword in RATE_LIMIT_KEYWORDS:
            if keyword in tail:
                return keyword
        return None

    def _is_echo(self, text: str, prompt: str) -> bool:
        normalized_text = " ".join(text.split())
        normalized_prompt = " ".join(prompt.split())
        if not normalized_text or not normalized_prompt:
            return False
        if len(normalized_text) <= len(normalized_prompt) + 20:
            head = normalized_text[:60]
            if head and normalized_prompt.startswith(head):
                return True
        return normalized_text[:200] == normalized_prompt[:200]

    async def _read_last_text(self, group: str, baseline: int, prompt: str) -> tuple[int, str]:
        selector, count = await self._group_locator(group)
        if selector is None or count <= baseline:
            return count, ""
        for index in range(count - 1, baseline - 1, -1):
            try:
                text = await self._page.locator(selector).nth(index).inner_text()
            except Exception:  # noqa: BLE001
                continue
            if prompt and self._is_echo(text, prompt):
                continue
            if text and text.strip():
                return count, text
        return count, ""

    async def _collect_citation_links(self, text: str) -> list[str]:
        """收集回答里的引用链接（含消息容器内的搜索来源面板）。"""
        try:
            raw = await self._page.evaluate(
                """() => {
                    const visible = (el) => {
                        const rect = el.getBoundingClientRect();
                        return rect.width > 1 && rect.height > 1;
                    };
                    const inThinking = (el) => !!el.closest("[class*='think'],[class*='reason']");
                    let nodes = Array.from(document.querySelectorAll('div.ds-markdown'))
                        .filter(el => visible(el) && !inThinking(el));
                    if (!nodes.length) {
                        nodes = Array.from(document.querySelectorAll("[class*='markdown']"))
                            .filter(el => visible(el) && !inThinking(el));
                    }
                    if (!nodes.length) return [];
                    let container = nodes[nodes.length - 1];
                    for (let i = 0; i < 3 && container.parentElement; i++) {
                        container = container.parentElement;
                    }
                    return Array.from(container.querySelectorAll("a[href^='http']"))
                        .map(a => a.href);
                }"""
            )
        except Exception:  # noqa: BLE001
            return []
        hrefs: list[str] = []
        for link in raw or []:
            if link and link not in hrefs and link not in text:
                hrefs.append(link)
        return hrefs[:8]

    async def _stop_generation(self) -> None:
        for selector in self._selectors.get("stop_button", []):
            try:
                locator = self._page.locator(selector).first
                if await locator.count() and await locator.is_visible():
                    await locator.click(timeout=2000)
                    await self._page.wait_for_timeout(300)
                    self._log.info("已点击停止生成")
                    return
            except Exception:  # noqa: BLE001
                continue
        self._log.warning("未能点击停止按钮（选择器未命中）")

    async def _read_response(self, prompt: str, options: SendOptions, cancel_event) -> AsyncIterator[BackendEvent]:
        started_at = time.monotonic()
        deadline = started_at + max(30.0, options.timeout_seconds)
        baseline_markdown = self._baselines.get("markdown", 0)
        baseline_thinking = self._baselines.get("thinking", 0)
        started = False
        stop_seen = False
        emitted_content = ""
        emitted_thinking = ""
        prev_content = ""
        prev_thinking = ""
        last_change = time.monotonic()
        divergence_since: float | None = None
        while True:
            if cancel_event.is_set():
                await self._stop_generation()
                yield Failed("请求已取消", code="cancelled")
                return
            now = time.monotonic()
            if now > deadline:
                yield Failed("等待网页回答超时。", code="timeout")
                return
            await asyncio.sleep(POLL_INTERVAL)
            now = time.monotonic()
            generating = await self._generating_indicator()
            if generating:
                stop_seen = True
            live = await self._read_live_texts()
            markdown_count = live["contentCount"]
            thinking_count = live["thinkCount"]
            content_text = live["content"] if markdown_count > baseline_markdown else ""
            thinking_text = live["think"] if thinking_count > baseline_thinking else ""
            if content_text and prompt and self._is_echo(content_text, prompt):
                content_text = ""
            if not started:
                if markdown_count > baseline_markdown or generating:
                    started = True
                    last_change = now
                else:
                    hint = await self._rate_limit_hint()
                    if hint:
                        yield Failed(
                            f"DeepSeek 网页提示「{hint}」：当前请求过于频繁，请稍后再试。"
                            "这是网页版的频率限制，不是本地服务的错误。",
                            code="rate_limited",
                        )
                        return
                    banner = await self._read_error_banner()
                    if banner:
                        yield Failed(banner, code="web_error")
                        return
                    if now - started_at > NO_OUTPUT_LIMIT:
                        yield Failed("发送后长时间没有检测到网页开始回答。", code="no_response")
                        return
                    continue
            if thinking_text != prev_thinking:
                prev_thinking = thinking_text
                last_change = now
                if thinking_text.startswith(emitted_thinking):
                    delta = thinking_text[len(emitted_thinking):]
                    emitted_thinking = thinking_text
                    if delta:
                        yield ThinkingDelta(delta)
            if content_text != prev_content:
                prev_content = content_text
                last_change = now
                if content_text.startswith(emitted_content):
                    delta = content_text[len(emitted_content):]
                    emitted_content = content_text
                    divergence_since = None
                    if delta:
                        yield ContentDelta(delta)
                else:
                    common = _common_prefix_len(emitted_content, content_text)
                    if common >= len(emitted_content) - 2:
                        emitted_content = content_text
                        delta = content_text[common:]
                        divergence_since = None
                        if delta:
                            yield ContentDelta(delta)
                    else:
                        divergence_since = divergence_since or now
                        if now - divergence_since > 2.0:
                            delta = content_text[common:]
                            emitted_content = emitted_content + delta
                            divergence_since = None
                            if delta:
                                yield ContentDelta(delta)
            banner = await self._read_error_banner()
            if banner and not emitted_content:
                yield Failed(banner, code="web_error")
                return
            if not (prev_content or prev_thinking):
                if now - last_change > 30:
                    yield Failed("网页没有返回有效内容。", code="empty_response")
                    return
                continue
            idle = now - last_change
            stable_needed = 0.9 if stop_seen else max(options.idle_seconds, 6.0)
            if not emitted_content.strip() and prev_thinking.strip():
                # 只有思考、还没出现回答正文时，多给网页一点渲染时间
                stable_needed = max(stable_needed, 6.0)
            if not generating and idle >= stable_needed:
                final_text = prev_content
                if final_text and final_text != emitted_content:
                    common = _common_prefix_len(emitted_content, final_text)
                    remainder = final_text[common:]
                    if remainder:
                        yield ContentDelta(remainder)
                        emitted_content = final_text
                if not emitted_content.strip() and not emitted_thinking.strip() and not prev_thinking.strip():
                    yield Failed("网页没有返回有效内容。", code="empty_response")
                    return
                citations = await self._collect_citation_links(emitted_content)
                if citations:
                    lines = "\n".join(f"- {link}" for link in citations)
                    extra = f"\n\n参考链接：\n{lines}"
                    emitted_content += extra
                    yield ContentDelta(extra)
                self._log.info(
                    "回答完成：content_chars=%d thinking_chars=%d seconds=%.1f",
                    len(emitted_content),
                    len(emitted_thinking),
                    time.monotonic() - started_at,
                )
                yield Completed(finish_reason="stop")
                return

    # ------------------------------------------------------------------ 发送入口
    async def send(
        self,
        messages: list[dict],
        options: SendOptions,
        attachments: list[Attachment],
        cancel_event,
    ) -> AsyncIterator[BackendEvent]:
        if self._busy:
            yield Failed("后端正在处理上一条消息，请稍后重试。", code="busy")
            return
        self._busy = True
        try:
            try:
                await self.ensure_ready()
            except BackendError as exc:
                yield Failed(str(exc), code=exc.code)
                return
            interval = float(getattr(self._cfg, "min_request_interval_seconds", 0.0) or 0.0)
            if interval > 0 and self._last_finished_at:
                wait_for = interval - (time.monotonic() - self._last_finished_at)
                if wait_for > 0:
                    self._log.info("请求间隔控制：等待 %.1f 秒", wait_for)
                    await asyncio.sleep(wait_for)
            try:
                core = [m for m in messages if str(m.get("role")) not in ("system", "developer")]
                core_fp = conversation_fingerprint(core, options, attachments)
                retry = self._active_core_fp is not None and core_fp == self._active_core_fp
                state_fp = None if retry else continuation_state_fingerprint(messages, options)
                entry = self._registry.find(state_fp) if state_fp else None
                switched = False
                if entry is not None:
                    switched = await self._switch_to_conversation(entry.url)
                if entry is not None and switched:
                    prompt = render_last_turn(messages)
                    self._log.info(
                        "复用网页对话 %s（续聊，只发送最后一条消息）",
                        entry.url.rsplit("/", 1)[-1],
                    )
                else:
                    await self._new_chat()
                    prompt = render_conversation(messages)
                    self._log.info(
                        "新建网页对话并发送完整上下文（消息数=%d，字符数=%d）",
                        len(messages),
                        len(prompt),
                    )
                    if len(prompt) > self._cfg.compose_char_limit:
                        yield Failed(
                            "对话历史过长，超过网页可承载范围；请开启新对话或减少上下文。",
                            code="context_too_long",
                        )
                        return
                if not prompt.strip():
                    yield Failed("消息内容为空。", code="empty_message")
                    return
                # 注意：网页在“新对话”后会重置开关，因此开关必须在新建对话之后设置
                await self._apply_toggles(options)
                await self._send_message(prompt, attachments)
                self._active_core_fp = core_fp
                self._pending_core = core
            except BackendError as exc:
                yield Failed(str(exc), code=exc.code)
                return
            except Exception as exc:  # noqa: BLE001
                self._log.exception("发送消息时发生内部错误")
                yield Failed(f"发送消息时发生内部错误：{exc}", code="internal_error")
                return
            if cancel_event.is_set():
                await self._stop_generation()
                yield Failed("请求已取消", code="cancelled")
                return
            async for event in self._read_response(prompt, options, cancel_event):
                yield event
            if self._pending_core is not None:
                self._remember_conversation(self._pending_core, options)
        finally:
            self._busy = False
            self._last_finished_at = time.monotonic()
            self._cleanup_upload_dir(self._pending_upload_dir)
            self._pending_upload_dir = None
            if self._state == BackendState.BUSY:
                self._set_state(BackendState.READY, "已登录，可以发送消息")

    async def cancel_current(self) -> None:
        await self._stop_generation()

    # ------------------------------------------------------------------ 诊断
    async def diagnose(self) -> dict:
        if self._page is None:
            raise BackendError("浏览器未启动，无法生成诊断信息。", code="browser_stopped")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        payload: dict = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "url": self._page.url,
            "title": await self._page.title(),
            "state": self._state.value,
            "selectors": {},
        }
        for group, candidates in self._selectors.items():
            details = []
            for selector in candidates:
                try:
                    count = await self._page.locator(selector).count()
                except Exception:  # noqa: BLE001
                    count = -1
                details.append({"selector": selector, "count": count})
            payload["selectors"][group] = details
        try:
            payload["elements"] = await self._page.evaluate(
                """() => ({
                    textareas: Array.from(document.querySelectorAll('textarea')).map(e => ({
                        id: e.id, ph: e.placeholder || '', visible: e.offsetParent !== null
                    })),
                    fileInputs: document.querySelectorAll("input[type='file']").length,
                    buttons: Array.from(document.querySelectorAll("button,[role='button']"))
                        .filter(e => e.offsetParent !== null)
                        .map(e => ({
                            t: (e.innerText || '').slice(0, 30),
                            a: e.getAttribute('aria-label') || '',
                            c: String(e.className || '').slice(0, 60)
                        })).slice(0, 60)
                })"""
            )
        except Exception:  # noqa: BLE001
            payload["elements"] = {}
        json_path = self._paths.diag_dir / f"diagnose-{stamp}.json"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        png_path = self._paths.diag_dir / f"diagnose-{stamp}.png"
        try:
            await self._page.screenshot(path=str(png_path), full_page=False)
        except Exception:  # noqa: BLE001
            png_path = None  # type: ignore[assignment]
        return {"json": str(json_path), "png": str(png_path) if png_path else None}

    async def test_message(self, text: str) -> dict:
        started = time.monotonic()
        cancel_event = asyncio.Event()
        options = SendOptions(
            thinking=self._cfg.thinking,
            web_search=self._cfg.web_search,
            idle_seconds=self._cfg.idle_seconds,
            timeout_seconds=min(180.0, self._cfg.request_timeout_seconds),
        )
        content: list[str] = []
        thinking: list[str] = []
        self._active_core_fp = None
        async for event in self.send([{"role": "user", "content": text}], options, [], cancel_event):
            if isinstance(event, ContentDelta):
                content.append(event.text)
            elif isinstance(event, ThinkingDelta):
                thinking.append(event.text)
            elif isinstance(event, Failed):
                return {
                    "ok": False,
                    "error": event.message,
                    "code": event.code,
                    "seconds": round(time.monotonic() - started, 1),
                }
        return {
            "ok": True,
            "content": "".join(content),
            "thinking": "".join(thinking),
            "seconds": round(time.monotonic() - started, 1),
        }
