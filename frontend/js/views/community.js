import { api, qs } from "../api.js";
import { bindAchievementForm, renderAchievementForm, validateAchievementForm } from "../achievement_form.js";
import { renderAchievementCategoryGroups, renderAchievementList, bindAchievementList } from "../achievement_list.js?v=20260807-achievement-groups";
import { ACHIEVEMENT_CATEGORIES, ACHIEVEMENT_TEMPLATES, getAchievementTemplate } from "../achievement_templates.js";
import { bindAchievementTimeline, defaultAchievementYear, renderAchievementTimeline } from "../achievement_timeline.js";
import { createAchievementUpload, openAchievementProof, renderAchievementUpload } from "../achievement_upload.js";
import { confirmAction, emptyState, escapeHtml, formatBytes, formatDate, icon, loadingState, pageHeader, showModal, toast } from "../ui.js";

const RESOURCE_TYPES = { experience: "竞赛经验", material: "学习资料", tool: "项目工具", recruit: "团队招募", competition: "比赛信息", project: "项目资源" };

function categoryOptions(selected = "") {
  return ACHIEVEMENT_CATEGORIES.map(category => `<option value="${category}" ${selected === category ? "selected" : ""}>${escapeHtml(ACHIEVEMENT_TEMPLATES[category].category_label)}</option>`).join("");
}

function detailValue(value) {
  if (typeof value === "boolean") return value ? "是" : "否";
  if (value === null || value === undefined || value === "") return "未设置";
  return String(value);
}

function renderAchievementDetail(item, canPreviewProofs) {
  const template = getAchievementTemplate(item.category);
  const detailRows = template && Object.keys(item.details || {}).length
    ? template.fields.map(field => `<div><dt>${escapeHtml(field.label)}</dt><dd>${escapeHtml(detailValue(item.details[field.key]))}</dd></div>`).join("")
    : `<div><dt>成果说明</dt><dd>${escapeHtml(item.description || "未设置")}</dd></div><div><dt>成果日期</dt><dd>${escapeHtml(item.achievement_date || "未设置")}</dd></div>`;
  const proofs = Array.isArray(item.proofs) ? item.proofs : [];
  return `
    ${!Object.keys(item.details || {}).length ? '<div class="achievement-legacy-notice"><strong>旧版成果记录</strong><p>该记录尚未包含分类模板明细，以下展示原通用字段。</p></div>' : ""}
    <dl class="achievement-detail-grid">
      <div><dt>成果类别</dt><dd>${escapeHtml(template?.category_label || item.category)}</dd></div>
      <div><dt>成果级别</dt><dd>${escapeHtml(item.level || "不适用")}</dd></div>
      <div><dt>成果日期</dt><dd>${escapeHtml(item.achievement_date || "未设置")}</dd></div>
      <div><dt>公开展示</dt><dd>${item.is_public ? "是" : "否"}</dd></div>
      ${detailRows}
    </dl>
    <section class="achievement-detail-proofs">
      <h3>证明材料 <span>${proofs.length} 份</span></h3>
      ${proofs.length ? `<ul>${proofs.map(proof => `<li><span>${icon("file")}<span><strong>${escapeHtml(proof.name || "未命名附件")}</strong><small>${formatBytes(proof.size || 0)}</small></span></span>${canPreviewProofs ? `<button class="button button-secondary button-small" type="button" data-detail-proof="${escapeHtml(proof.id || proof.stored_name || proof.path)}">${icon("eye")} 预览</button>` : ""}</li>`).join("")}</ul>` : '<p class="muted">没有附件记录。</p>'}
    </section>`;
}

export async function renderCommunity(container) {
  let tab = "resources";
  let resources = [];
  let achievements = [];
  let achievementYears = [];
  let selectedYear = defaultAchievementYear();
  let achievementCategory = "";
  let query = "";
  let resourceType = "";
  let unbindTimeline = () => {};
  let unbindList = () => {};

  container.innerHTML = pageHeader("成果与社区", "维护成长档案，发现比赛、项目和共享资源。") + loadingState();

  async function load() {
    if (tab === "resources") {
      const result = await api(`/api/v1/resources${qs({ page_size: 100, q: query, type: resourceType })}`);
      resources = result.items;
      return;
    }
    if (tab === "mine") {
      const params = { page: 1, page_size: 100, year: selectedYear };
      const [result, years] = await Promise.all([
        api(`/api/v1/achievements${qs(params)}`),
        api("/api/v1/achievements/years"),
      ]);
      const pageCount = Math.ceil(result.total / params.page_size);
      const remainingPages = pageCount > 1
        ? await Promise.all(Array.from({ length: pageCount - 1 }, (_, index) => api(`/api/v1/achievements${qs({ ...params, page: index + 2 })}`)))
        : [];
      achievements = [result, ...remainingPages].flatMap(page => page.items);
      achievementYears = years;
      return;
    }
    const result = await api(`/api/v1/achievements/public/list${qs({ page_size: 100, q: query, category: achievementCategory })}`);
    achievements = result.items;
  }

  function renderLoadError(error) {
    unbindTimeline();
    unbindList();
    container.innerHTML = `
      ${pageHeader("成果与社区", "维护成长档案，发现比赛、项目和共享资源。")}
      <div class="tabs"><button class="tab ${tab === "resources" ? "active" : ""}" data-tab="resources">资源社区</button><button class="tab ${tab === "mine" ? "active" : ""}" data-tab="mine">我的成果</button><button class="tab ${tab === "public" ? "active" : ""}" data-tab="public">成果广场</button></div>
      ${emptyState("加载失败", error?.message || "暂时无法连接服务器。", '<button class="button button-primary" id="retry-community">重新加载</button>')}`;
    bind();
  }

  async function refresh(showLoading = false) {
    if (showLoading) container.innerHTML = loadingState("正在加载成果数据");
    try {
      await load();
      draw();
    } catch (error) {
      renderLoadError(error);
    }
  }

  function visibleAchievements() {
    const normalizedQuery = query.trim().toLocaleLowerCase("zh-CN");
    if (!normalizedQuery || tab !== "mine") return achievements;
    return achievements.filter(item => `${item.title || ""} ${item.description || ""}`.toLocaleLowerCase("zh-CN").includes(normalizedQuery));
  }

  function resourceCards() {
    if (!resources.length) return emptyState("没有找到资源", "调整筛选条件，或发布一条新的社区资源。", '<button class="button button-primary" id="empty-resource">发布资源</button>');
    return `<div class="resource-grid">${resources.map(item => `<article class="resource-card"><div class="resource-card-head"><span class="resource-type">${escapeHtml(RESOURCE_TYPES[item.type] || item.type)}</span>${item.deadline ? `<span class="badge badge-warning">截止 ${formatDate(item.deadline, false)}</span>` : ""}</div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.content || "暂无内容说明")}</p><div class="tag-list" style="margin-top:10px">${item.tags.slice(0, 4).map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div><div class="resource-meta"><span>${icon("eye", 14)} ${item.view_count}</span><span>${icon("heart", 14)} ${item.like_count}</span><div class="resource-actions"><button class="icon-button" data-favorite="${item.id}" aria-label="收藏">${icon("bookmark")}</button><button class="icon-button" data-like="${item.id}" aria-label="点赞">${icon("heart")}</button><button class="button button-secondary button-small" data-resource="${item.id}">查看</button></div></div></article>`).join("")}</div>`;
  }

  function achievementToolbar() {
    return `<div class="toolbar achievement-toolbar">
      <form class="search-box" id="community-search">${icon("search")}<input class="input" name="q" value="${escapeHtml(query)}" placeholder="搜索成果标题"></form>
      ${tab === "public" ? `<select class="select" id="achievement-category"><option value="">全部类别</option>${categoryOptions(achievementCategory)}</select>` : ""}
    </div>`;
  }

  function achievementContent() {
    const items = visibleAchievements();
    if (tab === "mine") {
      const periodLabel = selectedYear ? `${selectedYear} 年` : "全部年份";
      const countLabel = query ? `当前搜索到 ${items.length} 项` : `共 ${items.length} 项`;
      return `${renderAchievementTimeline(achievementYears, selectedYear)}${achievementToolbar()}
        <div class="achievement-period-summary" role="status">
          <span class="stat-icon">${icon("trophy")}</span>
          <span><strong>${periodLabel}成果</strong><small>${countLabel}，已按八大类别归档</small></span>
        </div>
        ${renderAchievementCategoryGroups(items, { editable: true })}`;
    }
    const list = renderAchievementList(items, {
      editable: false,
      emptyTitle: "暂无公开成果",
      emptyDescription: "已审核且公开的成果会显示在这里。",
    });
    return `${achievementToolbar()}<section class="panel achievement-list-panel">${list}</section>`;
  }

  function draw() {
    unbindTimeline();
    unbindList();
    const action = tab === "resources" ? `<button class="button button-primary" id="new-resource">${icon("plus")} 发布资源</button>` : tab === "mine" ? `<button class="button button-primary" id="new-achievement">${icon("plus")} 添加成果</button>` : "";
    container.innerHTML = `
      ${pageHeader("成果与社区", "维护成长档案，发现比赛、项目和共享资源。", action)}
      <div class="tabs"><button class="tab ${tab === "resources" ? "active" : ""}" data-tab="resources">资源社区</button><button class="tab ${tab === "mine" ? "active" : ""}" data-tab="mine">我的成果</button><button class="tab ${tab === "public" ? "active" : ""}" data-tab="public">成果广场</button></div>
      ${tab === "resources" ? `<div class="toolbar"><form class="search-box" id="community-search">${icon("search")}<input class="input" name="q" value="${escapeHtml(query)}" placeholder="搜索比赛、资料、项目"></form><select class="select" id="resource-type" style="width:auto"><option value="">全部类型</option>${Object.entries(RESOURCE_TYPES).map(([value, label]) => `<option value="${value}" ${resourceType === value ? "selected" : ""}>${label}</option>`).join("")}</select></div>${resourceCards()}` : achievementContent()}`;
    bind();
  }

  function resourceModal() {
    showModal({
      title: "发布社区资源", submitText: "发布", size: "wide",
      content: `<div class="form-row"><label class="field"><span>资源类型</span><select class="select" name="type">${Object.entries(RESOURCE_TYPES).map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}</select></label><label class="field"><span>截止时间（可选）</span><input class="input" name="deadline" type="datetime-local"></label></div><label class="field"><span>标题</span><input class="input" name="title" maxlength="200" required></label><label class="field"><span>内容</span><textarea class="textarea" name="content"></textarea></label><div class="form-row"><label class="field"><span>标签</span><input class="input" name="tags" placeholder="AI, 大数据, 创新创业"><small>多个标签用逗号分隔</small></label><label class="field"><span>来源</span><input class="input" name="source" maxlength="200"></label></div>`,
      onSubmit: async data => {
        const body = { type: data.get("type"), title: data.get("title"), content: data.get("content") || null, tags: data.get("tags").split(/[,，]/).map(item => item.trim()).filter(Boolean), deadline: data.get("deadline") ? new Date(data.get("deadline")).toISOString() : null, source: data.get("source") || null };
        await api("/api/v1/resources", { method: "POST", body: JSON.stringify(body) });
        await load(); draw(); toast("资源已发布");
      },
    });
  }

  function achievementModal(item = null, preferredCategory = "") {
    let uploadControl;
    showModal({
      title: item ? "编辑成果" : "添加成果",
      submitText: item ? "保存并重新审核" : "提交审核",
      size: "wide",
      content: `${renderAchievementUpload(item?.proofs || [])}${renderAchievementForm(item)}`,
      onSubmit: async (_data, form) => {
        const result = validateAchievementForm(form);
        if (!result.valid) throw new Error("请检查并补全标记的成果字段");
        if (!uploadControl.validate()) throw new Error("请至少上传1份证明材料");
        const proofs = await uploadControl.uploadAll();
        const body = { ...result.payload, proofs };
        let saved;
        if (item) saved = await api(`/api/v1/achievements/${item.id}`, { method: "PUT", body: JSON.stringify(body) });
        else {
          saved = await api("/api/v1/achievements", { method: "POST", body: JSON.stringify(body) });
          selectedYear = null;
          query = "";
        }
        await load();
        draw();
        toast(item ? "成果已更新并提交审核" : "成果已提交审核");
        if (!item) setTimeout(() => {
          const target = container.querySelector(`[data-achievement-category-group="${CSS.escape(saved.category)}"]`);
          target?.scrollIntoView({ behavior: "smooth", block: "start" });
          target?.classList.add("is-highlighted");
          setTimeout(() => target?.classList.remove("is-highlighted"), 1400);
        }, 0);
      },
    });
    const form = document.querySelector("#modal-root .modal-form");
    bindAchievementForm(form, item);
    if (!item && ACHIEVEMENT_CATEGORIES.includes(preferredCategory)) {
      form.elements.category.value = preferredCategory;
      form.elements.category.dispatchEvent(new Event("change"));
    }
    uploadControl = createAchievementUpload(form.querySelector("[data-achievement-upload]"), { proofs: item?.proofs || [] });
  }

  function openAchievement(item) {
    showModal({
      title: item.title || "成果详情",
      submitText: "关闭",
      size: "wide",
      content: renderAchievementDetail(item, tab === "mine"),
      onSubmit: async () => {},
    });
    document.querySelectorAll("#modal-root [data-detail-proof]").forEach(node => node.addEventListener("click", async () => {
      try { await openAchievementProof(node.dataset.detailProof); }
      catch (error) { toast(error.message, "danger"); }
    }));
  }

  function openResource(item) {
    showModal({ title: item.title, submitText: "关闭", size: "wide", content: `<div class="tag-list">${item.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div><p style="white-space:pre-wrap">${escapeHtml(item.content || "暂无内容")}</p><div class="list-row-meta"><span>来源：${escapeHtml(item.source || "未注明")}</span><span>浏览 ${item.view_count}</span><span>点赞 ${item.like_count}</span>${item.deadline ? `<span>截止 ${formatDate(item.deadline)}</span>` : ""}</div>`, onSubmit: async () => {} });
    api(`/api/v1/resources/${item.id}`).catch(() => {});
  }

  function bind() {
    container.querySelectorAll("[data-tab]").forEach(node => node.addEventListener("click", async () => {
      tab = node.dataset.tab;
      query = "";
      achievementCategory = "";
      if (tab === "mine") selectedYear = defaultAchievementYear();
      await refresh(true);
    }));
    container.querySelector("#retry-community")?.addEventListener("click", () => refresh(true));
    container.querySelector("#new-resource")?.addEventListener("click", resourceModal);
    container.querySelector("#empty-resource")?.addEventListener("click", resourceModal);
    container.querySelector("#new-achievement")?.addEventListener("click", () => achievementModal());
    container.querySelector("#empty-achievement")?.addEventListener("click", () => achievementModal());
    container.querySelectorAll("[data-add-achievement-category]").forEach(node => node.addEventListener("click", () => achievementModal(null, node.dataset.addAchievementCategory)));
    container.querySelector("#community-search")?.addEventListener("submit", async event => {
      event.preventDefault();
      query = String(new FormData(event.currentTarget).get("q") || "").trim();
      if (tab !== "mine") await load();
      draw();
    });
    container.querySelector("#resource-type")?.addEventListener("change", async event => { resourceType = event.target.value; await refresh(); });
    container.querySelector("#achievement-category")?.addEventListener("change", async event => { achievementCategory = event.target.value; await refresh(); });
    container.querySelectorAll("[data-resource]").forEach(node => node.addEventListener("click", () => openResource(resources.find(item => item.id === Number(node.dataset.resource)))));
    container.querySelectorAll("[data-favorite]").forEach(node => node.addEventListener("click", async () => { try { await api(`/api/v1/resources/${node.dataset.favorite}/favorite`, { method: "POST" }); toast("已收藏"); } catch (error) { toast(error.message, "danger"); } }));
    container.querySelectorAll("[data-like]").forEach(node => node.addEventListener("click", async () => { try { await api(`/api/v1/resources/${node.dataset.like}/like`, { method: "POST" }); await load(); draw(); } catch (error) { toast(error.message, "danger"); } }));
    if (tab === "mine") {
      unbindTimeline = bindAchievementTimeline(container, async value => { selectedYear = value; await refresh(true); });
    }
    unbindList = bindAchievementList(container, {
      onView: id => openAchievement(achievements.find(item => item.id === id)),
      onEdit: tab === "mine" ? id => achievementModal(achievements.find(item => item.id === id)) : undefined,
      onDelete: tab === "mine" ? id => confirmAction("确认删除这条成果记录及其证明材料？", async () => { await api(`/api/v1/achievements/${id}`, { method: "DELETE" }); await load(); draw(); toast("成果已删除"); }, "删除") : undefined,
    });
  }

  await refresh();
  return () => {
    unbindTimeline();
    unbindList();
  };
}
