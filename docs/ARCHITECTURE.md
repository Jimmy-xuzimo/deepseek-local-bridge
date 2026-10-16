# 架构说明

```
Chatbox / Codex CLI(+CC Switch)
        │  OpenAI 兼容 HTTP
        ▼
FastAPI 本地服务（127.0.0.1:8317）
  ├── /v1/chat/completions → 串行队列（BridgeService）
  ├── /v1/files            → 附件落盘（FileStore）
  ├── /admin（设置页）      → 登录、开关、诊断、日志
  └── DeepSeekWebBackend（Playwright）
        │  持久化浏览器配置（专用 profile，一次登录长期有效）
        ▼
chat.deepseek.com 网页版
```

## 关键设计

- **串行队列**：`BridgeService` 用 `asyncio.Lock` 保证同一时间只有一条消息在网页里发送，等待中的请求按先来后到排队；`max_queue` 之外直接返回 429，避免网页被刷爆。
- **会话复用与多会话映射**：`ConversationRegistry`（`app/bridge/conversations.py`）把客户端会话映射到 DeepSeek 网页对话，只保存 URL + 消息指纹。
  - 判断规则：忽略 system/developer 消息（客户端常注入时间戳提醒）；当“最后一条是用户消息、倒数第二条是助手消息、去掉这两条后的历史指纹”命中某个已记录对话时，认为是在续聊。
  - 命中且不是当前打开的对话时，直接用 `goto` 切回那个网页对话（网页侧会显示该对话的历史），随后只发送最后一条消息；未命中则新建网页对话并发送完整上下文。
  - 每次请求结束后用“已处理过的消息列表”更新指纹（不含客户端保存的助手回答，因此客户端改写助手内容不影响匹配），并写入 `conversations.json`，服务重启后仍能切回。
- **取消**：客户端断开或请求被取消时，服务尝试点击网页“停止生成”按钮并结束当前读取。
- **回答读取**：轮询网页 DOM，把“思考块”和“回答块”分别增量推送；用“停止按钮消失 / 文本静默窗口”两个信号判定回答结束。文本回退（网页重排）时用公共前缀兜底，保证最终内容完整。
- **工具调用桥接**：`tools` 会转成一段协议提示词附加到系统消息；模型输出被解析并校验（工具名必须在清单内、参数必须是对象）后才转成标准 `tool_calls`，解析失败按普通文本回答处理。
- **选择器可覆盖**：网页改版后可在数据目录放 `selectors.json`（结构见 `app/bridge/selectors.py` 的 `DEFAULT_SELECTORS`）覆盖任意选择器，无需改代码；设置页“保存诊断信息”会导出当前页面结构与候选选择器命中数量，便于定位。
- **监听与 CORS**：`serve_on_lan` 决定绑定 `127.0.0.1` 还是 `0.0.0.0`（需重启服务生效，管理员页面本身始终只允许本机访问）；CORS 由 `app/cors.py` 的纯 ASGI 中间件实现，直接读取运行时配置，因此开关即时生效且不影响流式响应。

## 事件模型

后端向前端产出四种事件：`ThinkingDelta`（思考增量）、`ContentDelta`（回答增量）、`Completed`（完成）、`Failed`（失败，含错误码）。API 层负责把它们映射为 OpenAI 的流式/非流式结构；错误码到 HTTP 状态的映射见 `app/openai_api.py` 的 `ERROR_STATUS`。

## 目录结构

```
app/
  main.py            FastAPI 应用装配
  openai_api.py      OpenAI 兼容接口与 SSE 编码
  admin_ui.py        设置页与本地管理接口
  service.py         串行队列与任务状态
  files_store.py     附件存储
  bridge/
    deepseek.py      Playwright 适配器（发送/读取/开关/诊断）
    prompt.py        消息渲染与会话指纹
    toolcall.py      工具调用协议与解析
    selectors.py     选择器注册表（可覆盖）
tests/               单元测试（使用 FakeBackend）
verify/real_check.py 登录后的真实验收脚本
scripts/             安装、运行、停止、打包脚本
```
