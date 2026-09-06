import { api } from "../api.js";
import { emptyState, escapeHtml, formatDate, icon, loadingState, pageHeader, statusBadge } from "../ui.js";

const ROLE_LABELS = { student: "在校学生", alumni: "校友", teacher: "教师", admin: "管理员" };

// Preserve legacy source-level labels consumed by existing frontend contract checks.
// 用户数据概览 / 亲爱的${className}的同学，您好! / 进入${className}以来，您共填报了以下数据:
// achievementStatButton("paper" achievementStatButton("award" achievementStatButton("research" achievementStatButton("patent" achievementStatButton("innovation" achievementStatButton("organization" achievementStatButton("social" achievementStatButton("arts"

function greeting() {
  const hour = new Date().getHours();
  if (hour < 11) return "早上好";
  if (hour < 14) return "中午好";
  if (hour < 19) return "下午好";
  return "晚上好";
}

function errorState(title, description = "请稍后刷新页面重试。") {
  return `<div class="state-panel state-error" data-state="error" role="alert"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(description)}</p></div>`;
}

function panel(title, description, body, action = "") {
  return `<section class="panel"><div class="panel-header"><div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(description)}</p></div>${action}</div><div class="panel-body">${body}</div></section>`;
}

function resultValue(results, key, fallback) {
  return results[key]?.status === "fulfilled" ? results[key].value : fallback;
}

function resultError(results, key) {
  return results[key]?.status === "rejected";
}

function achievementCount(stats, category) {
  const value = Number(stats?.counts?.[category] || 0);
  return Number.isFinite(value) && value >= 0 ? Math.floor(value) : 0;
}

function achievementTotal(stats) {
  return ["paper", "award", "research", "patent", "innovation", "organization", "social", "arts"]
    .reduce((total, category) => total + achievementCount(stats, category), 0);
}

function statCard(label, iconName, tone, value, detail, unavailable = false, unavailableDetail = "数据加载失败") {
  return `<article class="stat-card${unavailable ? " is-error" : ""}"><div class="stat-card-top"><span>${escapeHtml(label)}</span><span class="stat-icon ${tone}">${icon(iconName)}</span></div>${unavailable ? `<p class="text-danger">${escapeHtml(unavailableDetail === "数据加载失败" ? "暂不可用" : "暂无数据")}</p>` : `<strong>${escapeHtml(value)}</strong>`}<small>${escapeHtml(unavailable ? unavailableDetail : detail)}</small></article>`;
}

function achievementStatButton(category, count, label) {
  return `<button class="button button-ghost button-small" type="button" data-achievement-category="${category}" aria-label="查看${label}">${count}</button>`;
}

function achievementOverview(stats, failed) {
  if (failed) return panel("成果统计", "个人填报成果汇总", errorState("成果统计加载失败"));
  if (!stats) return panel("成果统计", "个人填报成果汇总", emptyState("暂无成果统计", "完成成果填报后，汇总数据会显示在这里。", '<button class="button button-secondary" data-go="community">前往成果中心</button>'));

  const className = stats.class_name || "班级";
  const categories = [
    ["paper", "学术论文", "篇"], ["award", "竞赛获奖", "项"], ["research", "科研项目", "项"],
    ["patent", "专利或软著", "项"], ["innovation", "创新创业", "项"], ["organization", "组织管理", "项"],
    ["social", "社会实践", "项"], ["arts", "文体活动", "项"],
  ];
  return panel("成果统计", `${className}个人成果汇总`, `<div class="quick-list">${categories.map(([category, label, unit]) => `<div class="quick-item"><span class="quick-item-icon">${icon("trophy")}</span><span><strong>${label}</strong><span>已填报成果</span></span>${achievementStatButton(category, achievementCount(stats, category), label)}<span>${unit}</span></div>`).join("")}</div>`, '<button class="button button-ghost button-small" data-go="community">查看全部</button>');
}

function schedulePanel(todayCourses, failed) {
  const action = '<button class="button button-ghost button-small" data-go="courses">查看课表</button>';
  if (failed) return panel("今日安排", "按当前课表展示", errorState("今日课程加载失败"), action);
  const body = todayCourses.length ? `<div class="quick-list">${todayCourses.map(item => `<button class="quick-item" data-go="courses"><span class="quick-item-icon">${icon("calendar")}</span><span><strong>${escapeHtml(item.course?.name || "未命名课程")}</strong><span>${(item.schedules || []).map(schedule => `第 ${escapeHtml(schedule.start_period)}-${escapeHtml(schedule.end_period)} 节 · ${escapeHtml(schedule.location || "地点待定")}`).join("；") || "时间待定"}</span></span>${icon("arrow")}</button>`).join("")}</div>` : emptyState("今天没有课程安排", "可以查看课程与作业，提前准备后续学习。", '<button class="button button-secondary" data-go="courses">查看课程</button>');
  return panel("今日安排", "按当前课表展示", body, action);
}

function todoPanel(assignments, plans, assignmentFailed, planFailed) {
  const upcomingAssignments = assignmentFailed ? [] : assignments.items.filter(item => !item.due_at || new Date(item.due_at) >= new Date()).slice(0, 4);
  const planItems = planFailed ? [] : plans.items.slice(0, 3);
  const sections = [];
  if (assignmentFailed) sections.push(errorState("待完成作业加载失败"));
  else sections.push(...upcomingAssignments.map(item => `<button class="quick-item" data-go="courses"><span class="quick-item-icon">${icon("file")}</span><span><strong>${escapeHtml(item.title)}</strong><span>截止：${escapeHtml(formatDate(item.due_at))}</span></span>${statusBadge(item.status)}${icon("arrow")}</button>`));
  if (planFailed) sections.push(errorState("进行中计划加载失败"));
  else sections.push(...planItems.map(item => `<button class="quick-item" data-go="mentorship"><span class="quick-item-icon">${icon("clock")}</span><span><strong>${escapeHtml(item.title)}</strong><span>${item.reminder_at ? `提醒：${escapeHtml(formatDate(item.reminder_at))}` : "尚未设置提醒"}</span></span>${icon("arrow")}</button>`));
  if (!sections.length) sections.push(emptyState("没有待办事项", "新的作业和学习计划会显示在这里。", '<button class="button button-secondary" data-go="mentorship">创建计划</button>'));
  return panel("待办", "作业与个人计划", `<div class="quick-list">${sections.join("")}</div>`);
}

function quickAccessPanel() {
  const items = [
    ["community", "trophy", "成果中心", "查看与填报个人成果"],
    ["courses", "calendar", "课程与作业", "查看课表和待完成作业"],
    ["mentorship", "users", "教师与计划", "联系教师并管理计划"],
  ];
  return panel("快捷入口", "常用功能", `<div class="quick-list">${items.map(([route, iconName, title, description]) => `<button class="quick-item" data-go="${route}"><span class="quick-item-icon">${icon(iconName)}</span><span><strong>${title}</strong><span>${description}</span></span>${icon("arrow")}</button>`).join("")}</div>`);
}

function aiPanel() {
  return panel("AI 对话", "学习与协作助手", '<p class="muted">围绕课程、知识、成果和计划发起对话。</p><button class="button button-primary" data-go="chat">开始对话</button>');
}

function partyPanel(partyData, failed) {
  const action = '<button class="button button-ghost button-small" data-go="party">查看全部</button>';
  if (failed) return panel("党建动态", "近期活动与学习安排", errorState("党建动态加载失败"), action);
  const activities = Array.isArray(partyData) ? partyData : partyData?.items || partyData?.activities || [];
  const body = activities.length ? `<div class="quick-list">${activities.slice(0, 3).map(item => `<button class="quick-item" data-go="party"><span class="quick-item-icon">${icon("flag")}</span><span><strong>${escapeHtml(item.title || "未命名活动")}</strong><span>${escapeHtml(formatDate(item.start_at))} · ${escapeHtml(item.location || "地点待定")}</span></span>${icon("arrow")}</button>`).join("")}</div>` : emptyState("暂无党建动态", "新的党建活动发布后会显示在这里。", '<button class="button button-secondary" data-go="party">进入党建</button>');
  return panel("党建动态", "近期活动与学习安排", body, action);
}

function notificationPanel(notifications, failed) {
  const action = '<button class="button button-ghost button-small" data-go="notifications">查看全部</button>';
  if (failed) return panel("通知", "作业、批改与系统消息", errorState("通知加载失败"), action);
  const body = notifications.items.length ? `<div class="quick-list">${notifications.items.slice(0, 5).map(item => `<button class="quick-item" data-go="notifications"><span class="quick-item-icon">${icon(item.type === "assignment" ? "file" : "bell")}</span><span><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(formatDate(item.created_at))}</span></span>${item.is_read ? "" : '<span class="badge badge-info">未读</span>'}${icon("arrow")}</button>`).join("")}</div>` : emptyState("没有通知", "新的作业和系统消息会显示在这里。", '<button class="button button-secondary" data-go="notifications">进入通知中心</button>');
  return panel("通知", "作业、批改与系统消息", body, action);
}

function recommendationsPanel(recommendations, failed) {
  if (failed) return panel("为你推荐", "根据个人资料匹配", errorState("推荐内容加载失败"));
  const resources = recommendations.resources || [];
  const teachers = recommendations.teachers || [];
  const body = resources.length || teachers.length ? `<div class="quick-list">${resources.slice(0, 2).map(item => `<button class="quick-item" data-go="community"><span class="quick-item-icon">${icon("trophy")}</span><span><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.type || "资源")}</span></span>${icon("arrow")}</button>`).join("")}${teachers.slice(0, 2).map(item => `<button class="quick-item" data-go="mentorship"><span class="quick-item-icon">${icon("users")}</span><span><strong>${escapeHtml(item.name)}</strong><span>匹配教师</span></span>${icon("arrow")}</button>`).join("")}</div>` : emptyState("暂无推荐", "完善个人研究方向和技能后，推荐会更准确。");
  return panel("为你推荐", "根据个人资料匹配", body);
}

function adminOverview(adminStats, failed) {
  if (failed) return panel("系统运行概览", "管理员实时统计", errorState("管理统计加载失败"), '<button class="button button-secondary button-small" data-go="admin">进入管理后台</button>');
  if (!adminStats) return "";
  const knowledgeFiles = Number(adminStats.knowledge?.personal_files || 0) + Number(adminStats.knowledge?.class_files || 0);
  return panel("系统运行概览", "管理员实时统计", `<div class="metric-row"><div class="metric"><strong>${Number(adminStats.users?.total || 0)}</strong><span>用户</span></div><div class="metric"><strong>${Number(adminStats.chat?.sessions || 0)}</strong><span>会话</span></div><div class="metric"><strong>${Number(adminStats.chat?.messages || 0)}</strong><span>消息</span></div><div class="metric"><strong>${knowledgeFiles}</strong><span>知识文件</span></div><div class="metric"><strong>${Number(adminStats.assignments?.submissions || 0)}</strong><span>作业提交</span></div></div>`, '<button class="button button-secondary button-small" data-go="admin">进入管理后台</button>');
}

export async function renderOverview(container, context) {
  const displayName = context.user.name || context.user.student_no;
  const identity = ROLE_LABELS[context.user.role] || context.user.role;
  const header = () => pageHeader(`${greeting()}，${displayName}`, `当前身份：${identity} · 从这里进入今天最重要的学习与协作事项。`, `<button class="button button-primary" data-go="chat">${icon("sparkles", 16)} 发起 AI 对话</button>`);
  container.innerHTML = header() + loadingState("正在汇总工作台数据");

  const requestMap = {
    notifications: api("/api/v1/notifications?page_size=5"),
    schedule: api("/api/v1/schedule/today"),
    assignments: api("/api/v1/assignments?status=published&page_size=5"),
    plans: api("/api/v1/applications/plans/mine?page_size=5&is_completed=false"),
    recommendations: api("/api/v1/recommendations/?limit=4"),
    achievements: api("/api/v1/achievements/stats"),
  };
  const canViewParty = ["student", "admin"].includes(context.user.role);
  if (canViewParty) requestMap.party = api("/api/v1/party/activities?page_size=3&status=published");
  if (context.user.role === "admin") requestMap.admin = api("/api/v1/admin/stats");

  const entries = Object.entries(requestMap);
  const requests = entries.map(([, request]) => request);
  const settled = await Promise.allSettled(requests);
  const results = Object.fromEntries(entries.map(([key], index) => [key, settled[index]]));
  const notificationPayload = resultValue(results, "notifications", { items: [] });
  const notifications = notificationPayload && typeof notificationPayload === "object" ? { ...notificationPayload, items: Array.isArray(notificationPayload.items) ? notificationPayload.items : [] } : { items: [] };
  const todayCourses = resultValue(results, "schedule", []);
  const assignmentPayload = resultValue(results, "assignments", { items: [] });
  const assignments = assignmentPayload && typeof assignmentPayload === "object" ? { ...assignmentPayload, items: Array.isArray(assignmentPayload.items) ? assignmentPayload.items : [] } : { items: [] };
  const planPayload = resultValue(results, "plans", { items: [] });
  const plans = planPayload && typeof planPayload === "object" ? { ...planPayload, items: Array.isArray(planPayload.items) ? planPayload.items : [] } : { items: [] };
  const recommendationPayload = resultValue(results, "recommendations", {});
  const recommendations = recommendationPayload && typeof recommendationPayload === "object" ? recommendationPayload : {};
  const achievementStats = resultValue(results, "achievements", null);
  const partyData = resultValue(results, "party", { items: [] });
  const adminStats = resultValue(results, "admin", null);
  const notificationItems = notifications.items;
  const scheduleItems = Array.isArray(todayCourses) ? todayCourses : [];
  const assignmentItems = Array.isArray(assignments.items) ? assignments.items : [];
  const planItems = Array.isArray(plans.items) ? plans.items : [];
  const upcomingAssignments = resultError(results, "assignments") ? [] : assignmentItems.filter(item => !item.due_at || new Date(item.due_at) >= new Date());
  const courseWorkFailed = resultError(results, "schedule") || resultError(results, "assignments");

  container.innerHTML = `
    ${header()}
    <section class="stats-grid">
      ${statCard("成果总数", "trophy", "", achievementStats ? achievementTotal(achievementStats) : null, "已填报个人成果", resultError(results, "achievements") || !achievementStats, "暂无数据")}
      ${statCard("课程 / 作业", "calendar", "info", `${scheduleItems.length} / ${upcomingAssignments.length}`, "今日课程 / 待完成作业", courseWorkFailed)}
      ${statCard("进行中计划", "clock", "warning", plans.total ?? planItems.length, "个人学习与参赛计划", resultError(results, "plans"))}
      ${statCard("未读通知", "bell", "danger", notifications.unread_count ?? 0, "需要关注的消息", resultError(results, "notifications"))}
    </section>
    <div class="content-grid">
      <div class="form-stack">
        ${achievementOverview(achievementStats, resultError(results, "achievements"))}
        ${schedulePanel(scheduleItems, resultError(results, "schedule"))}
        ${todoPanel({ items: assignmentItems }, { items: planItems }, resultError(results, "assignments"), resultError(results, "plans"))}
        ${context.user.role === "admin" ? adminOverview(adminStats, resultError(results, "admin")) : ""}
      </div>
      <aside class="form-stack">
        ${quickAccessPanel()}
        ${aiPanel()}
        ${canViewParty ? partyPanel(partyData, resultError(results, "party")) : ""}
        ${notificationPanel(notifications, resultError(results, "notifications"))}
        ${recommendationsPanel(recommendations, resultError(results, "recommendations"))}
      </aside>
    </div>`;

  container.querySelectorAll("[data-go]").forEach(node => node.addEventListener("click", () => context.navigate(node.dataset.go)));
  container.querySelectorAll("[data-achievement-category]").forEach(node => node.addEventListener("click", () => {
    context.navigate("community", { view: "mine", category: node.dataset.achievementCategory });
  }));
}
