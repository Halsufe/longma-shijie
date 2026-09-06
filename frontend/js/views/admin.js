import { api, download, fetchBlob, qs } from "../api.js";
import { getAchievementTemplate } from "../achievement_templates.js";
import { confirmAction, emptyState, escapeHtml, formatBytes, formatDate, icon, loadingState, pageHeader, showModal, statusBadge, toast } from "../ui.js";
import { renderAdminParty } from "../admin_party.js";

const ROLE_LABELS = { student: "学生", alumni: "校友", teacher: "教师", admin: "管理员" };

function detailValue(value) {
  if (value === null || value === undefined || value === "") return "未填写";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) return value.join("、");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function achievementYear(item) {
  if (item.year) return String(item.year);
  const match = String(item.achievement_date || "").match(/^(\d{4})/);
  return match ? match[1] : "未设置";
}

function renderAchievementDetails(item) {
  const template = getAchievementTemplate(item.category);
  const details = item.details || {};
  const fields = template?.fields || Object.keys(details).map(key => ({ key, label: key }));
  if (!fields.length && item.description) {
    return `<div class="list-row-meta"><span><strong>说明：</strong>${escapeHtml(item.description)}</span></div>`;
  }
  return `<div class="list-row-meta">${fields.map(field => `<span><strong>${escapeHtml(field.label)}：</strong>${escapeHtml(detailValue(details[field.key]))}</span>`).join("")}</div>`;
}

function renderAchievementProofs(item) {
  const proofs = Array.isArray(item.proofs) ? item.proofs : [];
  if (!proofs.length) return '<div class="list-row-meta"><span>暂无证明材料</span></div>';
  return `<div class="list-row-meta">${proofs.map(proof => {
    const fileId = String(proof.stored_name || proof.path || proof.id || "");
    const name = String(proof.name || fileId || "证明材料");
    return `<span><strong>${escapeHtml(name)}</strong> <button class="button button-secondary button-small" type="button" data-proof-preview="${escapeHtml(fileId)}">${icon("eye", 14)} 预览</button> <button class="button button-secondary button-small" type="button" data-proof-download="${escapeHtml(fileId)}" data-proof-name="${escapeHtml(name)}">${icon("download", 14)} 下载</button></span>`;
  }).join("")}</div>`;
}

async function previewAchievementProof(fileId) {
  const url = URL.createObjectURL(await fetchBlob(`/api/v1/achievements/files/${encodeURIComponent(fileId)}`));
  const link = document.createElement("a");
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export async function renderAdmin(container) {
  let tab = "overview";
  let data = null;
  let query = "";
  let roleFilter = "";
  let statusFilter = "";
  let partyCleanup = null;
  let alumniRequests = [];
  container.innerHTML = pageHeader("管理后台", "管理系统用户、内容、能力配置和审计记录。") + loadingState();

  async function load() {
    if (tab === "overview") {
      const [stats, storage, activity] = await Promise.all([api("/api/v1/admin/stats"), api("/api/v1/admin/storage"), api("/api/v1/admin/stats/activity?days=30")]);
      data = { stats, storage, activity };
    } else if (tab === "users") { const results = await Promise.all([api(`/api/v1/admin/users${qs({ page_size: 100, q: query, role: roleFilter, status: statusFilter })}`), api("/api/v1/admin/users/alumni-requests?status=pending")]); data = results[0]; alumniRequests = results[1]; }
    else if (tab === "review") {
      const [achievements, resources] = await Promise.all([api("/api/v1/achievements/admin/all?page_size=100&status=pending"), api("/api/v1/resources/admin/pending?page_size=100")]);
      data = { achievements, resources };
    } else if (tab === "skills") data = await api("/api/v1/admin/skills?include_business=true");
    else if (tab === "audit") data = await api("/api/v1/admin/audit?page_size=100");
    else if (tab === "config") data = await api("/api/v1/admin/config");
    else if (tab === "activity") data = await api("/api/v1/admin/stats/activity?days=30");
    else if (tab === "business") data = await api("/api/v1/admin/stats/business");
    else if (tab === "quota") {
      const [policies, usage, users] = await Promise.all([
        api("/api/v1/admin/chat/quota-policies"),
        api("/api/v1/admin/chat/usage?page_size=100"),
        api("/api/v1/admin/chat/user-quotas").catch(async error => {
          // Keep older workers usable while they are being restarted after a
          // deployment that introduced the aggregate quota endpoint.
          if (error.status !== 404) throw error;
          const legacy = await api("/api/v1/admin/users?page_size=100&status=active");
          return {
            total: legacy.total,
            items: (legacy.items || []).map(user => ({
              user_id: user.id, user_name: user.name, student_no: user.student_no,
              role: user.role, quota: 0, used_tokens: 0,
              pending_reconciliation: 0, remaining_tokens: 0,
            })),
          };
        }),
      ]);
      data = { policies, usage, users: users.items || [], userQuotas: users };
    }
    else if (tab === "party") data = null;
  }

  async function refreshView(showLoading = true) {
    if (showLoading) container.innerHTML = loadingState();
    try {
      await load();
      draw();
    } catch (error) {
      container.innerHTML = `${pageHeader("管理后台", "管理系统用户、内容、能力配置和审计记录。")} ${tabs()} ${emptyState("加载失败", error.message, '<button class="button button-secondary" id="admin-retry">重新加载</button>')}`;
      bind();
    }
  }

  function tabs() {
    const items = [["overview","系统概览"],["users","用户管理"],["review","内容审核"],["party","党建管理"],["skills","Skills"],["activity","活跃趋势"],["business","业务统计"],["quota","对话额度"],["audit","审计日志"],["config","系统配置"]];
    return `<div class="tabs admin-tabs">${items.map(([value,label]) => `<button class="tab ${tab === value ? "active" : ""}" data-tab="${value}">${label}</button>`).join("")}</div>`;
  }

  function overview() {
    const { stats, storage } = data;
    return `<section class="stats-grid"><article class="stat-card"><div class="stat-card-top"><span>总用户</span><span class="stat-icon">${icon("users")}</span></div><strong>${stats.users.total}</strong><small>${stats.users.active} 个活跃账号</small></article><article class="stat-card"><div class="stat-card-top"><span>今日 DAU</span><span class="stat-icon info">${icon("overview")}</span></div><strong>${data.activity?.today_dau ?? 0}</strong><small>按北京时间自然日去重</small></article><article class="stat-card"><div class="stat-card-top"><span>知识文件</span><span class="stat-icon warning">${icon("library")}</span></div><strong>${stats.knowledge.personal_files + stats.knowledge.class_files}</strong><small>${formatBytes(stats.knowledge.total_size_bytes)}</small></article><article class="stat-card"><div class="stat-card-top"><span>作业提交</span><span class="stat-icon danger">${icon("file")}</span></div><strong>${stats.assignments.submissions}</strong><small>${stats.assignments.assignments} 项作业</small></article></section><div class="content-grid"><section class="panel"><div class="panel-header"><div><h2>存储用量</h2><p>按用户统计个人知识库</p></div></div><div class="panel-body">${data.storage.by_user.length ? data.storage.by_user.map(item => `<div class="session-row"><span class="avatar">${escapeHtml((item.name || "用").slice(0,1))}</span><div class="session-row-main"><strong>${escapeHtml(item.name || `用户 #${item.user_id}`)}</strong><span>${item.count} 个文件</span></div><strong>${formatBytes(item.bytes)}</strong></div>`).join("") : emptyState("暂无存储数据", "用户上传文件后会显示用量。")}</div></section><aside class="panel"><div class="panel-header"><div><h2>资源分布</h2><p>当前系统存储结构</p></div></div><div class="panel-body"><div class="metric-row" style="grid-template-columns:1fr 1fr"><div class="metric"><strong>${formatBytes(storage.personal_total_bytes)}</strong><span>个人知识库</span></div><div class="metric"><strong>${formatBytes(storage.class_total_bytes)}</strong><span>班级知识库</span></div><div class="metric"><strong>${stats.skills.skills}</strong><span>Skills</span></div><div class="metric"><strong>${stats.skills.calls}</strong><span>调用次数</span></div></div></div></aside></div>`;
  }

  function users() {
    if (!data.items.length) return emptyState("没有找到用户", "调整搜索词或创建新用户。");
    return `<section class="panel panel-flush"><div class="table-wrap"><table class="data-table"><thead><tr><th>用户</th><th>角色</th><th>状态</th><th>最近活跃</th><th>创建时间</th><th></th></tr></thead><tbody>${data.items.map(user => `<tr><td><div class="table-title"><span class="avatar">${escapeHtml(user.name.slice(0,1))}</span><span><strong>${escapeHtml(user.name)}</strong><span>${escapeHtml(user.student_no)}</span></span></div></td><td>${escapeHtml(ROLE_LABELS[user.role] || user.role)}</td><td>${statusBadge(user.status)}</td><td>${formatDate(user.last_active_at)}</td><td>${formatDate(user.created_at)}</td><td><div class="table-actions"><button class="icon-button" data-edit-user="${user.id}" aria-label="编辑">${icon("edit")}</button><button class="button button-secondary button-small" data-reset="${user.id}">重置密码</button>${user.status === "disabled" ? `<button class="button button-primary button-small" data-enable="${user.id}">启用</button>` : `<button class="button button-danger button-small" data-disable="${user.id}">禁用</button>`}<button class="icon-button danger" data-delete-user="${user.id}" aria-label="删除">${icon("trash")}</button></div></td></tr>`).join("")}</tbody></table></div></section>`;
  }

  function review() {
    const achievements = data.achievements.items;
    const resources = data.resources.items;
    return `<div class="content-grid"><section class="panel"><div class="panel-header"><div><h2>待审核成果</h2><p>${achievements.length} 条待处理</p></div></div><div class="panel-body"><div class="application-list">${achievements.length ? achievements.map(item => {
      const template = getAchievementTemplate(item.category);
      const categoryLabel = template?.category_label || item.category || "未设置";
      const proofCount = Number.isInteger(item.proof_count) ? item.proof_count : (item.proofs || []).length;
      return `<article class="list-row"><span class="quick-item-icon">${icon("trophy")}</span><div class="list-row-main"><h3>${escapeHtml(item.title)}</h3><div class="list-row-meta"><span>${escapeHtml(categoryLabel)}</span><span>用户 #${Number(item.user_id)}</span><span>级别：${escapeHtml(item.level || "不适用")}</span><span>年份：${escapeHtml(achievementYear(item))}</span><span>附件：${proofCount} 份</span></div>${renderAchievementDetails(item)}${renderAchievementProofs(item)}</div><div class="list-row-actions"><button class="button button-primary button-small" data-achievement-approve="${Number(item.id)}">通过</button><button class="button button-danger button-small" data-achievement-reject="${Number(item.id)}">拒绝</button></div></article>`;
    }).join("") : emptyState("没有待审核成果", "所有成果都已处理。")}</div></div></section><section class="panel"><div class="panel-header"><div><h2>待审核资源</h2><p>${resources.length} 条待处理</p></div></div><div class="panel-body"><div class="application-list">${resources.length ? resources.map(item => `<article class="list-row"><span class="quick-item-icon">${icon("file")}</span><div class="list-row-main"><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.content || "暂无说明")}</p><div class="list-row-meta"><span>${escapeHtml(item.type)}</span><span>作者 #${item.author_id}</span></div></div><div class="list-row-actions"><button class="button button-primary button-small" data-resource-approve="${item.id}">通过</button><button class="button button-danger button-small" data-resource-reject="${item.id}">拒绝</button></div></article>`).join("") : emptyState("没有待审核资源", "所有资源都已处理。")}</div></div></section></div>`;
  }

  function skills() {
    return `<section class="panel panel-flush">${data.items.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>Skill</th><th>类别</th><th>触发词</th><th>状态</th><th></th></tr></thead><tbody>${data.items.map(skill => `<tr><td><div class="table-title"><span class="quick-item-icon">${icon("sparkles")}</span><span><strong>${escapeHtml(skill.display_name)}</strong><span>${escapeHtml(skill.description || skill.name)}</span></span></div></td><td>${escapeHtml(skill.category)}</td><td><div class="tag-list">${skill.triggers.map(trigger => `<span class="tag">${escapeHtml(trigger)}</span>`).join("")}</div></td><td>${statusBadge(skill.is_enabled ? "active" : "disabled")}</td><td><button class="button button-secondary button-small" data-skill-edit="${skill.id}">${icon("edit", 14)} 编辑</button><button class="button ${skill.is_enabled ? "button-danger" : "button-primary"} button-small" data-skill-toggle="${skill.id}">${skill.is_enabled ? "停用" : "启用"}</button></td></tr>`).join("")}</tbody></table></div>` : emptyState("没有 Skills", "系统内置 Skill 会在启动时自动初始化。")}</section>`;
  }

  function activity() {
    const items = data.items || [];
    return `<section class="panel"><div class="panel-header"><div><h2>近 ${data.days || 30} 天活跃趋势</h2><p>DAU 按 Asia/Shanghai 自然日去重</p></div><button class="button button-secondary" id="export-activity">${icon("download")} 导出 CSV</button></div><div class="panel-body"><div class="table-wrap"><table class="data-table"><thead><tr><th>日期</th><th>DAU</th></tr></thead><tbody>${items.map(item => `<tr><td>${escapeHtml(item.date)}</td><td><strong>${item.dau}</strong></td></tr>`).join("")}</tbody></table></div></div></section>`;
  }

  function business() {
    const labels = { party: "党建", competition: "竞赛资源", achievements: "成果" };
    const entries = Object.entries(data).filter(([key, item]) => !["filters", "projects"].includes(key) && item && typeof item === "object");
    const details = entries.flatMap(([key, item]) => (item.details || []).map(detail => ({ key, ...detail })));
    return `<section class="panel"><div class="panel-header"><div><h2>业务统计</h2><p>党建、竞赛资源与成果的只读聚合</p></div></div><div class="panel-body"><div class="metric-row">${entries.map(([key, item]) => `<div class="metric"><strong>${Object.values(item).find(value => typeof value === "number") ?? 0}</strong><span>${labels[key] || key}</span><small>${escapeHtml(item.message || "")}</small></div>`).join("")}</div>${details.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>类别</th><th>明细</th></tr></thead><tbody>${details.map(item => `<tr><td>${escapeHtml(labels[item.key] || item.key)}</td><td>${escapeHtml(JSON.stringify(item))}</td></tr>`).join("")}</tbody></table></div>` : ""}</div></section>`;
  }

  function audit() {
    return `<section class="panel panel-flush">${data.items.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>时间</th><th>操作人</th><th>动作</th><th>目标</th><th>结果</th><th>IP</th></tr></thead><tbody>${data.items.map(item => `<tr><td class="nowrap">${formatDate(item.created_at)}</td><td>${escapeHtml(item.operator_name || (item.operator_id ? `#${item.operator_id}` : "系统"))}</td><td><span class="tag">${escapeHtml(item.action)}</span></td><td>${escapeHtml(item.target_type || "-")} ${escapeHtml(item.target_id || "")}</td><td>${statusBadge(item.result === "success" ? "active" : "failed")}</td><td>${escapeHtml(item.ip || "-")}</td></tr>`).join("")}</tbody></table></div>` : emptyState("暂无审计记录", "系统写操作会自动记录在这里。")}</section>`;
  }

  function config() {
    return `<section class="panel"><div class="panel-header"><div><h2>运行时配置</h2><p>数据库持久值优先于环境变量，保存后立即生效</p></div></div><form class="panel-body form-stack" id="config-form"><div class="form-row"><label class="field"><span>班级名称</span><input class="input" name="class_name" value="${escapeHtml(data.class_name)}"></label><label class="field"><span>默认个人配额（MB）</span><input class="input" name="default_quota_mb" type="number" min="1" value="${data.default_quota_mb}"></label></div><div class="form-row"><label class="field"><span>登录失败上限</span><input class="input" name="login_max_attempts" type="number" min="1" value="${data.login_max_attempts}"></label><label class="field"><span>统计窗口（分钟）</span><input class="input" name="login_window_minutes" type="number" min="1" value="${data.login_window_minutes}"></label></div><div class="form-row"><label class="field"><span>产品模型标识</span><input class="input" value="deepseek-v4-flash" disabled><small class="field-hint">内部固定标识，供应商模型由环境变量 AI_MODEL 控制（当前：${escapeHtml(data.ai_model || "deepseek-chat")}）</small></label><label class="field"><span>AI Base URL</span><input class="input" name="ai_base_url" type="url" value="${escapeHtml(data.ai_base_url || "")}"></label></div><div class="form-row"><label class="field"><span>作业提醒时间（小时，逗号分隔）</span><input class="input" name="assignment_reminder_hours" value="${escapeHtml((data.assignment_reminder_hours || []).join(", "))}"></label><label class="field"><span>API Key</span><input class="input" value="${data.ai_api_key_configured ? "已配置" : "未配置"}" disabled></label></div><div><button class="button button-primary" type="submit">保存配置</button></div></form></section>`;
  }

  function quota() {
    const policies = data.policies || [];
    const usage = data.usage || { items: [], settled_tokens: 0, pending_reconciliation: 0 };
    const users = data.users || [];
    const policyCards = policies.map(policy => `<form class="quota-policy-card" data-quota-role="${escapeHtml(policy.role)}"><div class="quota-policy-card-head"><div><strong>${escapeHtml(ROLE_LABELS[policy.role] || policy.role)}</strong><span>${policy.configured ? "已配置" : "未配置"}</span></div>${icon("edit", 16)}</div><label class="field"><span>每日 Token 上限</span><input class="input" name="daily_limit" type="number" min="0" value="${policy.daily_limit}"></label><label class="field"><span>调整原因</span><input class="input" name="reason" placeholder="例如：新学期额度" required></label><button class="button button-secondary" type="submit">保存策略</button></form>`).join("");
    const userRows = users.map(user => {
      const displayName = user.user_name || user.name || `用户 #${user.user_id}`;
      const quotaValue = user.quota ?? 0;
      const used = user.used_tokens ?? 0;
      const pending = user.pending_reconciliation ?? 0;
      const remaining = user.remaining_tokens ?? Math.max(0, quotaValue - used - pending);
      return `<tr><td><div class="table-title"><span class="avatar">${escapeHtml(displayName.slice(0, 1))}</span><span><strong>${escapeHtml(displayName)}</strong><span>${escapeHtml(user.student_no || "")} · ${escapeHtml(ROLE_LABELS[user.role] || user.role)}</span></span></div></td><td><strong>${quotaValue.toLocaleString()}</strong><span class="table-subtext">每日上限</span></td><td>${used.toLocaleString()}</td><td>${remaining.toLocaleString()}</td><td>${pending.toLocaleString()}</td><td><button class="button button-secondary button-small" data-quota-user="${user.user_id}">${icon("edit", 14)} 调整</button></td></tr>`;
    }).join("");
    return `<div class="quota-dashboard"><section class="quota-summary"><div class="quota-summary-item"><span>已结算 Token</span><strong>${Number(usage.settled_tokens || 0).toLocaleString()}</strong></div><div class="quota-summary-item"><span>待对账 Token</span><strong>${Number(usage.pending_reconciliation || 0).toLocaleString()}</strong></div><div class="quota-summary-item"><span>活跃用户</span><strong>${users.length}</strong></div></section><section class="panel quota-policy-panel"><div class="panel-header"><div><h2>角色每日额度</h2><p>产品模型：DeepSeek V4 Flash；额度按自然日重置</p></div></div><div class="quota-policy-grid">${policyCards}</div></section><section class="panel panel-flush quota-users-panel"><div class="panel-header"><div><h2>用户额度与用量</h2><p>${users.length} 个活跃用户 · 用量按北京时间统计</p></div></div>${users.length ? `<div class="table-wrap"><table class="data-table quota-users-table"><thead><tr><th>用户</th><th>额度</th><th>已用</th><th>剩余</th><th>待对账</th><th></th></tr></thead><tbody>${userRows}</tbody></table></div>` : emptyState("暂无活跃用户", "创建用户后可在这里调整个人额度。")}</section></div>`;
  }

  function quotaUserModal(user) {
    showModal({ title: `调整额度 · ${user.user_name || user.name || `用户 #${user.id}`}`, submitText: "保存额度", content: `<p class="modal-copy">个人额度会覆盖角色策略，可设置有效期；留空表示长期有效。</p><label class="field"><span>每日 Token 上限</span><input class="input" name="daily_limit" type="number" min="0" value="${user.quota ?? 0}" required></label><label class="field"><span>有效期至（可选）</span><input class="input" name="valid_until" type="datetime-local"></label><label class="field"><span>调整原因</span><input class="input" name="reason" placeholder="例如：项目冲刺临时增加" required></label>`, onSubmit: async form => { const validUntil = form.get("valid_until"); await api(`/api/v1/admin/users/${user.id}/chat-quota`, { method: "PUT", body: JSON.stringify({ daily_limit: Number(form.get("daily_limit")), valid_until: validUntil ? new Date(validUntil).toISOString() : null, reason: form.get("reason") }) }); await load(); draw(); toast("用户额度已更新"); } });
  }

  function draw() {
    const userActions = tab === "users" ? `<input type="file" id="user-import-file" accept=".csv" hidden><button class="button button-secondary" id="import-users">${icon("upload")} 导入 CSV</button><button class="button button-secondary" id="export-users">${icon("download")} 导出 CSV</button><button class="button button-primary" id="new-user">${icon("plus")} 新建用户</button>` : tab === "activity" ? `<button class="button button-secondary" id="export-activity">${icon("download")} 导出 CSV</button>` : "";
    let content;
    if (tab === "overview") content = overview();
    if (tab === "users") content = `<div class="toolbar"><form class="admin-user-filters" id="user-search"><div class="search-box admin-user-query">${icon("search")}<input class="input" name="q" value="${escapeHtml(query)}" placeholder="搜索学号或姓名"></div><select class="select admin-user-filter" name="role"><option value="">全部角色</option>${Object.entries(ROLE_LABELS).map(([value, label]) => `<option value="${value}" ${roleFilter === value ? "selected" : ""}>${label}</option>`).join("")}</select><select class="select admin-user-filter" name="status"><option value="">全部状态</option><option value="active" ${statusFilter === "active" ? "selected" : ""}>正常</option><option value="disabled" ${statusFilter === "disabled" ? "selected" : ""}>已禁用</option><option value="pending_change" ${statusFilter === "pending_change" ? "selected" : ""}>待改密</option></select></form></div>${users()}`;
    if (tab === "review") content = review();
    if (tab === "skills") content = skills();
    if (tab === "activity") content = activity();
    if (tab === "business") content = business();
    if (tab === "audit") content = audit();
    if (tab === "config") content = config();
    if (tab === "quota") content = quota();
    if (tab === "party") content = '<div id="admin-party-root"></div>';
    container.innerHTML = `${pageHeader("管理后台", "管理系统用户、内容、能力配置和审计记录。", userActions)}${tabs()}${content}`;
    bind();
    if (tab === "party") renderAdminParty(container.querySelector("#admin-party-root")).then(cleanup => { partyCleanup = cleanup; });
  }

  function userModal(user = null) {
    showModal({ title: user ? "编辑用户" : "新建用户", submitText: user ? "保存" : "创建", content: `<label class="field"><span>学号 / 工号</span><input class="input" name="student_no" value="${escapeHtml(user?.student_no || "")}" required></label><label class="field"><span>姓名</span><input class="input" name="name" value="${escapeHtml(user?.name || "")}" required></label><label class="field"><span>角色</span><select class="select" name="role">${Object.entries(ROLE_LABELS).map(([value,label]) => `<option value="${value}" ${user?.role === value ? "selected" : ""}>${label}</option>`).join("")}</select></label>${user ? "" : '<p class="muted">初始密码为 <strong>123456</strong>，用户首次登录后需修改密码。</p>'}`, onSubmit: async form => { const body = Object.fromEntries(form); if (user) await api(`/api/v1/admin/users/${user.id}`, { method: "PUT", body: JSON.stringify(body) }); else await api("/api/v1/admin/users", { method: "POST", body: JSON.stringify(body) }); await load(); draw(); toast(user ? "用户已更新" : "用户已创建，初始密码 123456"); } });
  }

  function skillModal(skill) {
    let modelConfig = {};
    try { modelConfig = skill.model_config_json ? JSON.parse(skill.model_config_json) : {}; } catch { modelConfig = {}; }
    showModal({ title: `编辑 Skill · ${skill.display_name}`, submitText: "保存", size: "wide", content: `<label class="field"><span>展示名</span><input class="input" name="display_name" value="${escapeHtml(skill.display_name)}" required></label><label class="field"><span>说明</span><textarea class="textarea" name="description">${escapeHtml(skill.description || "")}</textarea></label><label class="field"><span>触发词（逗号分隔）</span><input class="input" name="triggers" value="${escapeHtml((skill.triggers || []).join(", "))}"></label><label class="field"><span>模型配置 JSON</span><textarea class="textarea" name="model_config" placeholder='{"model":"...","temperature":0.2,"max_tokens":2000,"top_p":0.9}'>${escapeHtml(JSON.stringify(modelConfig, null, 2))}</textarea></label><label class="field"><span>启用状态</span><select class="select" name="is_enabled"><option value="true" ${skill.is_enabled ? "selected" : ""}>启用</option><option value="false" ${!skill.is_enabled ? "selected" : ""}>停用</option></select></label>`, onSubmit: async form => {
      let parsed = {};
      try { parsed = JSON.parse(form.get("model_config") || "{}"); } catch { throw new Error("模型配置必须是合法 JSON"); }
      await api(`/api/v1/admin/skills/${skill.id}`, { method: "PUT", body: JSON.stringify({ display_name: form.get("display_name"), description: form.get("description") || null, triggers: form.get("triggers").split(/[,，]/).map(value => value.trim()).filter(Boolean), is_enabled: form.get("is_enabled") === "true", model_config_json: JSON.stringify(parsed) }) });
      await load(); draw(); toast("Skill 配置已保存");
    } });
  }

  async function previewImport(file) {
    const form = new FormData(); form.append("file", file);
    const result = await api("/api/v1/admin/users/import/preview", { method: "POST", body: form });
    showModal({ title: "CSV 导入预检", submitText: "确认导入", size: "wide", content: `<div class="metric-row"><div class="metric"><strong>${result.summary.create}</strong><span>新增</span></div><div class="metric"><strong>${result.summary.update}</strong><span>更新</span></div><div class="metric"><strong>${result.summary.restore}</strong><span>恢复</span></div><div class="metric"><strong>${result.summary.error}</strong><span>错误</span></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>行</th><th>学号</th><th>姓名</th><th>角色</th><th>动作</th><th>错误</th></tr></thead><tbody>${result.rows.map(row => `<tr class="${row.action === "error" ? "danger" : ""}"><td>${row.line}</td><td>${escapeHtml(row.student_no)}</td><td>${escapeHtml(row.name)}</td><td>${escapeHtml(ROLE_LABELS[row.role] || row.role)}</td><td>${escapeHtml(row.action)}</td><td>${escapeHtml(row.error || "")}</td></tr>`).join("")}</tbody></table></div>`, onSubmit: async () => {
      if (result.summary.error) throw new Error("请先修正错误行后再导入");
      const confirmForm = new FormData(); confirmForm.append("file", file);
      const confirmed = await api(`/api/v1/admin/users/import/confirm?confirmation_token=${encodeURIComponent(result.confirmation_token)}`, { method: "POST", body: confirmForm });
      await load(); draw(); toast(`导入完成：新增 ${confirmed.created || 0}，更新 ${confirmed.updated || 0}`);
    } });
  }

  function bind() {
    container.querySelectorAll("[data-tab]").forEach(node => node.addEventListener("click", async () => { partyCleanup?.(); partyCleanup = null; tab = node.dataset.tab; query = ""; roleFilter = ""; statusFilter = ""; await refreshView(); }));
    container.querySelector("#admin-retry")?.addEventListener("click", () => refreshView());
    container.querySelector("#user-search")?.addEventListener("submit", async event => { event.preventDefault(); const form = new FormData(event.currentTarget); query = String(form.get("q") || "").trim(); roleFilter = String(form.get("role") || ""); statusFilter = String(form.get("status") || ""); await load(); draw(); });
    container.querySelector("#new-user")?.addEventListener("click", () => userModal());
    container.querySelectorAll("[data-edit-user]").forEach(node => node.addEventListener("click", () => userModal(data.items.find(item => item.id === Number(node.dataset.editUser)))));
    container.querySelectorAll("[data-reset]").forEach(node => node.addEventListener("click", () => showModal({ title: "重置密码", submitText: "重置", content: '<label class="field"><span>新密码（留空使用默认密码 123456）</span><input class="input" name="new_password" type="text" minlength="6" placeholder="123456"></label>', onSubmit: async form => { const result = await api(`/api/v1/admin/users/${node.dataset.reset}/reset-password`, { method: "PUT", body: JSON.stringify({ new_password: form.get("new_password") || null }) }); toast(result.message, "warning"); await load(); draw(); } })));
    container.querySelectorAll("[data-enable]").forEach(node => node.addEventListener("click", async () => { await api(`/api/v1/admin/users/${node.dataset.enable}/enable`, { method: "PUT" }); await load(); draw(); }));
    container.querySelectorAll("[data-disable]").forEach(node => node.addEventListener("click", () => confirmAction("禁用后，该用户当前会话会立即失效。确认继续？", async () => { await api(`/api/v1/admin/users/${node.dataset.disable}/disable`, { method: "PUT" }); await load(); draw(); }, "禁用")));
    container.querySelectorAll("[data-delete-user]").forEach(node => node.addEventListener("click", () => confirmAction("确认软删除这个用户？", async () => { await api(`/api/v1/admin/users/${node.dataset.deleteUser}`, { method: "DELETE" }); await load(); draw(); }, "删除")));
    container.querySelector("#import-users")?.addEventListener("click", () => container.querySelector("#user-import-file").click());
    container.querySelector("#user-import-file")?.addEventListener("change", async event => { const file = event.target.files[0]; if (!file) return; try { await previewImport(file); } catch (error) { toast(error.message, "danger"); } event.target.value = ""; });
    container.querySelector("#export-users")?.addEventListener("click", async () => { try { await download(`/api/v1/admin/users/export${qs({ q: query, role: roleFilter, status: statusFilter })}`, "users.csv"); } catch (error) { toast(error.message, "danger"); } });
    container.querySelectorAll("#export-activity").forEach(node => node.addEventListener("click", async () => { try { await download("/api/v1/admin/stats/activity/export?days=30", "activity.csv"); } catch (error) { toast(error.message, "danger"); } }));
    container.querySelectorAll("[data-proof-preview]").forEach(node => node.addEventListener("click", async () => { try { await previewAchievementProof(node.dataset.proofPreview); } catch (error) { toast(error.message, "danger"); } }));
    container.querySelectorAll("[data-proof-download]").forEach(node => node.addEventListener("click", async () => { try { await download(`/api/v1/achievements/files/${encodeURIComponent(node.dataset.proofDownload)}?download=true`, node.dataset.proofName); } catch (error) { toast(error.message, "danger"); } }));
    [["achievement-approve","achievements","approve"],["achievement-reject","achievements","reject"],["resource-approve","resources","approve"],["resource-reject","resources","reject"]].forEach(([attr,path,action]) => container.querySelectorAll(`[data-${attr}]`).forEach(node => node.addEventListener("click", async () => { await api(`/api/v1/${path}/admin/${node.dataset[attr.replace(/-([a-z])/g, (_,c) => c.toUpperCase())]}/${action}`, { method: "PUT" }); await load(); draw(); toast(action === "approve" ? "审核已通过" : "审核已拒绝"); })));
    container.querySelectorAll("[data-skill-edit]").forEach(node => node.addEventListener("click", () => skillModal(data.items.find(item => item.id === Number(node.dataset.skillEdit)))));
    container.querySelectorAll("[data-skill-toggle]").forEach(node => node.addEventListener("click", async () => { const skill = data.items.find(item => item.id === Number(node.dataset.skillToggle)); await api(`/api/v1/admin/skills/${skill.id}`, { method: "PUT", body: JSON.stringify({ is_enabled: !skill.is_enabled }) }); await load(); draw(); toast(`Skill 已${skill.is_enabled ? "停用" : "启用"}`); }));
    container.querySelector("#config-form")?.addEventListener("submit", async event => { event.preventDefault(); const form = new FormData(event.currentTarget); data = await api("/api/v1/admin/config", { method: "PUT", body: JSON.stringify({ class_name: form.get("class_name"), default_quota_mb: Number(form.get("default_quota_mb")), login_max_attempts: Number(form.get("login_max_attempts")), login_window_minutes: Number(form.get("login_window_minutes")), ai_base_url: form.get("ai_base_url"), assignment_reminder_hours: form.get("assignment_reminder_hours").split(/[,，]/).map(value => Number(value.trim())).filter(Boolean) }) }); draw(); toast("运行时配置已保存"); });
    container.querySelectorAll("[data-quota-role]").forEach(node => node.addEventListener("submit", async event => { event.preventDefault(); const form = new FormData(event.currentTarget); await api(`/api/v1/admin/chat/quota-policies/${node.dataset.quotaRole}`, { method: "PUT", body: JSON.stringify({ daily_limit: Number(form.get("daily_limit")), reason: form.get("reason") }) }); await load(); draw(); toast("额度策略已更新"); }));
    container.querySelectorAll("[data-quota-user]").forEach(node => node.addEventListener("click", () => { const user = (data.users || []).find(item => item.user_id === Number(node.dataset.quotaUser)); if (user) quotaUserModal({ ...user, id: user.user_id }); }));
  }

  await refreshView(false);
  return () => partyCleanup?.();
}
