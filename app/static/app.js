/* DeepSeek Local Bridge 设置页交互 */

const $ = (id) => document.getElementById(id);

let keyShown = false;
let lastState = null;

/* ------------------------------------------------------------------ 基础工具 */

function toast(message) {
  const el = $("toast");
  if (!el || !message) return;
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove("show"), 3400);
}

function attachRipple(root) {
  root.addEventListener("pointerdown", (event) => {
    const btn = event.target.closest(".btn");
    if (!btn || btn.disabled) return;
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const span = document.createElement("span");
    span.className = "ripple";
    span.style.width = span.style.height = `${size}px`;
    span.style.left = `${event.clientX - rect.left - size / 2}px`;
    span.style.top = `${event.clientY - rect.top - size / 2}px`;
    btn.appendChild(span);
    setTimeout(() => span.remove(), 640);
  });
}

async function withBusy(btn, fn) {
  if (!btn) return fn();
  btn.classList.add("busy");
  btn.disabled = true;
  try {
    return await fn();
  } finally {
    btn.classList.remove("busy");
    btn.disabled = false;
  }
}

async function api(action, payload = {}) {
  const response = await fetch("/admin/api/action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, ...payload }),
  });
  const data = await response.json().catch(() => ({}));
  if (data && data.message) toast(data.message);
  return data || {};
}

async function copyText(text, btn) {
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch (err) {
    toast("复制失败，请手动选择复制");
    return;
  }
  if (btn) {
    const original = btn.textContent;
    btn.classList.add("copied");
    btn.textContent = "已复制";
    setTimeout(() => {
      btn.classList.remove("copied");
      btn.textContent = original;
    }, 1200);
  }
}

/* ------------------------------------------------------------------ 状态渲染 */

const STATUS_TEXT = {
  stopped: "浏览器未启动",
  starting: "正在启动浏览器…",
  waiting_login: "等待登录",
  ready: "已就绪",
  busy: "正在回答",
  error: "出错了",
};

function renderStatus(backend) {
  const pill = $("status-pill");
  if (!pill) return;
  const label = pill.querySelector(".label");
  const text = STATUS_TEXT[backend.state] || backend.state || "-";
  if (label) label.textContent = text;
  pill.classList.remove("ready", "login", "error");
  if (backend.state === "ready" || backend.state === "busy") pill.classList.add("ready");
  else if (backend.state === "waiting_login" || backend.state === "starting") pill.classList.add("login");
  else if (backend.state === "error") pill.classList.add("error");
}

function renderUrls(config, server) {
  const box = $("api-urls");
  if (!box) return;
  const rows = [];
  const row = (label, url) =>
    `<div class="kv"><span class="kv-label">${label}</span><code>${url}</code>` +
    `<button class="btn btn-copy" data-copy-text="${url}">复制</button></div>`;
  if (server.local_url) rows.push(row("本机", server.local_url));
  for (const url of server.lan_urls || []) rows.push(row("局域网", url));
  if (!config.serve_on_lan) {
    rows.push('<p class="kv-hint">局域网服务未开启：打开“在网络中提供服务”并重启服务后，手机等设备即可通过 192.168 地址访问。</p>');
  } else if (!(server.lan_urls || []).length) {
    rows.push('<p class="kv-hint">已开启局域网服务，但未检测到局域网 IP，请检查网络连接。</p>');
  } else {
    rows.push('<p class="kv-hint">局域网内其它设备用上面的 192.168 地址 + 同一个 API Key 即可访问；首次可能需要在 Windows 防火墙弹窗中允许。</p>');
  }
  const html = rows.join("");
  if (box.dataset.html !== html) {
    box.dataset.html = html;
    box.innerHTML = html;
  }
}

function renderState(data) {
  lastState = data;
  const backend = data.backend || {};
  const config = data.config || {};
  const server = data.server || {};

  if ($("version")) $("version").textContent = "v" + (data.version || "");
  renderStatus(backend);
  if ($("browser-hint")) $("browser-hint").textContent = backend.detail || "";

  if (document.activeElement !== $("set-port")) $("set-port").value = server.port ?? config.port ?? "";
  if (document.activeElement !== $("set-interval")) $("set-interval").value = config.min_request_interval_seconds ?? 2;
  if (document.activeElement !== $("set-idle")) $("set-idle").value = config.idle_seconds ?? 2.5;
  if (document.activeElement !== $("set-timeout")) $("set-timeout").value = config.request_timeout_seconds ?? 600;
  $("set-channel").value = config.browser_channel || "auto";
  $("set-thinking").checked = !!config.thinking;
  $("set-search").checked = !!config.web_search;
  $("set-lan").checked = !!config.serve_on_lan;
  $("set-cors").checked = !!config.cors_enabled;
  $("set-launch").checked = !!config.launch_browser_on_start;

  renderUrls(config, server);

  if ($("api-model")) $("api-model").textContent = config.model_name || "deepseek-web";
  if ($("api-model-2")) $("api-model-2").textContent = config.model_name || "deepseek-web";
  const keyEl = $("api-key");
  if (keyEl) {
    keyEl.textContent = config.api_key || "-";
    keyEl.classList.toggle("shown", keyShown);
  }

  const queue = data.queue || {};
  if ($("queue-info")) {
    $("queue-info").textContent = `排队 ${queue.waiting || 0} ｜ 当前任务 ${queue.active_job || "无"}`;
  }
  if ($("last-error")) $("last-error").textContent = queue.last_error || "无";
  if ($("log-view")) $("log-view").textContent = data.logs || "(暂无日志)";
}

async function refresh() {
  try {
    const response = await fetch("/admin/api/state");
    if (response.status === 401) {
      document.body.innerHTML =
        "<p style='font-family:sans-serif;padding:40px'>未授权：请通过启动服务时自动打开的设置页地址访问。</p>";
      return;
    }
    renderState(await response.json());
  } catch (err) {
    const pill = $("status-pill");
    if (pill) {
      pill.classList.remove("ready", "login");
      pill.classList.add("error");
      const label = pill.querySelector(".label");
      if (label) label.textContent = "无法连接服务";
    }
  }
}

/* ------------------------------------------------------------------ 交互绑定 */

function bindClick(id, handler) {
  const el = $(id);
  if (el) el.addEventListener("click", handler);
}

bindClick("btn-start", (event) =>
  withBusy(event.currentTarget, async () => {
    await api("browser_start");
    refresh();
  })
);
bindClick("btn-recheck", (event) =>
  withBusy(event.currentTarget, async () => {
    await api("recheck_login");
    refresh();
  })
);
bindClick("btn-focus", (event) => withBusy(event.currentTarget, () => api("focus_browser")));
bindClick("btn-stop", (event) =>
  withBusy(event.currentTarget, async () => {
    await api("browser_stop");
    refresh();
  })
);
bindClick("btn-diagnose", (event) =>
  withBusy(event.currentTarget, async () => {
    const result = await api("diagnose");
    if (result.data && $("test-result")) {
      $("test-result").textContent = JSON.stringify(result.data, null, 2);
    }
  })
);
bindClick("btn-clear", (event) => {
  if (!confirm("将关闭浏览器并删除登录数据（浏览器配置目录），下次需要重新登录。继续？")) return;
  return withBusy(event.currentTarget, async () => {
    await api("clear_login");
    refresh();
  });
});
bindClick("btn-save", (event) =>
  withBusy(event.currentTarget, async () => {
    await api("save_settings", {
      settings: {
        port: parseInt($("set-port").value || "0", 10),
        min_request_interval_seconds: parseFloat($("set-interval").value || "2"),
        idle_seconds: parseFloat($("set-idle").value || "2.5"),
        request_timeout_seconds: parseFloat($("set-timeout").value || "600"),
        browser_channel: $("set-channel").value,
        thinking: $("set-thinking").checked,
        web_search: $("set-search").checked,
        serve_on_lan: $("set-lan").checked,
        cors_enabled: $("set-cors").checked,
        launch_browser_on_start: $("set-launch").checked,
      },
    });
    refresh();
  })
);
bindClick("btn-regen", (event) => {
  if (!confirm("重新生成 API Key 后，已有客户端需要更新配置。继续？")) return;
  return withBusy(event.currentTarget, async () => {
    await api("regenerate_api_key");
    refresh();
  });
});
bindClick("btn-show-key", () => {
  keyShown = !keyShown;
  const keyEl = $("api-key");
  if (keyEl) keyEl.classList.toggle("shown", keyShown);
  const btn = $("btn-show-key");
  if (btn) btn.textContent = keyShown ? "隐藏" : "显示";
});
bindClick("btn-test", (event) =>
  withBusy(event.currentTarget, async () => {
    if ($("test-result")) $("test-result").textContent = "正在发送测试消息，请稍候…";
    const result = await api("test_message", { text: $("test-text").value });
    const data = result.data || {};
    if ($("test-result")) {
      $("test-result").textContent = data.ok
        ? `✅ 用时 ${data.seconds}s\n${data.thinking ? "【思考】\n" + data.thinking + "\n\n" : ""}${data.content}`
        : `❌ ${data.error || result.message || "失败"}`;
    }
    refresh();
  })
);

/* 复制按钮（事件委托，兼容动态生成的地址行） */
document.addEventListener("click", (event) => {
  const btn = event.target.closest(".btn-copy");
  if (!btn || btn.id === "btn-show-key" || btn.id === "btn-regen") return;
  const text = btn.dataset.copyText || ($(btn.dataset.copy) ? $(btn.dataset.copy).textContent : "");
  copyText(text, btn);
});

/* 折叠面板 */
document.querySelectorAll(".collapse-toggle").forEach((toggle) => {
  toggle.addEventListener("click", () => {
    const parent = toggle.closest(".collapse");
    if (parent) parent.classList.toggle("open");
  });
});

attachRipple(document.body);
refresh();
setInterval(refresh, 3000);
