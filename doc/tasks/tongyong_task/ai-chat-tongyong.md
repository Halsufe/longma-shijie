# D5 AI 对话任务清单

> 来源：`tongyong_proposal.md` 第 8 章、`tongyong_design.md` 第 4.5 节
> 里程碑：M13 重新生成（P2）、M14 附件消息（P2）、M15 回答展示规范（P2）
> 依赖：S1 共享文件与预览服务、LLM 适配器、RAG

## M13 重新生成

- [x] 数据：`chat_messages.regenerated_at` 可空列 + Alembic 迁移。
- [x] 服务：`chat_service.regenerate_message`（仅最后一条 assistant、以上文重建上下文）。
- [x] 服务：会话级并发锁，生成期间新消息发送则取消或拒绝。
- [x] 路由：`POST /api/v1/chat/sessions/{id}/messages/{mid}/regenerate`（SSE）。
- [x] 前端：`chat.js` 助手消息悬停“重新生成”，生成中禁用，成功后标注“已重新生成”。
- [x] 测试：只影响最后一条助手消息、并发保护、失败提示。

## M14 附件消息

- [x] 数据：`ChatMessageAttachment` 模型 + Alembic 迁移。
- [x] 服务：`chat_attachment_service.py` 保存、权限校验、消息绑定。
- [x] 服务：文档解析注入上下文（最多 3 个、单文件 10MB、注入 ≤8000 字符）；图片保存不 OCR。
- [x] 路由：`POST /chat/sessions/{id}/messages` 支持 multipart，兼容 JSON。
- [x] 路由：附件列表/下载/预览（仅本人会话）。
- [x] 前端：`chat.js` composer 附件按钮、文件 chips、消息附件区（缩略图/下载）。
- [x] 测试：附件持久化、文档被 RAG 引用、越权访问拒绝。

## M15 回答展示规范

- [x] Prompt：ChatService 展示规范写入 `doc/prompt.md`、`doc/skills_prompt.md`。
- [x] 前端：本地 vendor 引入 `marked.min.js` + `dompurify.min.js`。
- [x] 前端：`messageHtml` 改用安全 Markdown 渲染（先脱敏）。
- [x] 样式：表格小屏横向滚动、代码块与列表样式对齐现有主题。
- [x] 评审：按正反例清单验证（无整篇代码块、无内部技术话术、结尾有可选操作）。

## 验收

- [x] 重新生成、附件消息、展示规范三项全部落地。
