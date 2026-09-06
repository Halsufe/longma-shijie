import { api, qs } from "../api.js";
import { confirmAction, emptyState, escapeHtml, formatDate, icon, loadingState, pageHeader, showModal, statusBadge, toast } from "../ui.js";
import { renderMentorSelection } from "../mentor_selection.js?v=20260818-workbench";

async function renderLegacyMentorship(container, context) {
  const canApply = false;
  const canManageDirections = ["teacher", "admin"].includes(context.user.role);
  let tab = canManageDirections ? "directions" : "plans";
  let items = [];
  let query = "";

  container.innerHTML = pageHeader("研究方向与计划", "维护研究方向和个人学习计划。") + loadingState();

  async function load() {
    if (tab === "teachers") items = (await api(`/api/v1/teachers/match${qs({ page_size: 100, q: query })}`)).items;
    else if (tab === "sent") items = (await api("/api/v1/applications/mine/sent?page_size=100")).items;
    else if (tab === "received") items = (await api("/api/v1/applications/mine/received?page_size=100")).items;
    else if (tab === "directions") items = (await api("/api/v1/teachers/directions/mine")).items;
    else items = (await api("/api/v1/applications/plans/mine?page_size=100")).items;
  }

  function tabs() {
    return `<div class="tabs">${canApply ? `<button class="tab ${tab === "teachers" ? "active" : ""}" data-tab="teachers">匹配教师</button><button class="tab ${tab === "sent" ? "active" : ""}" data-tab="sent">我的申请</button>` : ""}${canManageDirections ? `<button class="tab ${tab === "directions" ? "active" : ""}" data-tab="directions">研究方向</button>` : ""}<button class="tab ${tab === "plans" ? "active" : ""}" data-tab="plans">学习计划</button></div>`;
  }

  function teacherCards() {
    if (!items.length) return emptyState("暂无匹配教师", "尝试使用研究方向或技能关键词搜索。");
    return `<div class="resource-grid">${items.map(teacher => `<article class="resource-card"><div class="resource-card-head"><span class="avatar">${escapeHtml((teacher.name || "师").slice(0,1))}</span><span class="badge badge-info">${teacher.direction_count} 个方向</span></div><h3>${escapeHtml(teacher.name)}</h3><p>${escapeHtml(teacher.profile?.research || teacher.profile?.field || teacher.profile?.title || "教师暂未填写研究简介")}</p><div class="tag-list" style="margin-top:10px">${(teacher.profile?.skills || teacher.profile?.directions || []).slice(0,4).map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div><div class="resource-meta"><span>${escapeHtml(teacher.student_no)}</span><div class="resource-actions"><button class="button button-primary button-small" data-apply="${teacher.id}">发起交流</button></div></div></article>`).join("")}</div>`;
  }

  function listRows() {
    if (!items.length) return emptyState(tab === "plans" ? "暂无学习计划" : tab === "directions" ? "暂无研究方向" : "暂无交流申请", tab === "plans" ? "创建计划，将目标拆成可完成的行动。" : "新的内容会显示在这里。", tab === "plans" ? '<button class="button button-primary" id="empty-plan">新建计划</button>' : tab === "directions" ? '<button class="button button-primary" id="empty-direction">添加方向</button>' : "");
    return `<div class="${tab === "plans" ? "plan-list" : "application-list"}">${items.map(item => {
      if (tab === "plans") return `<article class="list-row"><button class="check-control ${item.is_completed ? "done" : ""}" data-toggle-plan="${item.id}" aria-label="切换完成状态">${icon("check",14)}</button><div class="list-row-main"><h3 class="${item.is_completed ? "completed-text" : ""}">${escapeHtml(item.title)}</h3><p>${escapeHtml(item.description || "暂无说明")}</p><div class="list-row-meta"><span>${item.items.length} 个步骤</span><span>${item.reminder_at ? `提醒 ${formatDate(item.reminder_at)}` : "未设置提醒"}</span></div></div><div class="list-row-actions"><button class="icon-button" data-edit-plan="${item.id}" aria-label="编辑">${icon("edit")}</button><button class="icon-button danger" data-delete-plan="${item.id}" aria-label="删除">${icon("trash")}</button></div></article>`;
      if (tab === "directions") return `<article class="list-row"><span class="quick-item-icon">${icon("users")}</span><div class="list-row-main"><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.description || "暂无说明")}</p><div class="tag-list" style="margin-top:8px">${item.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div></div><div class="list-row-actions"><button class="icon-button" data-edit-direction="${item.id}" aria-label="编辑">${icon("edit")}</button><button class="icon-button danger" data-delete-direction="${item.id}" aria-label="删除">${icon("trash")}</button></div></article>`;
      return `<article class="list-row"><span class="quick-item-icon">${icon("chat")}</span><div class="list-row-main"><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.message || "暂无附言")}</p><div class="list-row-meta"><span>${formatDate(item.created_at)}</span><span>学生 #${item.student_id}</span><span>教师 #${item.teacher_id}</span></div></div>${statusBadge(item.status)}<div class="list-row-actions">${tab === "received" && item.status === "pending" ? `<button class="button button-primary button-small" data-accept="${item.id}">接受</button><button class="button button-danger button-small" data-reject="${item.id}">拒绝</button>` : ""}${tab === "sent" && item.status === "pending" ? `<button class="icon-button danger" data-cancel="${item.id}" aria-label="取消申请">${icon("trash")}</button>` : ""}</div></article>`;
    }).join("")}</div>`;
  }

  function draw() {
    const action = tab === "plans" ? `<button class="button button-primary" id="new-plan">${icon("plus")} 新建计划</button>` : tab === "directions" ? `<button class="button button-primary" id="new-direction">${icon("plus")} 添加方向</button>` : "";
    container.innerHTML = `${pageHeader("研究方向与计划", "维护研究方向和个人学习计划。", action)}${tabs()}${tab === "teachers" ? `<div class="toolbar"><form class="search-box" id="teacher-search">${icon("search")}<input class="input" name="q" value="${escapeHtml(query)}" placeholder="搜索研究方向、教师姓名或标签"></form></div>${teacherCards()}` : listRows()}`;
    bind();
  }

  function applicationModal(teacher) {
    showModal({ title: `联系 ${teacher.name}`, submitText: "提交申请", content: `<label class="field"><span>申请主题</span><input class="input" name="title" placeholder="例如：咨询大数据竞赛指导" required></label><label class="field"><span>附言</span><textarea class="textarea" name="message" placeholder="说明你的方向、基础和希望交流的问题"></textarea></label>`, onSubmit: async data => { await api("/api/v1/applications", { method: "POST", body: JSON.stringify({ teacher_id: teacher.id, title: data.get("title"), message: data.get("message") || null }) }); toast("交流申请已提交"); } });
  }

  function planModal(item = null) {
    showModal({ title: item ? "编辑学习计划" : "新建学习计划", submitText: item ? "保存" : "创建", size: "wide", content: `<label class="field"><span>计划标题</span><input class="input" name="title" value="${escapeHtml(item?.title || "")}" required></label><label class="field"><span>说明</span><textarea class="textarea" name="description">${escapeHtml(item?.description || "")}</textarea></label><label class="field"><span>行动步骤</span><textarea class="textarea" name="items" placeholder="每行一个步骤">${escapeHtml((item?.items || []).map(value => value.title || value.text || String(value)).join("\n"))}</textarea></label><label class="field"><span>提醒时间</span><input class="input" name="reminder_at" type="datetime-local" value="${item?.reminder_at ? new Date(item.reminder_at).toISOString().slice(0,16) : ""}"></label>`, onSubmit: async data => {
      const body = { title: data.get("title"), description: data.get("description") || null, items: data.get("items").split("\n").map(value => value.trim()).filter(Boolean).map(title => ({ title, completed: false })), reminder_at: data.get("reminder_at") ? new Date(data.get("reminder_at")).toISOString() : null };
      if (item) await api(`/api/v1/applications/plans/${item.id}`, { method: "PUT", body: JSON.stringify(body) }); else await api("/api/v1/applications/plans", { method: "POST", body: JSON.stringify(body) });
      await load(); draw(); toast(item ? "计划已更新" : "计划已创建");
    }});
  }

  function directionModal(item = null) {
    showModal({ title: item ? "编辑研究方向" : "添加研究方向", submitText: "保存", content: `<label class="field"><span>方向名称</span><input class="input" name="title" value="${escapeHtml(item?.title || "")}" required></label><label class="field"><span>方向说明</span><textarea class="textarea" name="description">${escapeHtml(item?.description || "")}</textarea></label><label class="field"><span>标签</span><input class="input" name="tags" value="${escapeHtml((item?.tags || []).join(", "))}" placeholder="机器学习, 数据分析"></label>`, onSubmit: async data => { const body = { title: data.get("title"), description: data.get("description") || null, tags: data.get("tags").split(/[,，]/).map(value => value.trim()).filter(Boolean) }; if (item) await api(`/api/v1/teachers/directions/${item.id}`, { method: "PUT", body: JSON.stringify(body) }); else await api("/api/v1/teachers/directions", { method: "POST", body: JSON.stringify(body) }); await load(); draw(); toast("研究方向已保存"); } });
  }

  function bind() {
    container.querySelectorAll("[data-tab]").forEach(node => node.addEventListener("click", async () => { tab = node.dataset.tab; query = ""; container.innerHTML = loadingState(); await load(); draw(); }));
    container.querySelector("#teacher-search")?.addEventListener("submit", async event => { event.preventDefault(); query = new FormData(event.currentTarget).get("q").trim(); await load(); draw(); });
    container.querySelectorAll("[data-apply]").forEach(node => node.addEventListener("click", () => applicationModal(items.find(item => item.id === Number(node.dataset.apply)))));
    container.querySelector("#new-plan")?.addEventListener("click", () => planModal()); container.querySelector("#empty-plan")?.addEventListener("click", () => planModal());
    container.querySelectorAll("[data-edit-plan]").forEach(node => node.addEventListener("click", () => planModal(items.find(item => item.id === Number(node.dataset.editPlan)))));
    container.querySelectorAll("[data-toggle-plan]").forEach(node => node.addEventListener("click", async () => { const item = items.find(value => value.id === Number(node.dataset.togglePlan)); await api(`/api/v1/applications/plans/${item.id}`, { method: "PUT", body: JSON.stringify({ is_completed: !item.is_completed }) }); await load(); draw(); }));
    container.querySelectorAll("[data-delete-plan]").forEach(node => node.addEventListener("click", () => confirmAction("确认删除这个计划？", async () => { await api(`/api/v1/applications/plans/${node.dataset.deletePlan}`, { method: "DELETE" }); await load(); draw(); }, "删除")));
    container.querySelector("#new-direction")?.addEventListener("click", () => directionModal()); container.querySelector("#empty-direction")?.addEventListener("click", () => directionModal());
    container.querySelectorAll("[data-edit-direction]").forEach(node => node.addEventListener("click", () => directionModal(items.find(item => item.id === Number(node.dataset.editDirection)))));
    container.querySelectorAll("[data-delete-direction]").forEach(node => node.addEventListener("click", () => confirmAction("确认删除这个研究方向？", async () => { await api(`/api/v1/teachers/directions/${node.dataset.deleteDirection}`, { method: "DELETE" }); await load(); draw(); }, "删除")));
    container.querySelectorAll("[data-accept]").forEach(node => node.addEventListener("click", async () => { await api(`/api/v1/applications/${node.dataset.accept}/accept`, { method: "PUT" }); await load(); draw(); toast("申请已接受"); }));
    container.querySelectorAll("[data-reject]").forEach(node => node.addEventListener("click", async () => { await api(`/api/v1/applications/${node.dataset.reject}/reject`, { method: "PUT" }); await load(); draw(); toast("申请已拒绝"); }));
    container.querySelectorAll("[data-cancel]").forEach(node => node.addEventListener("click", () => confirmAction("确认取消这项申请？", async () => { await api(`/api/v1/applications/${node.dataset.cancel}`, { method: "DELETE" }); await load(); draw(); }, "取消申请")));
  }

  try { await load(); draw(); } catch (error) { container.innerHTML = pageHeader("研究方向与计划", "维护研究方向和个人学习计划。") + emptyState("加载失败", error.message); }
}

export async function renderMentorship(container, context) {
  let active = "selection";
  async function draw() {
    container.innerHTML = '<div class="tabs"><button class="tab ' +
      (active === "selection" ? "active" : "") +
      '" data-workspace="selection">导师双选</button><button class="tab ' +
      (active === "support" ? "active" : "") +
      '" data-workspace="support">研究方向与学习计划</button></div><div id="mentorship-workspace"></div>';
    const root = container.querySelector("#mentorship-workspace");
    if (active === "selection") await renderMentorSelection(root, context);
    else await renderLegacyMentorship(root, context);
    container.querySelectorAll("[data-workspace]").forEach(function (node) {
      node.addEventListener("click", async function () {
        active = node.dataset.workspace;
        await draw();
      });
    });
  }
  await draw();
}
