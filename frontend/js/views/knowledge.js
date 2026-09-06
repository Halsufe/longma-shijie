import { api, download, qs } from "../api.js";
import { confirmAction, emptyState, escapeHtml, formatBytes, formatDate, icon, loadingState, pageHeader, showModal, statusBadge, toast } from "../ui.js";

export async function renderKnowledge(container, context) {
  let scope = "personal";
  let query = "";
  let files = [];
  let folders = [];
  let folderId = null;
  let quota = null;

  container.innerHTML = pageHeader("知识库", "管理个人资料，并查阅班级共享知识。") + loadingState("正在加载知识库");

  const endpoint = () => scope === "personal" ? "/api/v1/knowledge" : "/api/v1/class-knowledge";

  async function load() {
    const calls = [api(`${endpoint()}/files${qs({ page_size: 100, q: query, folder_id: folderId })}`), api(`${endpoint()}/folders`)];
    if (scope === "personal") calls.push(api("/api/v1/knowledge/quota"));
    const results = await Promise.all(calls);
    files = results[0].items;
    folders = results[1].items;
    quota = scope === "personal" ? results[2] : null;
  }

  function renderTable() {
    if (!files.length) return emptyState(scope === "personal" ? "个人知识库为空" : "班级知识库为空", scope === "personal" ? "上传学习资料后，可以在 AI 对话中检索引用。" : "管理员上传后，全班成员可以检索和下载。", canUpload() ? '<button class="button button-primary" id="empty-upload">上传文件</button>' : "");
    return `<div class="table-wrap"><table class="data-table"><thead><tr><th>文件</th><th>标签</th><th>大小</th><th>解析状态</th><th>更新时间</th><th></th></tr></thead><tbody>${files.map(file => `
      <tr><td><div class="table-title"><span class="quick-item-icon">${icon("file")}</span><span><strong>${escapeHtml(file.original_name)}</strong><span>${escapeHtml(file.mime_type || "未知类型")}</span></span></div></td><td>${file.tag ? `<span class="tag">${escapeHtml(file.tag)}</span>` : '<span class="muted">无</span>'}</td><td>${formatBytes(file.size)}</td><td>${statusBadge(file.parse_status)}</td><td class="nowrap">${formatDate(file.updated_at)}</td><td><div class="table-actions"><button class="icon-button" data-preview="${file.id}" aria-label="预览">${icon("eye")}</button><button class="icon-button" data-download="${file.id}" aria-label="下载">${icon("download")}</button>${canManage(file) ? `<button class="icon-button" data-move="${file.id}" aria-label="移动">${icon("folder")}</button>${scope === "class" ? `<button class="icon-button" data-version="${file.id}" aria-label="版本历史">${icon("history")}</button>` : ""}<button class="icon-button" data-edit="${file.id}" aria-label="编辑">${icon("edit")}</button><button class="icon-button danger" data-delete="${file.id}" aria-label="删除">${icon("trash")}</button>` : ""}</div></td></tr>`).join("")}</tbody></table></div>`;
  }

  function canUpload() { return scope === "personal" || context.user.role === "admin"; }
  function canManage() { return scope === "personal" || context.user.role === "admin"; }

  function draw() {
    const usedMb = Number(quota?.used_mb ?? 0);
    const quotaMb = Number(quota?.quota_mb ?? 0);
    const quotaPercentage = Number(quota?.percentage ?? 0);
    const quotaBlock = quota ? `<div class="panel" style="margin-bottom:14px"><div class="panel-body"><div class="stat-card-top"><span>个人存储空间</span><strong>${usedMb.toFixed(2)} MB / ${quotaMb.toFixed(0)} MB</strong></div><div style="height:7px;background:var(--surface-strong);border-radius:4px;margin-top:10px;overflow:hidden"><span style="display:block;height:100%;width:${Math.min(quotaPercentage, 100)}%;background:var(--primary)"></span></div></div></div>` : "";
    const currentFolder = folders.find(folder => folder.id === folderId);
    container.innerHTML = `
      ${pageHeader("知识库", "管理个人资料，并查阅班级共享知识。", canUpload() ? `<button class="button button-primary" id="upload-file">${icon("upload")} 上传文件</button>` : "")}
      <div class="toolbar">
        <div class="segmented"><button class="segment ${scope === "personal" ? "active" : ""}" data-scope="personal">个人知识库</button><button class="segment ${scope === "class" ? "active" : ""}" data-scope="class">班级知识库</button></div>
        <form class="search-box" id="file-search">${icon("search")}<input class="input" name="q" value="${escapeHtml(query)}" placeholder="搜索文件名"></form>
      </div>
      <div class="toolbar"><div class="segmented"><button class="segment ${folderId === null ? "active" : ""}" data-folder="">全部文件</button>${folders.map(folder => `<button class="segment ${folderId === folder.id ? "active" : ""}" data-folder="${folder.id}">${escapeHtml(folder.name)}</button>`).join("")}</div>${canUpload() ? '<button class="button button-secondary" id="create-folder">新建文件夹</button>' : ""}</div>
      <nav class="breadcrumbs" aria-label="当前位置"><button type="button" class="breadcrumb-link" data-folder="">${scope === "personal" ? "个人知识库" : "班级知识库"}</button>${currentFolder ? `${icon("arrow", 14)}<span aria-current="page">${escapeHtml(currentFolder.name)}</span>` : ""}${query ? `<span class="badge badge-info">搜索：${escapeHtml(query)}</span>` : ""}</nav>
      ${quotaBlock}
      <section class="panel panel-flush">${renderTable()}</section>`;
    bind();
  }

  function uploadModal() {
    showModal({
      title: scope === "personal" ? "上传到个人知识库" : "上传到班级知识库",
      submitText: "开始上传",
      content: `<label class="field"><span>选择文件</span><input class="input" type="file" name="file" accept=".pdf,.docx,.txt,.md" required><small>支持 PDF、DOCX、TXT、Markdown，单文件最大 50 MB。</small></label><label class="field"><span>标签</span><input class="input" name="tag" maxlength="100" placeholder="例如：课程资料"></label>`,
      onSubmit: async data => {
        const file = data.get("file");
        if (!file?.size) throw new Error("请选择文件");
        const form = new FormData();
        form.append("file", file);
        if (data.get("tag")) form.append("tag", data.get("tag"));
        if (folderId !== null) form.append("folder_id", folderId);
        await api(`${endpoint()}/upload`, { method: "POST", body: form });
        await load();
        draw();
        toast("文件已上传并开始解析");
      },
    });
  }

  function bind() {
    container.querySelectorAll("[data-folder]").forEach(node => node.addEventListener("click", async () => { folderId = node.dataset.folder ? Number(node.dataset.folder) : null; await load(); draw(); }));
    container.querySelector("#create-folder")?.addEventListener("click", () => showModal({ title: "新建文件夹", submitText: "创建", content: '<label class="field"><span>名称</span><input class="input" name="name" maxlength="100" required></label>', onSubmit: async data => { await api(`${endpoint()}/folders`, { method: "POST", body: JSON.stringify({ name: data.get("name") }) }); await load(); draw(); toast("文件夹已创建"); } }));
    container.querySelectorAll("[data-scope]").forEach(node => node.addEventListener("click", async () => {
      scope = node.dataset.scope;
      query = "";
      container.innerHTML = loadingState("正在切换知识库");
      await load();
      draw();
    }));
    container.querySelector("#upload-file")?.addEventListener("click", uploadModal);
    container.querySelector("#empty-upload")?.addEventListener("click", uploadModal);
    container.querySelector("#file-search")?.addEventListener("submit", async event => {
      event.preventDefault();
      query = new FormData(event.currentTarget).get("q").trim();
      await load();
      draw();
    });
    container.querySelectorAll("[data-download]").forEach(node => node.addEventListener("click", async () => {
      const file = files.find(item => item.id === Number(node.dataset.download));
      try { await download(`${endpoint()}/files/${file.id}/download`, file.original_name); } catch (error) { toast(error.message, "danger"); }
    }));
    container.querySelectorAll("[data-preview]").forEach(node => {
      node.addEventListener("click", async () => {
        const result = await api(`${endpoint()}/files/${node.dataset.preview}/preview`);
        const content = result.supported
          ? (result.format === "html"
            ? result.content
            : `<iframe style="width:100%;height:65vh" src="${endpoint()}/${result.preview_url}"></iframe>`)
          : `<p>${escapeHtml(result.content || "暂不支持预览，请下载查看")}</p>`;
        showModal({ title: result.original_name, content });
      });
    });
    container.querySelectorAll("[data-move]").forEach(node => {
      node.addEventListener("click", () => {
        showModal({
          title: "移动文件",
          submitText: "移动",
          content: `<label class="field"><span>目标文件夹</span><select class="select" name="folder_id"><option value="">根目录</option>${folders.map(folder => `<option value="${folder.id}">${escapeHtml(folder.name)}</option>`).join("")}</select></label>`,
          onSubmit: async data => {
            await api(`${endpoint()}/files/${node.dataset.move}/move`, {
              method: "PUT",
              body: JSON.stringify({ folder_id: data.get("folder_id") ? Number(data.get("folder_id")) : null }),
            });
            await load();
            draw();
          },
        });
      });
    });
    container.querySelectorAll("[data-version]").forEach(node => {
      node.addEventListener("click", async () => {
        const versions = await api(`${endpoint()}/files/${node.dataset.version}/versions`);
        showModal({
          title: "版本历史",
          content: versions.length
            ? versions.map(item => `<p>v${item.version} · ${escapeHtml(item.original_name)} · ${formatDate(item.uploaded_at)}</p>`).join("")
            : '<p class="muted">暂无历史版本</p>',
        });
      });
    });
    container.querySelectorAll("[data-edit]").forEach(node => node.addEventListener("click", () => {
      const file = files.find(item => item.id === Number(node.dataset.edit));
      showModal({
        title: "编辑文件信息", submitText: "保存",
        content: `<label class="field"><span>文件名</span><input class="input" name="original_name" value="${escapeHtml(file.original_name)}" required></label><label class="field"><span>标签</span><input class="input" name="tag" value="${escapeHtml(file.tag || "")}"></label>${scope === "class" ? `<label class="field"><span><input type="checkbox" name="is_pinned" ${file.is_pinned ? "checked" : ""}> 置顶文件</span></label>` : ""}`,
        onSubmit: async data => {
          await api(`${endpoint()}/files/${file.id}`, { method: "PUT", body: JSON.stringify({ original_name: data.get("original_name"), tag: data.get("tag") || null, ...(scope === "class" ? { is_pinned: data.get("is_pinned") === "on" } : {}) }) });
          await load(); draw(); toast("文件信息已更新");
        },
      });
    }));
    container.querySelectorAll("[data-delete]").forEach(node => node.addEventListener("click", () => {
      const file = files.find(item => item.id === Number(node.dataset.delete));
      confirmAction(`确认删除“${file.original_name}”？文件将进入软删除状态。`, async () => {
        await api(`${endpoint()}/files/${file.id}`, { method: "DELETE" });
        await load(); draw(); toast("文件已删除");
      }, "删除");
    }));
  }

  try { await load(); draw(); } catch (error) { container.innerHTML = pageHeader("知识库", "管理个人资料，并查阅班级共享知识。") + emptyState("加载失败", error.message); }
}
