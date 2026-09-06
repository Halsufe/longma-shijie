# D2 知识库任务清�?
> 来源：`tongyong_proposal.md` �?5 章、`tongyong_design.md` �?4.2 �?> 里程碑：M3 文件夹与移动（P1）、M4 在线预览（P1）、M5 班级文件版本管理（P2�?> 依赖：S1 共享文件与预览服务、S4 兼容与迁�?
## M3 文件夹与移动

- [x] 数据：`KnowledgeFolder` 模型 + Alembic 迁移；`KnowledgeFile.folder_id` 可空列与索引�?- [x] 仓储：文件夹查重（scope+owner+name）、列表、非空校验、移动文件�?- [x] 服务：`knowledge_folder_service.py`（单层目录规则、空文件夹删除、移动校验）�?- [x] 路由：个人知识库 folders CRUD（`/api/v1/knowledge/folders`）�?- [x] 路由：班级知识库 folders CRUD（`/api/v1/class-knowledge/folders`，写�?admin）�?- [x] 路由：`GET /files?folder_id=` 过滤、上传支�?`folder_id`、`PUT /files/{id}/move`�?- [x] 前端：`knowledge.js` 新建/重命�?删除文件夹�?- [x] 前端：面包屑导航（全部文�?/ 文件夹名）与文件夹行、文件行区分展示�?- [x] 前端：移动弹窗（目标文件夹或根目录）�?- [x] 测试：个�?班级权限、同名拒绝、非空文件夹删除拒绝、移动后列表正确�?
## M4 在线预览

- [x] 路由：个�?`GET /knowledge/files/{id}/preview`、班�?`GET /class-knowledge/files/{id}/preview`（权限复用）�?- [x] 服务：`file_preview_adapter.py` 权限检查后调用 S1，返回统一结构�?- [x] 前端：`knowledge.js` 文件行“预览”按钮与弹窗（iframe/img/HTML）�?- [x] 规则：预览不计入 `download_count`�?- [x] 测试：六类格式预览、无权限返回 404/403、预览内容脱敏�?
## M5 班级文件版本管理

- [x] 数据：`KnowledgeFileVersion` 模型 + Alembic 迁移�?- [x] 服务：`knowledge_version_service.py` 替换逻辑（保存新文件、版�?1、旧记录入版本表）�?- [x] 服务：替换后重新解析并替�?`file_chunks`�?- [x] 路由：`POST /class-knowledge/files/{id}/replace`�?- [x] 路由：`GET .../files/{id}/versions` �?`GET .../versions/{version}/download`�?- [x] 规则：历史版本上�?20，超出清理最旧记录与物理文件�?- [x] 前端：`knowledge.js` 班级文件“上传新版本”与“版本历史”弹窗�?- [x] 测试：版本递增、历史下载�?0 上限、RAG 引用指向新版本�?
## 验收

- [x] 文件夹、面包屑、移动、预览、版本管理全部可用且权限正确�?
