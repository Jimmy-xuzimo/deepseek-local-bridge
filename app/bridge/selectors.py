"""页面选择器注册表，支持通过数据目录下的 selectors.json 覆盖。"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_SELECTORS: dict[str, list[str]] = {
    "chat_input": [
        "textarea#chat-input",
        "textarea",
        "div[contenteditable='true'][role='textbox']",
        "div[contenteditable='true']",
    ],
    "send_button": [
        "button[type='submit']",
        "[aria-label*='发送']",
        "[class*='send-button']",
        "[class*='sendButton']",
    ],
    "stop_button": [
        "[aria-label*='停止']",
        "[aria-label*='stop']",
        "[class*='stop-button']",
        "[class*='stopButton']",
        "[class*='stop-btn']",
    ],
    "new_chat": [
        "button:has-text('新对话')",
        "[role='button']:has-text('新对话')",
        "a:has-text('新对话')",
    ],
    "toggle_thinking": [
        "text=深度思考",
        "text=深度思考(R1)",
        "text=DeepThink",
    ],
    "toggle_search": [
        "text=联网搜索",
        "text=智能搜索",
        "text=Search",
    ],
    "markdown": [
        "div.ds-markdown",
        "div[class*='ds-markdown']",
        "[class*='markdown']",
    ],
    "thinking": [
        "[class*='thinking']",
        "[class*='reasoning']",
        "[class*='think']",
    ],
    "file_input": ["input[type='file']"],
    "upload_button": [
        "[aria-label*='上传']",
        "[aria-label*='附件']",
        "[class*='upload']",
        "[class*='attach']",
        "[class*='paperclip']",
    ],
    "error_toast": [
        "[class*='toast']",
        "[role='alert']",
        "[class*='notification']",
        "[class*='error']",
    ],
    "answer_fallback": ["[class*='assistant']"],
}


def load_selectors(override_path: Path | None = None) -> dict[str, list[str]]:
    selectors = {key: list(value) for key, value in DEFAULT_SELECTORS.items()}
    if override_path and override_path.exists():
        try:
            data = json.loads(override_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return selectors
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    selectors[key] = [value]
                elif isinstance(value, list):
                    selectors[key] = [str(item) for item in value]
    return selectors
