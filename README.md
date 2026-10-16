# DeepSeek Local Bridge

把 DeepSeek 网页版（chat.deepseek.com）桥接成本机可用的 OpenAI 兼容 API：你只需在一个专用浏览器窗口里登录一次，之后 Chatbox、CC Switch + Codex CLI 等客户端就能通过本地接口使用 DeepSeek 网页版。

> ⚠️ 非官方项目：通过浏览器自动化调用网页版，可能受网页改版、账号风控影响，也可能不符合 DeepSeek 服务条款。请仅在本机、个人学习范围内使用，不要商用、不要大规模并发。

🌐 **项目介绍页（中英双语 / 深浅色主题）**：https://jimmy-xuzimo.github.io/deepseek-local-bridge/

## 功能

- `/v1/models`、`/v1/chat/completions`（支持 `stream` 流式输出），模型统一为 `deepseek-web`
- 深度思考（DeepThink）与联网搜索开关，在设置页统一控制，也支持请求级 `thinking` / `web_search` 覆盖
- 附件：图片（PNG/JPG）、PDF、TXT/MD、DOCX，支持 `image_url`（data URL）与 `/v1/files` 上传引用
- 工具调用（function calling）桥接：给模型工具定义，返回标准 `tool_calls`，可用于 Codex CLI 的自动编程
- 一个账号串行处理请求：正在回答时其余请求排队；支持取消、超时与登录过期提示
- 识别网页限流提示（“消息发送过于频繁”），返回 429；可设置请求最小间隔降低触发概率
- 多会话映射：客户端里每个对话对应一个 DeepSeek 网页对话；新建对话会在网页新建，**切回旧对话会切回原来的网页对话**，上下文保留（映射持久化在数据目录 `conversations.json`）
- 设置页（现代化界面，带过渡动画与按钮反馈）提供登录、开关、诊断、日志与客户端接入信息
- 服务端设置参照 LM Studio：服务端口、「在网络中提供服务」（局域网）、「启用 CORS」，并显示本机与 192.168 局域网地址
- 跨平台：Windows / macOS / Linux（x64 与 ARM64）均可运行；提供 Windows 与 macOS/Linux 两套脚本

## 环境要求

- Windows 10/11、macOS 12+ 或常见 Linux 发行版（x64 / ARM64）
- 已安装 Microsoft Edge（推荐）或 Google Chrome；两者都没有时可用 `python -m playwright install chromium` 安装内置 Chromium 兜底
- Python 3.10+（源码运行方式需要；便携包不需要）

## 快速开始（源码方式）

Windows：

1. 双击 `start.bat`（或运行 `powershell -ExecutionPolicy Bypass -File scripts\run.ps1`）。首次运行会自动创建 `.venv` 并安装依赖。

macOS / Linux：

1. 运行 `./start.sh`（或 `bash scripts/run.sh`）。首次运行会自动创建 `.venv` 并安装依赖。

两端后续步骤相同：

2. 服务启动后会自动打开设置页，并弹出一个浏览器窗口访问 DeepSeek。
3. 在浏览器窗口里登录 DeepSeek（手机号验证码、密码或微信扫码均可）。设置页显示“已就绪”即完成。
4. 打开 Chatbox：设置 → 模型 → 添加自定义供应商（OpenAI API 兼容）
   - API 域名：`http://127.0.0.1:8317`（Chatbox 会自动补 `/v1`；若连不上改为 `http://127.0.0.1:8317/v1`）
   - API Key：设置页“③ 客户端接入”里复制
   - 模型名：`deepseek-web`
5. 想让 Codex CLI 使用：见 [docs/CLIENTS.md](docs/CLIENTS.md)（通过 CC Switch 路由模式接入）。

停止服务：前台运行时按 `Ctrl+C`；后台运行时 Windows 执行 `powershell -File scripts\stop.ps1`，macOS/Linux 执行 `bash scripts/stop.sh`。

## 局域网使用（手机 / 其它电脑）

1. 设置页 → 「② 服务设置」确认「在网络中提供服务」为开启（默认开启），保存后重启服务（Windows：`scripts\restart.ps1`；macOS/Linux：`scripts/restart.sh`）。端口与局域网设置需要重启才生效。
2. 设置页「③ 客户端接入」会列出全部可用地址，例如：
   - 本机：`http://127.0.0.1:8317/v1`
   - 局域网：`http://192.168.1.100:8317/v1`（以设置页实际显示的地址为准）
3. 手机/其它电脑用局域网地址 + 同一个 API Key 接入（例如手机版 Chatbox）。
4. 第一次从其它设备访问时，系统防火墙可能弹窗询问，选择“允许”；macOS 可在“系统设置 → 网络 → 防火墙”中放行，Linux 视发行版放行 8317 端口。

安全提示：局域网开启后，同一网络内持有 API Key 的设备都能使用你的 DeepSeek 网页账号；请勿把端口映射到公网，也不要关闭 API Key 校验。设置页本身仅允许本机访问。

「启用 CORS」默认开启，用于浏览器网页类客户端跨域调用本服务；关闭后普通桌面客户端不受影响。CORS 开关即时生效，端口与局域网开关需要重启服务。

## 便携包

便携包内含自带 Python 运行时的可执行文件，目标机器无需安装 Python：

- Windows：`powershell -File scripts\build_portable.ps1` → `dist\DeepSeekBridge-win64-<版本>.zip`，解压后双击 `DeepSeekBridge.exe`。
- macOS / Linux：`bash scripts/build_portable.sh` → `dist/DeepSeekBridge-<系统>-<架构>-<版本>.zip`。
- 仓库自带 GitHub Actions 工作流（`.github/workflows/ci.yml`），在 Windows / Linux / macOS（Intel 与 Apple Silicon）上自动跑测试并产出便携包工件。

注意：PyInstaller 不支持交叉编译，**便携包需要在目标平台上构建**（或直接使用 CI 工件）。

### Windows 提示“不信任的应用 / 未知发布者”怎么办

便携包目前**没有代码签名证书**，因此从网络下载后第一次运行时，Windows SmartScreen 会弹出“Windows 已保护你的电脑 / 未知发布者”的提示。这不是病毒告警，而是“这个 exe 没有签名、系统不认识它”。

推荐做法（任选其一）：

1. **先解除锁定再解压**（最干净）：右键下载到的 zip → 属性 → 勾选底部的“解除锁定” → 确定，然后再解压运行；这样解压出来的文件不会带上“来自网络”的标记，通常就不会再弹提示。
2. 直接运行时点击提示里的 **“更多信息” → “仍要运行”**。
3. 用 PowerShell 解除锁定：`Unblock-File .\DeepSeekBridge-win64-0.1.1.zip`（解压前后都可以对 exe 再执行一次）。

想确认下载的文件没被篡改，可以对照 Release 里的 `SHA256SUMS.txt` 校验：

```powershell
Get-FileHash .\DeepSeekBridge-win64-0.1.1.zip -Algorithm SHA256
```

**彻底消除警告**需要给 exe 做代码签名（需要证书，属于账号/费用层面的事，项目本身无法自行解决）：

- 购买 OV / EV 代码签名证书（EV 可立即消除 SmartScreen 提示，OV 需要积累下载信誉），主流 CA 与国内 CA 均可；
- 或申请 [SignPath Foundation](https://signpath.org/)（面向开源项目免费签名，需审核，支持 GitHub Actions）；
- 或使用 Azure Trusted Signing（按月的微软签名服务，需要身份/组织验证）。

拿到证书或签名服务后，把签名步骤接进 `.github/workflows/ci.yml` 即可自动签署所有平台的产物。

## 数据与隐私

所有数据都在本机，默认数据目录：

| 平台 | 默认位置 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\DeepSeekBridge` |
| macOS | `~/Library/Application Support/DeepSeekBridge` |
| Linux | `$XDG_DATA_HOME/DeepSeekBridge`（默认 `~/.local/share/DeepSeekBridge`） |

目录里包含浏览器登录配置、上传附件、配置、日志、诊断文件与会话映射（`conversations.json`，只有 URL 和指纹）。日志只记录长度、耗时与错误，不记录对话内容、Cookie 或密码。设置页需要管理员令牌（启动脚本会自动打开带令牌的地址），且只允许本机访问。

## 平台支持

| 平台 | 状态 |
| --- | --- |
| Windows 10/11 x64 | ✅ 本机完整实测（登录、聊天、流式、思考、联网、附件、工具调用、局域网、CORS、便携包） |
| Windows ARM64 | ✅ 设计支持（Playwright 1.64 提供 `win_arm64` 轮子）；建议使用 ARM64 版 Python 与 Edge |
| macOS Intel / Apple Silicon | ✅ 设计支持（`macosx_11_0_arm64` / `x86_64` 轮子、独立脚本、CI 覆盖） |
| Linux x64 / ARM64 | ✅ 设计支持（`manylinux` x86_64 与 aarch64 轮子、独立脚本、CI 覆盖） |

除 Windows x64 外，其它平台由 CI 运行单元测试与打包验证；浏览器自动化链路需要真实账号登录，请按 `docs/VERIFY.md` 自行验收。

## 验证

登录后运行：

```powershell
.venv\Scripts\python.exe verify\real_check.py
```

脚本会逐项检查聊天、流式、思考、联网、附件与工具调用，输出 PASS/WARN/FAIL 汇总。详见 [docs/VERIFY.md](docs/VERIFY.md)。

## 文档

- [客户端接入（Chatbox / CC Switch + Codex CLI）](docs/CLIENTS.md)
- [常见问题与排查](docs/TROUBLESHOOTING.md)
- [架构说明](docs/ARCHITECTURE.md)
- [验收清单](docs/VERIFY.md)

## 开发

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
```

macOS / Linux 把 `.venv\Scripts\python.exe` 换成 `.venv/bin/python` 即可。

## 许可

MIT License，见 [LICENSE](LICENSE)。
