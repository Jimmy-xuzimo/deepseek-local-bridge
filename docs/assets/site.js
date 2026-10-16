/* DeepSeek Local Bridge · 介绍页交互（无依赖） */

const I18N = {
  zh: {
    "doc.title": "DeepSeek Local Bridge · 把 DeepSeek 网页版变成本机 API",
    "nav.features": "特性",
    "nav.how": "原理",
    "nav.clients": "接入",
    "nav.download": "下载",
    "hero.badge": "非官方 · MIT 开源 · 数据不出本机",
    "hero.title": '把 DeepSeek 网页版<br/><span class="grad">变成本机可用的 API</span>',
    "hero.lead": "登录一次，Chatbox、Codex CLI 等客户端就能通过标准 OpenAI 接口调用 DeepSeek 网页版：流式输出、深度思考、联网搜索、附件与工具调用全都保留。",
    "hero.cta1": "下载便携包",
    "hero.ctaWindows": "下载 Windows 便携包",
    "hero.ctaMac": "下载 macOS 便携包",
    "hero.ctaLinux": "下载 Linux 便携包",
    "hero.mobileHint": "手机 / 平板无法直接运行便携包：在电脑上启动服务后，用局域网地址（192.168.x.x）把手机接进来即可。",
    "hero.cta2": "查看源码",
    "hero.meta": "Windows / macOS / Linux · x64 与 ARM64 · 一条命令启动",
    "stats.platforms": "平台便携包",
    "stats.tests": "单元测试",
    "stats.ci": "CI 任务全绿",
    "stats.local": "本地运行",
    "demo.ready": "已就绪",
    "demo.title": "DeepSeek Local Bridge",
    "demo.endpoint": "本机地址",
    "demo.lan": "局域网",
    "demo.think": "深度思考",
    "demo.search": "联网搜索",
    "demo.cors": "CORS",
    "demo.client": "客户端",
    "demo.bridge": "本机服务",
    "demo.web": "DeepSeek 网页",
    "features.title": "能力一览",
    "features.lead": "标准接口 + 网页版能力全覆盖，客户端几乎不用改配置。",
    "f1.t": "OpenAI 兼容",
    "f1.d": "提供 /v1/chat/completions（SSE 流式）、/v1/models 与 /v1/files，任何兼容客户端直接填地址即可。",
    "f2.t": "深度思考",
    "f2.d": "网页版思考过程通过 reasoning_content 回传，Chatbox 里可以直接查看模型的推理链。",
    "f3.t": "联网搜索",
    "f3.d": "一键开启网页版联网搜索，回答里保留网页给出的参考链接。",
    "f4.t": "附件直传",
    "f4.d": "图片、PDF、TXT/MD、DOCX 都能丢给网页版解析，接口层兼容图片与文件两种写法。",
    "f5.t": "工具调用",
    "f5.d": "把 function calling 桥接到网页版，配合 CC Switch 可让 Codex CLI 完成读写代码、跑测试的完整闭环。",
    "f6.t": "多会话映射",
    "f6.d": "客户端每个对话对应一个网页对话；新建会新建，切回旧对话会切回原来的网页对话，上下文不丢。",
    "f7.t": "局域网可用",
    "f7.d": "开启“在网络中提供服务”，手机、平板用 192.168 地址加同一个 API Key 即可接入，CORS 随时开关。",
    "f8.t": "稳定与可控",
    "f8.d": "串行队列、请求取消、网页限流识别（429）、请求最小间隔、页面诊断与选择器覆盖，出问题能自查。",
    "f9.t": "跨平台",
    "f9.d": "Windows / macOS / Linux，x64 与 ARM64 都有构建；一键脚本、便携包与 CI 三件套齐全。",
    "how.title": "三步开始",
    "how.lead": "不需要官方 API Key，用你已有的网页版账号即可。",
    "how.s1t": "启动并登录一次",
    "how.s1d": "运行 start.bat / ./start.sh，弹出专用浏览器窗口登录 DeepSeek；登录状态长期保留，可以最小化窗口。",
    "how.s2t": "本地服务就绪",
    "how.s2d": "设置页自动打开，显示 127.0.0.1:8317、API Key、思考/联网开关与局域网地址，还带一键自测。",
    "how.s3t": "客户端接入",
    "how.s3d": "Chatbox 填地址与 Key 就能聊；Codex CLI 通过 CC Switch 的路由模式接入，工具调用自动桥接。",
    "clients.title": "客户端接入",
    "clients.lead": "复制粘贴即可，配置项一共三个：地址、Key、模型名。",
    "clients.copy": "复制",
    "clients.chatboxHead": "Chatbox · OpenAI API 兼容",
    "clients.codexHead": "CC Switch · Routing",
    "clients.chatboxTip": "Chatbox 会自动补 /v1；连不上时改成 http://127.0.0.1:8317/v1 再试。",
    "clients.codexTip": "Codex 用 Responses 协议，交给 CC Switch 转成 Chat Completions 再进本服务。",
    "clients.curlTip": "Python 里把 base_url 设为 http://127.0.0.1:8317/v1 即可直接复用 OpenAI SDK。",
    "clients.chatboxSnippet": '<span class="c-key">API 域名</span>  http://127.0.0.1:8317\n<span class="c-key">API Key</span>   在设置页「客户端接入」一键复制\n<span class="c-key">模型名称</span>  deepseek-web',
    "clients.codexSnippet": '<span class="c-key">API Request URL</span>  http://127.0.0.1:8317/v1\n<span class="c-key">Default Model</span>    deepseek-web\n<span class="c-key">Upstream Format</span>  OpenAI Chat Completions（需要路由）\n<span class="c-key">Routing</span>          打开总开关并启用 Codex，然后重启终端',
    "dl.title": "下载便携包",
    "dl.lead": "自带 Python 运行时，解压即用；也可以从源码一键启动。",
    "qs.title": "从源码启动",
    "faq.title": "常见疑问",
    "faq.q1": "需要官方 API Key 吗？",
    "faq.a1": "不需要。它使用你已登录的 DeepSeek 网页版账号，因此也不受官方 API 计费影响。",
    "faq.q2": "数据会上传到别处吗？",
    "faq.a2": "服务只监听本机，登录配置、附件、日志、会话映射都存在你的数据目录里；日志只记录长度与耗时，不记录对话内容和凭证。",
    "faq.q3": "网页改版了怎么办？",
    "faq.a3": "设置页可以一键保存诊断信息（页面结构与选择器命中情况），在数据目录放一个 selectors.json 就能覆盖失效的选择器，不用改代码。",
    "faq.q4": "会有账号风险吗？",
    "faq.a4": "这是非官方方式，可能受网页改版与账号风控影响，请仅个人学习使用、遵守服务条款，避免高频或商用请求。",
    "faq.q5": "Windows 提示“不信任的应用”怎么办？",
    "faq.a5": "便携包没有代码签名，首次运行会被 SmartScreen 拦一下：右键 zip → 属性 → 勾选“解除锁定”再解压，或者点“更多信息 → 仍要运行”。想校验文件可对照 Release 里的 SHA256SUMS.txt。",
    "footer.note": "非官方项目 · 仅供个人学习使用 · 请遵守 DeepSeek 服务条款",
    "footer.dl": "下载"
  },
  en: {
    "doc.title": "DeepSeek Local Bridge · Turn the DeepSeek web app into a local API",
    "nav.features": "Features",
    "nav.how": "How it works",
    "nav.clients": "Clients",
    "nav.download": "Download",
    "hero.badge": "Unofficial · MIT licensed · Your data stays local",
    "hero.title": 'Turn the DeepSeek web app<br/><span class="grad">into a local API you can use anywhere</span>',
    "hero.lead": "Sign in once, then Chatbox, Codex CLI and any OpenAI-compatible client can talk to the DeepSeek web app — streaming, deep thinking, web search, attachments and tool calls included.",
    "hero.cta1": "Download portable build",
    "hero.ctaWindows": "Download for Windows",
    "hero.ctaMac": "Download for macOS",
    "hero.ctaLinux": "Download for Linux",
    "hero.mobileHint": "Portable builds need a desktop OS — start the service on your computer, then connect your phone through the LAN URL (192.168.x.x).",
    "hero.cta2": "View source",
    "hero.meta": "Windows / macOS / Linux · x64 and ARM64 · one command to start",
    "stats.platforms": "portable builds",
    "stats.tests": "unit tests",
    "stats.ci": "green CI jobs",
    "stats.local": "runs locally",
    "demo.ready": "Ready",
    "demo.title": "DeepSeek Local Bridge",
    "demo.endpoint": "Local URL",
    "demo.lan": "LAN",
    "demo.think": "Deep thinking",
    "demo.search": "Web search",
    "demo.cors": "CORS",
    "demo.client": "Client",
    "demo.bridge": "Local bridge",
    "demo.web": "DeepSeek web",
    "features.title": "What you get",
    "features.lead": "A standard API on top of everything the web app can do — clients barely need any setup.",
    "f1.t": "OpenAI compatible",
    "f1.d": "/v1/chat/completions (SSE streaming), /v1/models and /v1/files — point any compatible client at the local URL.",
    "f2.t": "Deep thinking",
    "f2.d": "The web app's reasoning is returned as reasoning_content, so Chatbox can show the model's chain of thought.",
    "f3.t": "Web search",
    "f3.d": "Toggle the web app's search on and keep the reference links it returns.",
    "f4.t": "Attachments",
    "f4.d": "Images, PDF, TXT/MD and DOCX are forwarded to the web app; both image and file content parts are supported.",
    "f5.t": "Tool calling",
    "f5.d": "Function calling is bridged to the web app — with CC Switch, Codex CLI can read code, edit it and run tests end to end.",
    "f6.t": "Conversation mapping",
    "f6.d": "Each client conversation maps to its own web conversation; switch back and your context is still there.",
    "f7.t": "LAN ready",
    "f7.d": "Serve on the local network so phones and tablets can connect with a 192.168 address and the same API key; CORS is a switch.",
    "f8.t": "Stable and observable",
    "f8.d": "Serialized queue, cancellation, rate-limit detection (429), minimum request interval, diagnostics and selector overrides.",
    "f9.t": "Cross platform",
    "f9.d": "Windows, macOS and Linux on x64 and ARM64, with one-click scripts, portable builds and CI coverage.",
    "how.title": "Three steps",
    "how.lead": "No official API key required — it uses the web account you already have.",
    "how.s1t": "Start and sign in once",
    "how.s1d": "Run start.bat / ./start.sh, sign in to DeepSeek in the dedicated browser window; the session is kept for next time.",
    "how.s2t": "Local service is ready",
    "how.s2d": "The settings page opens with 127.0.0.1:8317, your API key, thinking/search switches, LAN URL and a built-in self test.",
    "how.s3t": "Connect your client",
    "how.s3d": "Paste the URL and key into Chatbox, or route Codex CLI through CC Switch — tool calls are bridged automatically.",
    "clients.title": "Connect a client",
    "clients.lead": "Copy and paste: you only need the URL, the key and the model name.",
    "clients.copy": "Copy",
    "clients.chatboxHead": "Chatbox · OpenAI compatible",
    "clients.codexHead": "CC Switch · Routing",
    "clients.chatboxTip": "Chatbox appends /v1 automatically; if it fails, try http://127.0.0.1:8317/v1.",
    "clients.codexTip": "Codex speaks the Responses API; let CC Switch convert it to Chat Completions for this service.",
    "clients.curlTip": "In Python just set base_url to http://127.0.0.1:8317/v1 and reuse the official OpenAI SDK.",
    "clients.chatboxSnippet": '<span class="c-key">API host</span>   http://127.0.0.1:8317\n<span class="c-key">API key</span>    copy it from the settings page\n<span class="c-key">Model</span>      deepseek-web',
    "clients.codexSnippet": '<span class="c-key">API Request URL</span>  http://127.0.0.1:8317/v1\n<span class="c-key">Default Model</span>    deepseek-web\n<span class="c-key">Upstream Format</span>  OpenAI Chat Completions (routing required)\n<span class="c-key">Routing</span>           enable it and turn Codex on, then restart the terminal',
    "dl.title": "Download",
    "dl.lead": "Portable builds bundle Python — unzip and run. Or start straight from source.",
    "qs.title": "Start from source",
    "faq.title": "FAQ",
    "faq.q1": "Do I need an official API key?",
    "faq.a1": "No. It drives the DeepSeek web account you are already signed in to, so official API billing does not apply.",
    "faq.q2": "Is my data uploaded anywhere?",
    "faq.a2": "The service only listens on localhost. Login profile, uploads, logs and conversation mapping live in your data directory, and logs never contain message text or credentials.",
    "faq.q3": "What if the website changes?",
    "faq.a3": "Save a diagnostic dump from the settings page (page structure and selector hits), then drop a selectors.json into the data directory to override broken selectors — no code changes.",
    "faq.q4": "Any risk to my account?",
    "faq.a4": "This is an unofficial approach and can be affected by site changes or account controls. Keep it for personal study, follow the terms of service and avoid heavy or commercial use.",
    "faq.q5": "Windows says \"unrecognized app\" — what now?",
    "faq.a5": "The portable build is not code-signed, so SmartScreen stops it once: right-click the zip → Properties → tick \"Unblock\" before extracting, or choose \"More info → Run anyway\". You can also verify the file against SHA256SUMS.txt in the release.",
    "footer.note": "Unofficial project · Personal study only · Please respect DeepSeek's terms of service",
    "footer.dl": "Download"
  }
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/* ---------- 设备 / 浏览器识别（UA + UA-CH，失败时退回媒体查询） ---------- */
function detectDevice() {
  const ua = navigator.userAgent || "";
  const platform = (navigator.userAgentData && navigator.userAgentData.platform) || "";
  const touchPoints = navigator.maxTouchPoints || 0;
  const coarsePointer = window.matchMedia("(pointer: coarse)").matches;
  const canHover = window.matchMedia("(hover: hover)").matches;
  // iPadOS 13+ 的 UA 与 macOS 相同：用“触摸点 + 粗指针”区分，避免触屏笔记本被误判
  const isIOS = /iPad|iPhone|iPod/.test(ua)
    || (platform === "macOS" && touchPoints > 1 && coarsePointer);
  const isAndroid = /Android/.test(ua) || platform === "Android";
  const isTablet = isIOS ? /iPad/.test(ua) || (touchPoints > 1 && !/iPhone/.test(ua))
                         : isAndroid && !/Mobile/.test(ua);
  const os = isIOS ? "ios"
    : isAndroid ? "android"
    : /Windows/i.test(platform || ua) ? "windows"
    : /Mac/i.test(platform || ua) ? "macos"
    : /Linux|X11|CrOS/i.test(platform || ua) ? "linux"
    : "unknown";
  return {
    os,
    isMobile: isIOS || isAndroid,
    isTablet: Boolean(isTablet),
    // 只有“不能悬停”的设备才算触屏（触屏笔记本仍按桌面处理）
    isTouch: !canHover || /Mobile|Tablet|Android|iPhone|iPad/.test(ua),
  };
}

const DEVICE = detectDevice();

function markDevice() {
  const root = document.documentElement;
  root.dataset.os = DEVICE.os;
  root.classList.add(DEVICE.isMobile ? "is-mobile" : "is-desktop");
  if (DEVICE.isTablet) root.classList.add("is-tablet");
  if (DEVICE.isTouch) root.classList.add("is-touch");
  root.classList.add(`os-${DEVICE.os}`);
}

/* 按系统给出对应的下载文案；手机/平板给出局域网接入提示 */
function updateDownloadCta() {
  const label = $("#cta-label");
  const hint = $("#mobile-hint");
  const lang = document.documentElement.lang === "en" ? "en" : "zh";
  const dict = I18N[lang];
  if (label) {
    const key = { windows: "hero.ctaWindows", macos: "hero.ctaMac", linux: "hero.ctaLinux" }[DEVICE.os];
    label.textContent = dict[key] || dict["hero.cta1"];
  }
  if (hint) {
    const mobile = DEVICE.isMobile;
    hint.hidden = !mobile;
    if (mobile) {
      hint.textContent = dict["hero.mobileHint"];
      hint.classList.add("in");
    }
  }
}

/* ---------- 主题 ---------- */
function applyTheme(theme, persist = true) {
  document.documentElement.dataset.theme = theme;
  const btn = $("#theme-toggle");
  if (btn) btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
  const meta = $("#theme-color");
  if (meta) meta.setAttribute("content", theme === "dark" ? "#080b12" : "#f6f8fd");
  if (persist) {
    try { localStorage.setItem("dsb-theme", theme); } catch (e) { /* ignore */ }
  }
}

/* ---------- 语言 ---------- */
function applyLang(lang, persist = true) {
  const dict = I18N[lang] || I18N.zh;
  document.documentElement.lang = lang === "en" ? "en" : "zh-CN";
  document.title = dict["doc.title"] || document.title;
  $$("[data-i18n]").forEach((el) => {
    const value = dict[el.dataset.i18n];
    if (value !== undefined) el.textContent = value;
  });
  $$("[data-i18n-html]").forEach((el) => {
    const value = dict[el.dataset.i18nHtml];
    if (value !== undefined) el.innerHTML = value;
  });
  const toggle = $("#lang-toggle");
  if (toggle) toggle.dataset.lang = lang;
  updateDownloadCta();
  if (persist) {
    try { localStorage.setItem("dsb-lang", lang); } catch (e) { /* ignore */ }
  }
}

/* ---------- 进入动画 ---------- */
function setupReveal() {
  const items = $$(".reveal");
  if (!("IntersectionObserver" in window)) {
    items.forEach((el) => el.classList.add("in"));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      const group = el.parentElement ? Array.from(el.parentElement.children).indexOf(el) : 0;
      el.style.transitionDelay = `${Math.min(group, 6) * 70}ms`;
      el.classList.add("in");
      observer.unobserve(el);
      if (el.classList.contains("stats") || el.querySelector?.("[data-count]")) countUp(el);
      if (el.classList.contains("hero-visual")) startTyping();
    });
  }, { threshold: 0.15, rootMargin: "0px 0px -40px" });
  items.forEach((el) => observer.observe(el));
  // 兜底：无论如何 2.5 秒后全部显示，避免异常环境下内容不可见
  setTimeout(() => items.forEach((el) => el.classList.add("in")), 2500);
}

/* ---------- 数字增长 ---------- */
function countUp(root) {
  $$("[data-count]", root).forEach((el) => {
    const target = Number(el.dataset.count || 0);
    const suffix = el.dataset.suffix || "";
    const duration = 1100;
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

/* ---------- 窗口里的打字效果 ---------- */
function startTyping() {
  const el = $(".typing");
  if (!el || el.dataset.typed === "1") return;
  el.dataset.typed = "1";
  const text = el.dataset.text || "";
  let i = 0;
  const step = () => {
    el.textContent = text.slice(0, ++i);
    if (i < text.length) setTimeout(step, 42);
  };
  setTimeout(step, 320);
}

/* ---------- Tabs ---------- */
function setupTabs() {
  $$(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const name = btn.dataset.tab;
      $$(".tab-btn").forEach((b) => {
        const active = b === btn;
        b.classList.toggle("active", active);
        b.setAttribute("aria-selected", active ? "true" : "false");
      });
      $$(".tab-panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === name));
    });
  });
}

/* ---------- 复制 ---------- */
function setupCopy() {
  $$(".copy-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const target = document.getElementById(btn.dataset.copyTarget);
      if (!target) return;
      const text = target.innerText;
      try {
        await navigator.clipboard.writeText(text);
      } catch (e) {
        const range = document.createRange();
        range.selectNodeContents(target);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        document.execCommand("copy");
        sel.removeAllRanges();
      }
      btn.classList.add("done");
      const label = $("span", btn);
      const original = label ? label.textContent : "";
      if (label) label.textContent = document.documentElement.lang === "en" ? "Copied" : "已复制";
      setTimeout(() => {
        btn.classList.remove("done");
        if (label) label.textContent = original;
      }, 1400);
    });
  });
}

/* ---------- 顶栏阴影 ---------- */
function setupNav() {
  const nav = $("#nav");
  const onScroll = () => nav.classList.toggle("scrolled", window.scrollY > 8);
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });
}

/* ---------- 初始化 ---------- */
(function init() {
  markDevice();
  let theme = "light";
  let lang = "zh";
  try {
    theme = localStorage.getItem("dsb-theme") || "light";
    lang = localStorage.getItem("dsb-lang") || "zh";
  } catch (e) { /* ignore */ }
  applyTheme(theme, false);
  applyLang(lang, false);

  $("#theme-toggle")?.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
  });
  $("#lang-toggle")?.addEventListener("click", () => {
    const next = $("#lang-toggle").dataset.lang === "en" ? "zh" : "en";
    applyLang(next);
  });

  setupNav();
  setupReveal();
  setupTabs();
  setupCopy();
})();
