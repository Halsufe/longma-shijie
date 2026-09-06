# S1 共享文件与预览服务任务清单

> 来源：`tongyong_design.md` 第 4.6 节
> 覆盖：M4 在线预览、M6 作业附件、M14 聊天附件共用的存储与预览能力

## S1.1 存储适配

- [x] `StorageService` 支持 `personal/class/assignment/submission/chat` scope。
- [x] 统一上传校验：扩展名白名单、文件头校验、大小限制、UUID 物理名。

## S1.2 Office 高保真转换

- [x] 封装 `soffice --headless --norestore -env:UserInstallation=... --convert-to pdf` 调用。
- [x] 每任务独立 LibreOffice user profile，避免并发互锁。
- [x] 超时控制（默认 60s）+ 失败重试 1 次 + 进程清理。
- [x] 全局并发信号量（默认 2）+ 每文件转换锁。
- [x] 转换范围 `.doc/.docx/.xls/.xlsx/.ppt/.pptx`，目标 PDF。
- [x] 配置项：`PREVIEW_OFFICE_ENABLED`、`PREVIEW_OFFICE_TIMEOUT_SECONDS`、`PREVIEW_OFFICE_MAX_MB`、`PREVIEW_CACHE_TTL_DAYS`。

## S1.3 预览渲染与缓存

- [x] PDF/图片 inline 输出（正确 content-type，浏览器原生阅读器）。
- [x] 文本/代码类按纯文本 `<pre>` 渲染。
- [x] Markdown 转安全 HTML（移除 script、事件属性、iframe、外部资源）。
- [x] 预览缓存键 `sha256(stored_name + size + version)`，产物入 `storage/preview_cache/`。
- [x] 扩展 `workers/file_cleanup.py` 清理超 TTL 预览缓存。
- [x] 统一返回结构 `{supported, preview_url, content, message}`。

## S1.4 错误防护

- [x] soffice 缺失、加密/损坏文件、超时、超限统一降级为“暂不支持预览，请下载查看”。
- [x] 内部异常只记日志，不进入响应体。
- [x] 测试：转换失败降级、缓存命中、缓存清理与安全渲染。

## 验收

- [x] 知识库、作业附件、聊天附件三类场景均可复用同一预览服务。
