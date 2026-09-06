# M3 附件模块（Attachment）

> 输入文档：`../achievements_proposal.md`（第 7 章）、`../high-level-design.md`（4.3、6）  
> 前置依赖：M2、现有文件存储服务  
> 完成定义：成果证明材料可上传、预览、下载、替换、删除，格式与大小受控，且至少 1 份为提交前提。

## 任务清单

- [x] T3-1 附件上传接口
  - 交付物：`POST /api/v1/achievements/files`，登录用户可调用；格式仅 PDF/JPG/PNG，单文件不超过 20MB（可配置）；复用现有文件服务。
  - 验收：返回文件记录（id/name/path/size/mime/uploaded_at）；格式或超限返回明确错误。
- [x] T3-2 附件预览/下载接口
  - 交付物：`GET /api/v1/achievements/files/{file_id}`，仅本人或管理员可访问。
  - 验收：越权访问返回 404/403；Content-Type 与下载头正确。
- [x] T3-3 proofs 关联与最少 1 份校验
  - 交付物：创建/更新成果时写入 `proofs_json`，无附件提交报错。
  - 验收：多份附件正确保存；缺附件不能提交。
- [x] T3-4 附件删除与替换
  - 交付物：编辑成果时支持移除 proofs 中某项、替换为新文件；被删文件进入现有清理机制。
  - 验收：编辑后 proofs 与用户操作一致，孤立文件可被清理。
- [x] T3-5 附件模块测试
  - 交付物：`backend/tests/test_achievement_files.py`。
  - 验收：上传、格式/大小拒绝、越权下载、最少 1 份、替换删除、清理全部通过。
