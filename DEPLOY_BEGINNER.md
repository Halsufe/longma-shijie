# 初学者部署指南

本项目采用三部分：GitHub Pages 托管前端，Hugging Face Spaces 运行 FastAPI 后端，Supabase 提供 PostgreSQL 数据库和文件存储。GitHub Pages 本身不能运行 Python。

## 1. 创建 Supabase

1. 打开 <https://supabase.com>，注册并新建项目。
2. 在 **Project Settings → Database** 复制连接串。选择 URI 格式，并把其中的密码保管好，作为 Render 的 `DB_URL`。
3. 在 **Storage → New bucket** 创建名为 `longma-files` 的 bucket，保持 **Private**。
4. 在 **Project Settings → API** 复制 `Project URL` 和 `service_role` key。`service_role` 只能填写到 Render，不能提交到 GitHub，也不能写入前端。

数据库表会由 Render 启动时自动执行 `alembic upgrade head` 创建。

## 2. 创建 GitHub 仓库并推送

在本目录打开 PowerShell：

```powershell
cd D:\班级ai\BD\LM_SJ
git init
git add .
git commit -m "prepare cloud deployment"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

不要提交 `.env`、数据库文件或任何 API key；项目的 `.gitignore` 已经忽略这些内容。

## 3. 部署后端到 Hugging Face Spaces（无需银行卡）

1. 打开 <https://huggingface.co/new-space>，创建 Docker Space，名称填写 `longma-shijie-api`。
2. 在 Space Settings -> Repository secrets 添加：
   - `DB_URL`：Supabase Database URI
   - `CORS_ORIGINS`：先填 GitHub Pages 地址，例如 `https://halsufe.github.io`
   - `SUPABASE_URL`：Supabase Project URL
   - `SUPABASE_SERVICE_ROLE_KEY`：Supabase `service_role` key
   - `AI_API_KEY`：你的 AI 服务密钥（生产配置要求填写）
   - `ENV`：`prod`
   - `STORAGE_BACKEND`：`supabase`
   - `SUPABASE_STORAGE_BUCKET`：`longma-files`
   - `SECRET_KEY`、`MCP_SERVICE_TOKEN`：随机长字符串
3. 将本仓库内容同步到 Space，根目录 Dockerfile 会自动构建。
4. 打开 `https://<用户名>-longma-shijie-api.hf.space/health`，看到 `{"status":"ok"}` 才算成功。

## 4. 部署前端到 GitHub Pages

1. 在 GitHub 仓库打开 **Settings → Pages**。
2. **Source** 选择 **GitHub Actions**。
3. 打开 **Settings → Secrets and variables → Actions → Variables**，新建变量 `LONGMA_API_BASE_URL`，值为 Space 后端地址。
4. 再次推送代码，或在 **Actions → Deploy frontend to GitHub Pages → Run workflow** 手动运行。
5. 打开 GitHub Pages 给出的地址。登录页能打开且浏览器没有 CORS 错误，说明前后端已连通。

## 5. 首次验证

1. 用现有管理员账号登录。
2. 新建一个测试用户，使用另一台设备或无痕窗口登录。
3. 在一台设备发布一条公开资源，另一台设备刷新后应能看到。
4. 上传一个小 PDF，再在另一台设备下载；这一步验证的是 Supabase Storage，而不是浏览器缓存。

## 常见问题

- **CORS 错误**：把实际 Pages 地址（不带末尾 `/`）填入 Space 的 `CORS_ORIGINS`，保存并重新构建。
- **数据库连接失败**：检查 Supabase 连接串密码是否已 URL 编码；Render 与 Supabase 都支持 IPv4 时优先使用 Supabase 提供的连接池 URI。
- **文件上传失败**：确认 bucket 名为 `longma-files`，且 Render 中 `STORAGE_BACKEND=supabase`、URL 和 service role key 均已填写。
- **Spaces 免费服务休眠**：首次访问可能需要几十秒唤醒，这是平台限制，不是前端故障。
