# 客户端接入

服务默认地址：`http://127.0.0.1:8317`，模型名：`deepseek-web`，API Key 在设置页“③ 客户端接入”复制。

在手机或其它电脑上接入时，把地址换成设置页里列出的局域网地址（例如 `http://192.168.1.100:8317/v1`，以设置页实际显示为准），API Key 相同。使用前提：设置页已开启“在网络中提供服务”，并已重启过服务；设备与电脑在同一个局域网。

## Chatbox

1. 设置 → 模型 → 添加自定义供应商，类型选择 “OpenAI API 兼容”。
2. API 域名：先填 `http://127.0.0.1:8317`（Chatbox 会自动追加 `/v1`）；如果提示 404/连接失败，再改为 `http://127.0.0.1:8317/v1`。
3. API Key：粘贴设置页里的 Key。
4. 模型：填写 `deepseek-web`（如果 Chatbox 需要先“获取模型列表”，点一下即可）。
5. 进入对话后：
   - 深度思考、联网搜索由设置页开关决定（也可以让 Chatbox 发 `thinking: true` 这样的扩展字段，但多数客户端 UI 不支持，直接在设置页切换更简单）。
   - 发送图片时 Chatbox 会以 data URL 形式传图，本服务会转成网页附件上传；文档类附件建议用“附件”功能上传后引用，或直接在本服务设置页测试。

手机版 Chatbox 的填法相同，只是 API 域名换成 `http://<电脑局域网IP>:8317`（同样先试不带 `/v1`）。

## CC Switch + Codex CLI（自动编程）

Codex CLI 使用 OpenAI Responses 协议，本服务只提供 Chat Completions，通过 CC Switch 的“本机路由”做协议转换。

1. 打开 CC Switch → 右上角添加供应商，选择 **Codex** 类型。
2. 填写：
   - 名称：`DeepSeek Local Bridge`
   - API Request URL：`http://127.0.0.1:8317/v1`
   - API Key：设置页里的 Key
   - Default Model：`deepseek-web`
3. 展开 **Advanced Options**，把 **Upstream Format** 改为 `OpenAI Chat Completions`（需要路由才能工作）。
4. 打开 Settings → Routing 中的 **Routing Master Switch**，并在 “Routing Enabled” 里勾选 **Codex**。此时 Codex 的 `config.toml` 会被改写到本地路由地址（`http://127.0.0.1:15721/v1`），真实请求再由 CC Switch 转发到本服务。
5. 重启终端里的 Codex，然后让 Codex 执行一个小任务（例如“读取 README.md 并总结”）。

工作方式与限制：

- 工具调用通过“提示词协议”桥接：本服务把 CC Switch 发来的 `tools` 转成结构化提示，模型输出 JSON 工具调用后再转回标准 `tool_calls`。如果模型输出格式不合法，本服务会退化为普通文本回答（客户端会看到普通回复而不是工具调用）。
- 带工具定义的请求会先缓冲完整回答再返回（避免半截 JSON 触发客户端解析错误），因此工具类请求的首字延迟比普通聊天高。
- 网页版是单会话串行：一次只处理一个 Codex 步骤，多步任务会依次排队，整体速度受网页端生成速度限制。
- 若 CC Switch 的界面文字与实际版本不同，以“上游格式 = OpenAI Chat Completions / Chat 格式”这一项为准。
