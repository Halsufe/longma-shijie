import { api, download, qs } from "./api.js";
import { confirmAction, emptyState, escapeHtml, formatBytes, formatDate, icon, loadingState, showModal, toast } from "./ui.js";

const PARTY_TYPES = ["正式党员", "预备党员", "入党积极分子"];
const APPLY_STATUSES = ["递交申请", "确定为积极分子", "列为发展对象", "接受为预备党员", "转为正式党员", "停止发展"];
const CATEGORIES = ["组织生活会", "主题党日", "理论学习", "志愿公益", "发展工作", "民主评议", "专题教育", "其他", "主题团日", "团学实践", "团组织建设", "其他团学"];
const TARGET_ROLES = ["全体党员", "党员与积极分子", "预备党员与积极分子", "全体团员", "党员与团员", "全体学生", "群众", "指定人员"];
const ACTIVITY_STATUSES = { draft: "草稿", published: "已发布", ongoing: "进行中", finished: "已结束", archived: "已归档" };
const MATERIAL_TYPES = ["申请书", "思想汇报", "政审材料", "考察材料", "其他"];

function arrayOf(payload, ...keys) {
  if (Array.isArray(payload)) return payload;
  for (const key of keys) if (Array.isArray(payload?.[key])) return payload[key];
  return [];
}

function partyOf(member) {
  return member?.party || member?.party_profile || member?.profile || member || {};
}

function memberId(member) {
  return Number(member?.user_id || member?.user?.id || member?.id);
}

function memberName(member) {
  return member?.name || member?.user_name || member?.user?.name || `用户 #${memberId(member)}`;
}

function optionList(values, selected = "") {
  return values.map(value => `<option value="${escapeHtml(value)}" ${selected === value ? "selected" : ""}>${escapeHtml(value)}</option>`).join("");
}

function activityBadge(status) {
  const tone = { draft: "muted", published: "success", ongoing: "info", finished: "warning", archived: "muted" }[status] || "muted";
  return `<span class="badge badge-${tone}">${escapeHtml(ACTIVITY_STATUSES[status] || status || "未知")}</span>`;
}

function jsonList(value) {
  if (Array.isArray(value)) return value;
  if (typeof value === "string") {
    try { return jsonList(JSON.parse(value)); } catch { return value.split(/[,，]/).map(item => item.trim()).filter(Boolean); }
  }
  return [];
}

function listInput(value) {
  return jsonList(value).map(item => typeof item === "object" ? (item.name || item.original_name || item.id || "") : item).filter(Boolean).join(", ");
}

function datetimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function isoOrNull(value) {
  return value ? new Date(value).toISOString() : null;
}

function numberOrNull(value) {
  return value === "" || value === null ? null : Number(value);
}

function objectEntries(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  return Object.entries(value);
}

function metricValue(data, paths, fallback = 0) {
  for (const path of paths) {
    let value = data;
    for (const part of path.split(".")) value = value?.[part];
    if (value !== undefined && value !== null && typeof value !== "object") return value;
  }
  return fallback;
}

function percent(value) {
  const number = Number(value || 0);
  return `${number <= 1 && number >= 0 ? (number * 100).toFixed(1) : number.toFixed(1)}%`;
}

function saveCsv(content, filename) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export async function renderAdminParty(container) {
  let section = "members";
  let members = [];
  let activities = [];
  let stats = {};
  let reviews = [];
  let politicalRoster = [];
  let politicalMaterials = [];
  let memberFilters = { q: "", class_name: "", party_type: "", apply_status: "" };
  let activityFilters = { status: "", category: "", year: "" };
  let statsFilters = { class_name: "", grade: "", year: "", category: "", political_status: "" };
  let reviewFilters = { status: "pending", to_status: "" };
  let rosterFilters = { q: "", political_status: "", class_name: "", grade: "" };
  let active = true;

  async function load() {
    if (section === "members") {
      const result = await api(`/api/v1/party/members${qs({ page_size: 100, ...memberFilters })}`);
      members = arrayOf(result, "items", "members");
    } else if (section === "activities" || section === "archives") {
      const filters = section === "archives" ? { page_size: 100, status: activityFilters.status || undefined, category: activityFilters.category, year: activityFilters.year } : { page_size: 100, ...activityFilters };
      const result = await api(`/api/v1/party/activities${qs(filters)}`);
      activities = arrayOf(result, "items", "activities");
      if (section === "archives" && !activityFilters.status) activities = activities.filter(item => ["finished", "archived"].includes(item.status));
    } else if (section === "stats") {
      stats = await api(`/api/v1/party/stats${qs(statsFilters)}`);
    } else if (section === "political") {
      const result = await api(`/api/v1/party/political-status/reviews${qs({ page_size: 100, ...reviewFilters })}`);
      reviews = arrayOf(result, "items", "reviews");
    } else if (section === "roster") {
      const result = await api(`/api/v1/party/political-status/roster${qs({ page_size: 100, ...rosterFilters })}`);
      politicalRoster = arrayOf(result, "items", "users", "roster");
    } else if (section === "learning-materials") {
      const result = await api("/api/v1/party/learning-materials");
      politicalMaterials = arrayOf(result, "items", "materials");
    }
  }

  function navigation() {
    const items = [["members", "党员档案"], ["roster", "政治面貌名册"], ["political", "政治面貌审核"], ["activities", "活动管理"], ["learning-materials", "政治学习资料"], ["stats", "党建统计"], ["archives", "工作档案"]];
    return `<div class="segmented party-admin-nav">${items.map(([value, label]) => `<button class="segment ${section === value ? "active" : ""}" type="button" data-party-section="${value}">${label}</button>`).join("")}</div>`;
  }

  function memberTable() {
    if (!members.length) return emptyState("没有党员档案", "调整筛选条件，或新增一条党员身份记录。", '<button class="button button-primary" id="party-empty-member">新增党员</button>');
    return `<section class="panel panel-flush"><div class="table-wrap"><table class="data-table party-table"><thead><tr><th>成员</th><th>党员类型</th><th>发展阶段</th><th>班级</th><th>入党时间</th><th></th></tr></thead><tbody>${members.map(member => {
      const party = partyOf(member);
      const id = memberId(member);
      const name = memberName(member);
      return `<tr><td><div class="table-title"><span class="avatar">${escapeHtml((name || "党").slice(0, 1))}</span><span><strong>${escapeHtml(name)}</strong><span>${escapeHtml(member.student_no || member.user?.student_no || `ID ${id}`)}</span></span></div></td><td>${escapeHtml(party.party_type || "-")}</td><td>${escapeHtml(party.apply_status || "-")}</td><td>${escapeHtml(party.class_name || "-")}</td><td>${escapeHtml(party.party_join_date || party.full_date || "-")}</td><td><div class="table-actions"><button class="icon-button" type="button" data-member-edit="${id}" aria-label="编辑党员档案">${icon("edit")}</button><button class="button button-secondary button-small" type="button" data-member-status="${id}">阶段流转</button><button class="button button-secondary button-small" type="button" data-member-material="${id}">${icon("upload", 14)} 材料</button><button class="icon-button danger" type="button" data-member-delete="${id}" aria-label="移除党员档案">${icon("trash")}</button></div></td></tr>`;
    }).join("")}</tbody></table></div></section>`;
  }

  function membersView() {
    return `<div class="party-admin-heading"><div><h2>党员档案</h2><p>维护身份、发展时间轴和涉敏材料。</p></div><div class="page-actions"><input id="party-member-import-file" type="file" accept=".csv,text/csv" hidden><button class="button button-secondary" id="party-member-import">${icon("upload")} 导入 CSV</button><button class="button button-primary" id="party-member-new">${icon("plus")} 新增党员</button></div></div>
      <form class="toolbar party-admin-filter" id="party-member-filter"><input class="input" name="q" value="${escapeHtml(memberFilters.q)}" placeholder="姓名、学号或用户 ID"><input class="input" name="class_name" value="${escapeHtml(memberFilters.class_name)}" placeholder="班级"><select class="select" name="party_type"><option value="">全部类型</option>${optionList(PARTY_TYPES, memberFilters.party_type)}</select><select class="select" name="apply_status"><option value="">全部阶段</option>${optionList(APPLY_STATUSES, memberFilters.apply_status)}</select><button class="button button-secondary" type="submit">${icon("search")} 筛选</button></form>${memberTable()}`;
  }

  function politicalReviewsView() {
    return `<div class="party-admin-heading"><div><h2>政治面貌审核</h2><p>审核学生提交的团员或群众身份变更。</p></div></div><form class="toolbar party-admin-filter" id="party-review-filter"><select class="select" name="status"><option value="pending">待审核</option><option value="approved">已通过</option><option value="rejected">已拒绝</option><option value="">全部状态</option></select><select class="select" name="to_status"><option value="">全部政治面貌</option><option value="共青团员">共青团员</option><option value="群众">群众</option></select><button class="button button-secondary" type="submit">${icon("search")} 筛选</button></form><section class="panel panel-flush"><div class="table-wrap"><table class="data-table party-table"><thead><tr><th>学生</th><th>原面貌</th><th>申请面貌</th><th>说明</th><th>状态</th><th></th></tr></thead><tbody>${reviews.length ? reviews.map(item => `<tr><td><strong>${escapeHtml(item.user_name || `用户 #${item.user_id}`)}</strong><br><small>${escapeHtml(item.student_no || "-")}</small></td><td>${escapeHtml(item.from_status)}</td><td>${escapeHtml(item.to_status)}</td><td>${escapeHtml(item.remark || "-")}</td><td>${escapeHtml(item.status)}</td><td>${item.status === "pending" ? `<div class="table-actions"><button class="button button-primary button-small" data-review-approve="${item.id}">通过</button><button class="button button-secondary button-small" data-review-reject="${item.id}">拒绝</button></div>` : ""}</td></tr>`).join("") : '<tr><td colspan="6" class="muted">暂无申请记录。</td></tr>'}</tbody></table></div></section>`;
  }

  function politicalRosterView() {
    const statusLabel = item => item.latest_review ? `${item.latest_review.to_status} · ${item.latest_review.status === "pending" ? "待审核" : item.latest_review.status === "approved" ? "已通过" : "已拒绝"}` : "无申请记录";
    return `<div class="party-admin-heading"><div><h2>政治面貌名册</h2><p>查看全体学生的党员、团员和群众身份。</p></div></div><form class="toolbar party-admin-filter" id="party-roster-filter"><input class="input" name="q" value="${escapeHtml(rosterFilters.q)}" placeholder="姓名或学号"><select class="select" name="political_status"><option value="">全部政治面貌</option><option value="中共党员" ${rosterFilters.political_status === "中共党员" ? "selected" : ""}>中共党员</option><option value="预备党员" ${rosterFilters.political_status === "预备党员" ? "selected" : ""}>预备党员</option><option value="入党积极分子" ${rosterFilters.political_status === "入党积极分子" ? "selected" : ""}>入党积极分子</option><option value="共青团员" ${rosterFilters.political_status === "共青团员" ? "selected" : ""}>共青团员</option><option value="群众" ${rosterFilters.political_status === "群众" ? "selected" : ""}>群众</option></select><input class="input" name="class_name" value="${escapeHtml(rosterFilters.class_name)}" placeholder="班级"><input class="input" name="grade" value="${escapeHtml(rosterFilters.grade)}" placeholder="年级"><button class="button button-secondary" type="submit">${icon("search")} 筛选</button></form><section class="panel panel-flush"><div class="table-wrap"><table class="data-table party-table"><thead><tr><th>学生</th><th>政治面貌</th><th>党员档案</th><th>班级</th><th>年级</th><th>最近申请</th></tr></thead><tbody>${politicalRoster.length ? politicalRoster.map(item => `<tr><td><div class="table-title"><span class="avatar">${escapeHtml((item.name || "学").slice(0, 1))}</span><span><strong>${escapeHtml(item.name || "未命名")}</strong><span>${escapeHtml(item.student_no || `ID ${item.user_id}`)}</span></span></div></td><td><span class="badge badge-info">${escapeHtml(item.political_status || "群众")}</span></td><td>${escapeHtml(item.party_type || "非党员档案")}${item.apply_status ? `<br><small>${escapeHtml(item.apply_status)}</small>` : ""}</td><td>${escapeHtml(item.class_name || "未设置")}</td><td>${escapeHtml(item.grade || "未设置")}</td><td>${escapeHtml(statusLabel(item))}</td></tr>`).join("") : '<tr><td colspan="6" class="muted">暂无匹配学生。</td></tr>'}</tbody></table></div></section>`;
  }

  function politicalMaterialsView() {
    return `<div class="party-admin-heading"><div><h2>政治学习资料</h2><p>发布后按政治面貌或指定人员可见。</p></div><button class="button button-primary" id="political-material-new">${icon("plus")} 新增资料</button></div><section class="panel panel-flush"><div class="table-wrap"><table class="data-table party-table"><thead><tr><th>标题</th><th>适用对象</th><th>附件</th><th>状态</th><th></th></tr></thead><tbody>${politicalMaterials.length ? politicalMaterials.map(item => `<tr><td><strong>${escapeHtml(item.title)}</strong><br><small>${escapeHtml(item.description || "")}</small></td><td>${escapeHtml((item.applicable_roles || []).join("、") || "未指定")}</td><td>${Number(item.attachments?.length || 0)}</td><td>${escapeHtml(item.status)}</td><td><div class="table-actions"><button class="icon-button" data-political-material-edit="${item.id}" aria-label="编辑资料">${icon("edit")}</button><button class="button button-secondary button-small" data-political-material-upload="${item.id}">${icon("upload", 14)} 附件</button><button class="icon-button danger" data-political-material-delete="${item.id}" aria-label="删除资料">${icon("trash")}</button></div></td></tr>`).join("") : '<tr><td colspan="5" class="muted">暂无政治学习资料。</td></tr>'}</tbody></table></div></section>`;
  }

  function activityTable(archiveOnly = false) {
    if (!activities.length) return emptyState(archiveOnly ? "暂无工作档案" : "暂无党建活动", archiveOnly ? "已结束或归档的活动会显示在这里。" : "创建活动后可发布通知并管理参与情况。");
    return `<section class="panel panel-flush"><div class="table-wrap"><table class="data-table party-table"><thead><tr><th>活动</th><th>类别</th><th>时间</th><th>对象</th><th>状态</th><th></th></tr></thead><tbody>${activities.map(activity => `<tr><td><div class="table-title"><span class="quick-item-icon">${icon("flag")}</span><span><strong>${escapeHtml(activity.title || "未命名活动")}</strong><span>${escapeHtml(activity.location || "地点待定")}</span></span></div></td><td>${escapeHtml(activity.category || "其他")}</td><td class="nowrap">${escapeHtml(formatDate(activity.start_at))}</td><td>${escapeHtml(activity.target_roles || "-")}</td><td>${activityBadge(activity.status)}</td><td><div class="table-actions">${archiveOnly ? `<button class="button button-secondary button-small" data-activity-archive="${Number(activity.id)}">${icon("eye", 14)} 查看档案</button>` : activityActions(activity)}</div></td></tr>`).join("")}</tbody></table></div></section>`;
  }

  function activityActions(activity) {
    const id = Number(activity.id);
    const next = { published: "ongoing", ongoing: "finished", finished: "archived" }[activity.status];
    return `<button class="icon-button" data-activity-edit="${id}" aria-label="编辑活动">${icon("edit")}</button>${activity.status === "draft" ? `<button class="button button-primary button-small" data-activity-publish="${id}">发布</button>` : ""}${next ? `<button class="button button-secondary button-small" data-activity-status="${id}" data-next-status="${next}">${escapeHtml(ACTIVITY_STATUSES[next])}</button>` : ""}${["ongoing", "finished"].includes(activity.status) ? `<button class="button button-secondary button-small" data-activity-summary="${id}">填写总结</button>` : ""}${["finished", "archived"].includes(activity.status) ? `<button class="button button-secondary button-small" data-activity-archive="${id}">${icon("eye", 14)} 档案</button>` : ""}<button class="icon-button danger" data-activity-delete="${id}" aria-label="删除活动">${icon("trash")}</button>`;
  }

  function activityFilter() {
    return `<form class="toolbar party-admin-filter" id="party-activity-filter"><select class="select" name="status"><option value="">全部状态</option>${Object.entries(ACTIVITY_STATUSES).map(([value, label]) => `<option value="${value}" ${activityFilters.status === value ? "selected" : ""}>${label}</option>`).join("")}</select><select class="select" name="category"><option value="">全部类别</option>${optionList(CATEGORIES, activityFilters.category)}</select><input class="input" name="year" type="number" min="2000" max="2100" value="${escapeHtml(activityFilters.year)}" placeholder="年份"><button class="button button-secondary" type="submit">${icon("search")} 筛选</button></form>`;
  }

  function activitiesView() {
    return `<div class="party-admin-heading"><div><h2>活动管理</h2><p>创建、发布、推进状态并完成活动归档。</p></div><button class="button button-primary" id="party-activity-new">${icon("plus")} 创建活动</button></div>${activityFilter()}${activityTable()}`;
  }

  function distribution(title, value) {
    const entries = Array.isArray(value) ? value.map(item => [item.label || item.name || item.key || item.party_type || item.class_name || item.apply_status || "其他", item.count ?? item.value ?? 0]) : objectEntries(value);
    return `<section class="panel"><div class="panel-header"><div><h2>${escapeHtml(title)}</h2><p>当前筛选口径</p></div></div><div class="panel-body party-stat-list">${entries.length ? entries.map(([label, count]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(count)}</strong></div>`).join("") : '<p class="muted">暂无分组数据。</p>'}</div></section>`;
  }

  function statsView() {
    const memberGroups = stats.member_counts?.by_party_type || stats.members?.by_party_type || stats.party_type_counts;
    const classGroups = stats.member_counts?.by_class || stats.members?.by_class || stats.class_distribution;
    const development = stats.development?.by_status || stats.apply_status_counts || stats.development_counts;
    const derivedTotal = (Array.isArray(memberGroups) ? memberGroups.map(item => item.count ?? item.value ?? 0) : objectEntries(memberGroups).map(([, value]) => value)).reduce((sum, value) => sum + Number(value || 0), 0);
    const total = metricValue(stats, ["member_counts.total", "members.total", "total_members", "member_total"], derivedTotal);
    const participation = metricValue(stats, ["participation.participation_rate", "activity_participation.participation_rate", "participation_rate"]);
    const materials = metricValue(stats, ["materials.total", "material_uploads.total", "total_materials", "material_count"]);
    const annualFull = metricValue(stats, ["development.annual_full_count", "development.annual_conversions", "annual_full_count"]);
    const politicalCounts = stats.political_counts?.by_status || [];
    const leagueRate = stats.league_participation?.participation_rate || 0;
    const politicalMaterialTotal = stats.political_materials?.total || 0;
    return `<div class="party-admin-heading"><div><h2>党建统计</h2><p>按班级、年级、年份和活动类别查看核心指标。</p></div><div class="page-actions"><select class="select" id="party-export-type"><option value="stats">统计汇总</option><option value="members">党员名册</option><option value="participants">参与名单</option></select><button class="button button-secondary" id="party-export">${icon("download")} 导出 CSV</button></div></div>
      <form class="toolbar party-admin-filter" id="party-stats-filter"><input class="input" name="class_name" value="${escapeHtml(statsFilters.class_name)}" placeholder="班级"><input class="input" name="grade" value="${escapeHtml(statsFilters.grade)}" placeholder="年级"><input class="input" name="year" type="number" min="2000" max="2100" value="${escapeHtml(statsFilters.year)}" placeholder="年份"><select class="select" name="category"><option value="">全部活动类别</option>${optionList(CATEGORIES, statsFilters.category)}</select><select class="select" name="political_status"><option value="">全部政治面貌</option><option value="中共党员">中共党员</option><option value="预备党员">预备党员</option><option value="入党积极分子">入党积极分子</option><option value="共青团员">共青团员</option><option value="群众">群众</option></select><button class="button button-secondary" type="submit">${icon("search")} 应用筛选</button></form>
      <section class="stats-grid party-stats-grid"><article class="stat-card"><div class="stat-card-top"><span>党员档案</span><span class="stat-icon">${icon("users")}</span></div><strong>${escapeHtml(total)}</strong><small>当前名册人数</small></article><article class="stat-card"><div class="stat-card-top"><span>活动参与率</span><span class="stat-icon info">${icon("check")}</span></div><strong>${percent(participation)}</strong><small>签到人数 / 应参加人数</small></article><article class="stat-card"><div class="stat-card-top"><span>材料上传量</span><span class="stat-icon warning">${icon("file")}</span></div><strong>${escapeHtml(materials)}</strong><small>学习及发展材料</small></article><article class="stat-card"><div class="stat-card-top"><span>年度转正</span><span class="stat-icon danger">${icon("flag")}</span></div><strong>${escapeHtml(annualFull)}</strong><small>正式党员新增人数</small></article></section>
      <div class="party-stat-panels">${distribution("党员类型", memberGroups)}${distribution("政治面貌分布", politicalCounts)}${distribution("班级分布", classGroups)}${distribution("发展阶段", development)}${distribution("团学活动参与率", [["签到参与率", percent(leagueRate)]])}${distribution("政治学习资料", [["资料数量", politicalMaterialTotal]])}</div>`;
  }

  function archivesView() {
    return `<div class="party-admin-heading"><div><h2>工作档案</h2><p>查看活动材料、应参加名单、报名签到和总结。</p></div></div>${activityFilter()}${activityTable(true)}`;
  }

  function draw() {
    if (!active) return;
    const view = section === "members" ? membersView() : section === "roster" ? politicalRosterView() : section === "political" ? politicalReviewsView() : section === "activities" ? activitiesView() : section === "learning-materials" ? politicalMaterialsView() : section === "stats" ? statsView() : archivesView();
    container.innerHTML = `<div class="party-admin-shell">${navigation()}${view}</div>`;
    bind();
  }

  function memberFields(member = null) {
    const party = partyOf(member);
    const identityField = member
      ? `<label class="field"><span>学号</span><input class="input" value="${escapeHtml(member.student_no || "")}" readonly></label>`
      : `<label class="field"><span>学号</span><input class="input" name="student_no" type="text" inputmode="numeric" autocomplete="off" placeholder="请输入已存在的学生学号" required></label>`;
    return `<div class="form-row">${identityField}<label class="field"><span>党员类型</span><select class="select" name="party_type" required><option value="">请选择</option>${optionList(PARTY_TYPES, party.party_type)}</select></label></div><div class="form-row"><label class="field"><span>申请状态</span><select class="select" name="apply_status" required>${optionList(APPLY_STATUSES, party.apply_status)}</select></label><label class="field"><span>支部归属</span><input class="input" name="branch_name" value="${escapeHtml(party.branch_name || "大数据党支部")}" required></label></div><div class="form-row"><label class="field"><span>班级</span><input class="input" name="class_name" value="${escapeHtml(party.class_name || "")}" required></label><label class="field"><span>年级</span><input class="input" name="grade" value="${escapeHtml(party.grade || "")}" required></label></div><div class="party-date-fields">${[["apply_date", "递交申请"], ["activist_date", "确定积极分子"], ["target_date", "列为发展对象"], ["probation_date", "接受为预备党员"], ["full_date", "转为正式党员"], ["party_join_date", "入党时间"]].map(([name, label]) => `<label class="field"><span>${label}</span><input class="input" name="${name}" type="month" value="${escapeHtml(party[name] || "")}"></label>`).join("")}</div><div class="form-row"><label class="field"><span>介绍人</span><input class="input" name="introducer_names" value="${escapeHtml(party.introducer_names || "")}"></label><label class="field"><span>培养联系人</span><input class="input" name="mentor_names" value="${escapeHtml(party.mentor_names || "")}"></label></div><label class="field"><span>停止发展原因</span><input class="input" name="stop_reason" value="${escapeHtml(party.stop_reason || "")}"></label><label class="field"><span>备注</span><textarea class="textarea" name="remark">${escapeHtml(party.remark || "")}</textarea></label>`;
  }

  function memberPayload(form) {
    const payload = Object.fromEntries(form);
    if (payload.user_id) payload.user_id = Number(payload.user_id);
    if (payload.student_no) payload.student_no = String(payload.student_no).trim();
    // Date fields are string-based in the party profile schema. Keep blank
    // dates as empty strings so backend validation can return the stage-specific
    // required-field message instead of a Pydantic null/type error.
    for (const key of ["apply_date", "activist_date", "target_date", "probation_date", "full_date", "party_join_date"]) if (!payload[key]) payload[key] = "";
    for (const key of ["introducer_names", "mentor_names", "stop_reason", "remark"]) if (!payload[key]) payload[key] = null;
    return payload;
  }

  function memberModal(member = null) {
    showModal({ title: member ? "编辑党员档案" : "新增党员档案", submitText: member ? "保存" : "创建", size: "wide", content: memberFields(member), onSubmit: async form => {
      const payload = memberPayload(form);
      const userId = memberId(member);
      if (member) delete payload.user_id;
      await api(member ? `/api/v1/party/members/${userId}` : "/api/v1/party/members", { method: member ? "PUT" : "POST", body: JSON.stringify(payload) });
      await load(); draw(); toast(member ? "党员档案已更新" : "党员档案已创建");
    } });
  }

  function statusModal(member) {
    const party = partyOf(member);
    const userId = memberId(member);
    showModal({ title: "发展阶段流转", submitText: "确认流转", content: `<label class="field"><span>新阶段</span><select class="select" name="apply_status" required>${optionList(APPLY_STATUSES, party.apply_status)}</select></label><label class="field"><span>阶段日期</span><input class="input" name="effective_date" type="month"></label><label class="field"><span>停止发展原因</span><input class="input" name="stop_reason" value="${escapeHtml(party.stop_reason || "")}"></label>`, onSubmit: async form => { const applyStatus = String(form.get("apply_status")); const effectiveDate = String(form.get("effective_date") || ""); if (applyStatus !== "停止发展" && !effectiveDate) throw new Error("请选择阶段日期"); const payload = { apply_status: applyStatus, effective_date: effectiveDate || null, stop_reason: form.get("stop_reason") || null }; await api(`/api/v1/party/members/${userId}/status`, { method: "PUT", body: JSON.stringify(payload) }); await load(); draw(); toast("发展阶段已更新"); } });
  }

  async function materialModal(userId) {
    let materials = [];
    try { const result = await api(`/api/v1/party/members/${userId}/materials`); materials = arrayOf(result, "items", "materials"); }
    catch (error) { toast(error.message, "danger"); }
    showModal({ title: "党员发展材料", submitText: "上传", content: `<section class="party-materials-current"><h3>已有材料</h3>${materials.length ? materials.map(item => `<article><span class="quick-item-icon">${icon("file", 16)}</span><div><strong>${escapeHtml(item.title || item.original_name || "未命名材料")}</strong><span>${escapeHtml(item.material_type || "其他")} · ${formatBytes(Number(item.size || 0))} · ${escapeHtml(formatDate(item.uploaded_at, false))}</span></div></article>`).join("") : '<p class="muted">暂无发展材料。</p>'}</section><input type="hidden" name="user_id" value="${userId}"><label class="field"><span>材料类型</span><select class="select" name="material_type">${optionList(MATERIAL_TYPES)}</select></label><label class="field"><span>材料名称</span><input class="input" name="title" maxlength="200" required></label><label class="field"><span>文件</span><input class="input" name="file" type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" required><small>PDF/JPG/PNG，单文件不超过 20MB</small></label>`, onSubmit: async form => { const file = form.get("file"); const extensionOk = /\.(pdf|jpe?g|png)$/i.test(file?.name || ""); if (!file || !extensionOk) throw new Error("仅支持 PDF、JPG、PNG 文件"); if (file.size > 20 * 1024 * 1024) throw new Error("单文件不能超过 20MB"); await api("/api/v1/party/materials", { method: "POST", body: form }); toast("发展材料已上传"); } });
  }

  function activityModal(activity = null) {
    showModal({ title: activity ? "编辑党建活动" : "创建党建活动", submitText: activity ? "保存" : "创建", size: "wide", content: `<label class="field"><span>活动标题</span><input class="input" name="title" maxlength="200" value="${escapeHtml(activity?.title || "")}" required></label><div class="form-row"><label class="field"><span>活动类别</span><select class="select" name="category">${optionList(CATEGORIES, activity?.category)}</select></label><label class="field"><span>地点</span><input class="input" name="location" maxlength="200" value="${escapeHtml(activity?.location || "")}" required></label></div><label class="field"><span>通知正文</span><textarea class="textarea" name="content" required>${escapeHtml(activity?.content || "")}</textarea></label><div class="party-date-fields"><label class="field"><span>开始时间</span><input class="input" name="start_at" type="datetime-local" value="${datetimeLocal(activity?.start_at)}" required></label><label class="field"><span>结束时间</span><input class="input" name="end_at" type="datetime-local" value="${datetimeLocal(activity?.end_at)}" required></label><label class="field"><span>报名截止</span><input class="input" name="registration_deadline" type="datetime-local" value="${datetimeLocal(activity?.registration_deadline)}"></label></div><div class="form-row"><label class="field"><span>参加对象</span><select class="select" name="target_roles">${optionList(TARGET_ROLES, activity?.target_roles)}</select></label><label class="field"><span>人数上限</span><input class="input" name="max_participants" type="number" min="1" value="${escapeHtml(activity?.max_participants || "")}"></label></div><label class="field"><span>指定人员用户 ID</span><input class="input" name="target_member_ids" value="${escapeHtml(listInput(activity?.target_member_ids || activity?.target_member_ids_json))}" placeholder="多个 ID 用逗号分隔"></label><label class="field"><span>学习材料标识</span><input class="input" name="materials" value="${escapeHtml(listInput(activity?.materials || activity?.materials_json))}" placeholder="多个文件标识或名称用逗号分隔"></label>`, onSubmit: async form => {
      const values = Object.fromEntries(form);
      const payload = { title: values.title, category: values.category, location: values.location, content: values.content, start_at: isoOrNull(values.start_at), end_at: isoOrNull(values.end_at), registration_deadline: isoOrNull(values.registration_deadline), target_roles: values.target_roles, max_participants: numberOrNull(values.max_participants), target_member_ids: String(values.target_member_ids || "").split(/[,，]/).map(value => Number(value.trim())).filter(Number.isInteger), materials: String(values.materials || "").split(/[,，]/).map(name => name.trim()).filter(Boolean).map(name => ({ name })) };
      await api(activity ? `/api/v1/party/activities/${activity.id}` : "/api/v1/party/activities", { method: activity ? "PUT" : "POST", body: JSON.stringify(payload) }); await load(); draw(); toast(activity ? "活动已更新" : "活动已创建");
    } });
  }

  function summaryModal(activity) {
    showModal({ title: "活动总结", submitText: "保存总结", size: "wide", content: `<label class="field"><span>总结正文</span><textarea class="textarea" name="summary" required>${escapeHtml(activity.summary || "")}</textarea></label><label class="field"><span>总结附件标识</span><input class="input" name="attachments" value="${escapeHtml(listInput(activity.summary_attachments || activity.summary_attachments_json))}" placeholder="多个文件标识或名称用逗号分隔"></label><label class="party-check"><input type="checkbox" name="archive" value="true"><span>保存后归档活动</span></label>`, onSubmit: async form => { const payload = { summary: form.get("summary"), summary_attachments: String(form.get("attachments") || "").split(/[,，]/).map(name => name.trim()).filter(Boolean).map(name => ({ name })) }; if (form.get("archive") === "true") payload.archive = true; await api(`/api/v1/party/activities/${activity.id}/summary`, { method: "POST", body: JSON.stringify(payload) }); await load(); draw(); toast("活动总结已保存"); } });
  }

  async function openArchive(id) {
    try {
      const result = await api(`/api/v1/party/activities/${id}/archive`);
      const archive = result.archive || result;
      const activity = archive.activity || archive;
      const participants = arrayOf(archive, "participants", "records", "attendance_records");
      showModal({ title: activity.title || "活动档案", submitText: "关闭", size: "wide", content: `<dl class="party-detail-grid"><div><dt>活动类别</dt><dd>${escapeHtml(activity.category || "-")}</dd></div><div><dt>活动时间</dt><dd>${escapeHtml(formatDate(activity.start_at))} 至 ${escapeHtml(formatDate(activity.end_at))}</dd></div><div><dt>活动地点</dt><dd>${escapeHtml(activity.location || "-")}</dd></div><div><dt>参加对象</dt><dd>${escapeHtml(activity.target_roles || "-")}</dd></div></dl><section class="party-detail-section"><h3>活动总结</h3><p>${escapeHtml(activity.summary || "暂无总结")}</p></section><section class="party-detail-section"><h3>参与记录</h3>${participants.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>成员</th><th>报名</th><th>签到</th><th>签到时间</th></tr></thead><tbody>${participants.map(item => `<tr><td>${escapeHtml(item.user_name || item.name || `用户 #${item.user_id}`)}</td><td>${escapeHtml(item.registration_status || "-")}</td><td>${escapeHtml(item.attendance_status || "-")}</td><td>${escapeHtml(formatDate(item.sign_in_time))}</td></tr>`).join("")}</tbody></table></div>` : '<p class="muted">暂无参与记录。</p>'}</section>`, onSubmit: async () => {} });
    } catch (error) { toast(error.message, "danger"); }
  }

  async function transitionActivity(id, nextStatus) {
    try { await api(`/api/v1/party/activities/${id}/status`, { method: "PUT", body: JSON.stringify({ status: nextStatus }) }); await load(); draw(); toast(`活动已设为${ACTIVITY_STATUSES[nextStatus]}`); }
    catch (error) { toast(error.message, "danger"); }
  }

  async function exportCsv() {
    const type = container.querySelector("#party-export-type")?.value || "stats";
    try {
      const result = await api("/api/v1/party/stats/export", { method: "POST", body: JSON.stringify({ format: "csv", export_type: type, ...statsFilters }) });
      if (typeof result === "string") saveCsv(result, `party-${type}.csv`);
      else if (result?.content || result?.csv) saveCsv(result.content || result.csv, result.filename || `party-${type}.csv`);
      else if (result?.download_url) await download(result.download_url, result.filename || `party-${type}.csv`);
      else throw new Error("导出接口未返回可下载内容");
      toast("CSV 已生成");
    } catch (error) { toast(error.message, "danger"); }
  }

  function bindFilter(selector, target) {
    container.querySelector(selector)?.addEventListener("submit", async event => { event.preventDefault(); Object.assign(target, Object.fromEntries(new FormData(event.currentTarget))); container.innerHTML = loadingState("正在应用筛选"); try { await load(); draw(); } catch (error) { container.innerHTML = emptyState("筛选失败", error.message); } });
  }

  async function decidePoliticalReview(reviewId, approved) {
    const action = approved ? "approve" : "reject";
    try {
      await api(`/api/v1/party/political-status/reviews/${reviewId}/${action}`, { method: "PUT", body: JSON.stringify({ remark: null }) });
      await load(); draw(); toast(approved ? "政治面貌申请已通过" : "政治面貌申请已拒绝");
    } catch (error) { toast(error.message, "danger"); }
  }

  function politicalMaterialModal(item = null) {
    const roles = ["中共党员", "预备党员", "入党积极分子", "共青团员", "群众", "全体学生", "指定人员"];
    const selected = new Set(item?.applicable_roles || []);
    showModal({
      title: item ? "编辑政治学习资料" : "新增政治学习资料",
      submitText: item ? "保存" : "创建",
      size: "wide",
      content: `<label class="field"><span>标题</span><input class="input" name="title" maxlength="200" value="${escapeHtml(item?.title || "")}" required></label><label class="field"><span>说明</span><textarea class="textarea" name="description" maxlength="5000">${escapeHtml(item?.description || "")}</textarea></label><label class="field"><span>适用对象</span><select class="select" name="applicable_roles" multiple size="7">${roles.map(role => `<option value="${escapeHtml(role)}" ${selected.has(role) ? "selected" : ""}>${escapeHtml(role)}</option>`).join("")}</select></label><label class="field"><span>指定人员用户 ID</span><input class="input" name="target_user_ids" value="${escapeHtml((item?.target_user_ids || []).join(","))}" placeholder="多个 ID 用逗号分隔"></label><label class="field"><span>发布状态</span><select class="select" name="status"><option value="draft" ${item?.status === "draft" ? "selected" : ""}>草稿</option><option value="published" ${item?.status === "published" ? "selected" : ""}>已发布</option><option value="offline" ${item?.status === "offline" ? "selected" : ""}>已下架</option></select></label>`,
      onSubmit: async (form, element) => {
        const payload = { title: form.get("title"), description: form.get("description") || null, applicable_roles: Array.from(element.querySelector("[name=applicable_roles]").selectedOptions).map(option => option.value), target_user_ids: String(form.get("target_user_ids") || "").split(/[,，]/).map(value => Number(value.trim())).filter(Number.isInteger), status: form.get("status") };
        await api(item ? `/api/v1/party/learning-materials/${item.id}` : "/api/v1/party/learning-materials", { method: item ? "PUT" : "POST", body: JSON.stringify(payload) });
        await load(); draw(); toast(item ? "资料已更新" : "资料已创建");
      },
    });
  }

  function uploadPoliticalMaterialAttachment(materialId) {
    showModal({ title: "上传政治学习资料附件", submitText: "上传", content: `<label class="field"><span>文件</span><input class="input" name="file" type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" required><small>仅支持 PDF、JPG、JPEG、PNG，单文件不超过 20MB</small></label>`, onSubmit: async form => { const file = form.get("file"); if (!file || !/\.(pdf|jpe?g|png)$/i.test(file.name || "")) throw new Error("仅支持 PDF、JPG、JPEG、PNG 文件"); if (file.size > 20 * 1024 * 1024) throw new Error("单文件不能超过 20MB"); await api(`/api/v1/party/learning-materials/${materialId}/attachments`, { method: "POST", body: form }); await load(); draw(); toast("附件已上传"); } });
  }

  function bind() {
    container.querySelectorAll("[data-party-section]").forEach(node => node.addEventListener("click", async () => { section = node.dataset.partySection; container.innerHTML = loadingState(); try { await load(); draw(); } catch (error) { container.innerHTML = emptyState("党建管理加载失败", error.message); } }));
    bindFilter("#party-member-filter", memberFilters);
    bindFilter("#party-activity-filter", activityFilters);
    bindFilter("#party-stats-filter", statsFilters);
    bindFilter("#party-review-filter", reviewFilters);
    bindFilter("#party-roster-filter", rosterFilters);
    container.querySelector("#party-member-new")?.addEventListener("click", () => memberModal());
    container.querySelector("#party-empty-member")?.addEventListener("click", () => memberModal());
    container.querySelectorAll("[data-member-edit]").forEach(node => node.addEventListener("click", () => memberModal(members.find(item => memberId(item) === Number(node.dataset.memberEdit)))));
    container.querySelectorAll("[data-member-status]").forEach(node => node.addEventListener("click", () => statusModal(members.find(item => memberId(item) === Number(node.dataset.memberStatus)))));
    container.querySelectorAll("[data-member-material]").forEach(node => node.addEventListener("click", () => materialModal(Number(node.dataset.memberMaterial))));
    container.querySelectorAll("[data-member-delete]").forEach(node => node.addEventListener("click", () => confirmAction("确认移除该党员身份？历史业务记录仍会保留。", async () => { await api(`/api/v1/party/members/${node.dataset.memberDelete}`, { method: "DELETE" }); await load(); draw(); toast("党员身份已移除"); }, "移除")));
    container.querySelector("#party-member-import")?.addEventListener("click", () => container.querySelector("#party-member-import-file")?.click());
    container.querySelector("#party-member-import-file")?.addEventListener("change", async event => { const file = event.target.files?.[0]; if (!file) return; const form = new FormData(); form.append("file", file); try { const result = await api("/api/v1/party/members/import", { method: "POST", body: form }); toast(result?.message || `导入完成：新增 ${result?.created || 0}，更新 ${result?.updated || 0}，跳过 ${result?.skipped || 0}`); await load(); draw(); } catch (error) { toast(error.message, "danger"); } });
    container.querySelector("#party-activity-new")?.addEventListener("click", () => activityModal());
    container.querySelectorAll("[data-activity-edit]").forEach(node => node.addEventListener("click", () => activityModal(activities.find(item => Number(item.id) === Number(node.dataset.activityEdit)))));
    container.querySelectorAll("[data-activity-publish]").forEach(node => node.addEventListener("click", async () => { try { await api(`/api/v1/party/activities/${node.dataset.activityPublish}/publish`, { method: "POST", body: JSON.stringify({ notify: true }) }); await load(); draw(); toast("活动已发布并通知目标用户"); } catch (error) { toast(error.message, "danger"); } }));
    container.querySelectorAll("[data-activity-status]").forEach(node => node.addEventListener("click", () => transitionActivity(node.dataset.activityStatus, node.dataset.nextStatus)));
    container.querySelectorAll("[data-activity-summary]").forEach(node => node.addEventListener("click", () => summaryModal(activities.find(item => Number(item.id) === Number(node.dataset.activitySummary)))));
    container.querySelectorAll("[data-activity-archive]").forEach(node => node.addEventListener("click", () => openArchive(node.dataset.activityArchive)));
    container.querySelectorAll("[data-activity-delete]").forEach(node => node.addEventListener("click", () => confirmAction("活动仅在已归档后允许删除。确认继续？", async () => { await api(`/api/v1/party/activities/${node.dataset.activityDelete}`, { method: "DELETE" }); await load(); draw(); toast("活动已删除"); }, "删除")));
    container.querySelector("#party-export")?.addEventListener("click", exportCsv);
    container.querySelector("#political-material-new")?.addEventListener("click", () => politicalMaterialModal());
    container.querySelectorAll("[data-review-approve]").forEach(node => node.addEventListener("click", () => decidePoliticalReview(node.dataset.reviewApprove, true)));
    container.querySelectorAll("[data-review-reject]").forEach(node => node.addEventListener("click", () => decidePoliticalReview(node.dataset.reviewReject, false)));
    container.querySelectorAll("[data-political-material-edit]").forEach(node => node.addEventListener("click", () => politicalMaterialModal(politicalMaterials.find(item => Number(item.id) === Number(node.dataset.politicalMaterialEdit)))));
    container.querySelectorAll("[data-political-material-upload]").forEach(node => node.addEventListener("click", () => uploadPoliticalMaterialAttachment(Number(node.dataset.politicalMaterialUpload))));
    container.querySelectorAll("[data-political-material-delete]").forEach(node => node.addEventListener("click", () => confirmAction("确认删除这份政治学习资料？", async () => { await api(`/api/v1/party/learning-materials/${node.dataset.politicalMaterialDelete}`, { method: "DELETE" }); await load(); draw(); toast("资料已删除"); }, "删除")));
  }

  container.innerHTML = loadingState("正在加载党建管理数据");
  try { await load(); draw(); }
  catch (error) { container.innerHTML = emptyState("党建管理加载失败", error.message, '<button class="button button-primary" id="party-admin-retry">重新加载</button>'); container.querySelector("#party-admin-retry")?.addEventListener("click", () => renderAdminParty(container)); }
  return () => { active = false; };
}
