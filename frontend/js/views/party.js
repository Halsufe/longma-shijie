import { api, download, qs } from "../api.js";
import { confirmAction, emptyState, escapeHtml, formatDate, icon, loadingState, pageHeader, showModal, toast } from "../ui.js";

const CATEGORY_LABELS = ["组织生活会", "主题党日", "理论学习", "志愿公益", "发展工作", "民主评议", "专题教育", "其他", "主题团日", "团学实践", "团组织建设", "其他团学"];
const STATUS_LABELS = { draft: "草稿", published: "已发布", ongoing: "进行中", finished: "已结束", archived: "已归档" };

function arrayOf(payload, ...keys) {
  if (Array.isArray(payload)) return payload;
  for (const key of keys) if (Array.isArray(payload?.[key])) return payload[key];
  return [];
}

function partyOf(payload) {
  return payload?.party || payload?.profile || payload?.member?.party || payload?.member || null;
}

function participantOf(activity) {
  return activity?.my_participation || activity?.my_participant || activity?.participant || activity?.participation || null;
}

function activityBadge(status) {
  const tone = { draft: "muted", published: "success", ongoing: "info", finished: "warning", archived: "muted" }[status] || "muted";
  return `<span class="badge badge-${tone}">${escapeHtml(STATUS_LABELS[status] || status || "未知")}</span>`;
}

function attachments(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === "string") {
    try { return attachments(JSON.parse(value)); } catch { return value ? [{ name: value }] : []; }
  }
  return [];
}

function attachmentName(item) {
  if (typeof item === "string") return item;
  return item?.name || item?.original_name || item?.filename || item?.title || "附件";
}

function renderAttachments(value) {
  const items = attachments(value);
  if (!items.length) return '<span class="muted">暂无材料</span>';
  return `<ul class="party-attachment-list">${items.map(item => `<li>${icon("file", 15)}<span>${escapeHtml(attachmentName(item))}</span></li>`).join("")}</ul>`;
}

function profileFacts(profile) {
  const fields = [
    ["党员类型", "party_type"], ["申请状态", "apply_status"], ["支部归属", "branch_name"],
    ["班级", "class_name"], ["年级", "grade"], ["递交申请", "apply_date"],
    ["确定积极分子", "activist_date"], ["列为发展对象", "target_date"],
    ["接受为预备党员", "probation_date"], ["转为正式党员", "full_date"],
  ];
  return fields.map(([label, key]) => `<div><dt>${label}</dt><dd>${escapeHtml(profile?.[key] || "未填写")}</dd></div>`).join("");
}

function recordActivity(record) {
  return record.activity || record.party_activity || record;
}

function recordStatus(record) {
  const registration = record.registration_status || record.participant?.registration_status || "-";
  const attendance = record.attendance_status || record.participant?.attendance_status || "none";
  const registrationLabel = registration === "registered" ? "已报名" : registration === "cancelled" ? "已取消" : registration;
  const attendanceLabel = { none: "未签到", signed_in: "已签到", absent: "缺席" }[attendance] || attendance;
  return `${registrationLabel} · ${attendanceLabel}`;
}

export async function renderParty(container) {
  let activities = [];
  let mine = null;
  let political = null;
  let politicalMaterials = [];
  let status = "";
  let category = "";
  let year = "";
  let active = true;

  container.innerHTML = pageHeader("党建", "查看活动安排、完成报名签到并管理个人参与记录。") + loadingState();

  async function load() {
    const activityRequest = api(`/api/v1/party/activities${qs({ page_size: 100, status, category, year })}`);
    const mineRequest = api("/api/v1/party/mine").catch(error => ({ unavailable: true, message: error.message }));
    const politicalRequest = api("/api/v1/party/political-status/mine").catch(error => ({ unavailable: true, message: error.message }));
    const materialRequest = api("/api/v1/party/learning-materials").catch(() => ({ items: [] }));
    const [activityData, mineData, politicalData, materialData] = await Promise.all([activityRequest, mineRequest, politicalRequest, materialRequest]);
    activities = arrayOf(activityData, "items", "activities");
    mine = mineData;
    political = politicalData;
    politicalMaterials = arrayOf(materialData, "items", "materials");
  }

  function activityActions(activity) {
    const participant = participantOf(activity);
    const registered = participant?.registration_status === "registered";
    const signedIn = participant?.attendance_status === "signed_in";
    const canAct = ["published", "ongoing"].includes(activity.status);
    const deadlineTime = new Date(activity.registration_deadline).getTime();
    const deadlineOpen = !activity.registration_deadline || Number.isNaN(deadlineTime) || deadlineTime > Date.now();
    const canRegister = canAct && deadlineOpen && activity.can_register !== false;
    const canCancel = activity.can_cancel_registration !== false && deadlineOpen;
    const canSignIn = canAct && activity.can_sign_in !== false;
    return `<div class="party-card-actions">
      <button class="button button-secondary button-small" data-party-detail="${Number(activity.id)}">${icon("eye", 15)} 查看</button>
      ${canRegister && !registered ? `<button class="button button-primary button-small" data-party-register="${Number(activity.id)}">报名</button>` : ""}
      ${registered && !signedIn && canCancel ? `<button class="button button-secondary button-small" data-party-cancel="${Number(activity.id)}">取消报名</button>` : ""}
      ${registered && !signedIn && canSignIn ? `<button class="button button-primary button-small" data-party-signin="${Number(activity.id)}">${icon("check", 15)} 签到</button>` : ""}
      ${signedIn ? '<span class="badge badge-success">已签到</span>' : ""}
    </div>`;
  }

  function activityCards() {
    if (!activities.length) return emptyState("暂无可见活动", "调整筛选条件后再试。", '<button class="button button-secondary" id="party-clear-filters">清除筛选</button>');
    return `<div class="party-activity-list">${activities.map(activity => {
      const participant = participantOf(activity);
      return `<article class="party-activity-card party-activity-row">
        <header><span class="party-category">${escapeHtml(activity.category || "其他")}</span>${activityBadge(activity.status)}</header>
        <h2>${escapeHtml(activity.title || "未命名活动")}</h2>
        <p>${escapeHtml(activity.content || activity.description || "暂无活动说明")}</p>
        <dl class="party-activity-meta">
          <div>${icon("calendar", 15)}<span>${escapeHtml(formatDate(activity.start_at))} 至 ${escapeHtml(formatDate(activity.end_at))}</span></div>
          <div>${icon("flag", 15)}<span>${escapeHtml(activity.location || "地点待定")}</span></div>
          ${activity.registration_deadline ? `<div>${icon("clock", 15)}<span>报名截止 ${escapeHtml(formatDate(activity.registration_deadline))}</span></div>` : ""}
        </dl>
        ${participant ? `<div class="party-participation-note">${escapeHtml(recordStatus(participant))}</div>` : ""}
        ${activityActions(activity)}
      </article>`;
    }).join("")}</div>`;
  }

  function minePanels() {
    if (mine?.unavailable) return {
      profile: `<section class="panel party-profile-panel"><div class="panel-header"><div><h2>我的党建档案</h2><p>当前账号暂无党员档案</p></div></div><div class="panel-body"><p class="muted">党员档案由管理员维护；公开活动仍可按参加对象报名。</p></div></section>`,
      records: "",
    };
    const profile = partyOf(mine);
    const records = arrayOf(mine, "records", "participation_records", "participations", "participants", "activities");
    return {
      profile: `<section class="panel party-profile-panel"><div class="panel-header"><div><h2>我的党员信息</h2><p>个人只读档案</p></div></div><div class="panel-body">${profile ? `<dl class="party-profile-facts">${profileFacts(profile)}</dl>${profile.remark ? `<p class="party-remark">${escapeHtml(profile.remark)}</p>` : ""}` : '<p class="muted">暂无党员档案。</p>'}</div></section>`,
      records: `<section class="panel party-record-panel"><div class="panel-header"><div><h2>我的参与记录</h2><p>${records.length} 条记录</p></div></div><div class="panel-body party-record-list">${records.length ? records.map(record => {
        const activity = recordActivity(record);
        return `<article><div><strong>${escapeHtml(activity.title || `活动 #${activity.id || record.activity_id || "-"}`)}</strong><span>${escapeHtml(formatDate(activity.start_at || record.created_at))}</span></div><span>${escapeHtml(recordStatus(record))}</span></article>`;
      }).join("") : '<p class="muted">暂无报名或签到记录。</p>'}</div></section>`,
    };
  }

  function partySummary() {
    const current = political?.political_status || "群众";
    const records = arrayOf(mine, "records", "participation_records", "participations", "participants", "activities");
    const upcoming = activities.filter(activity => ["published", "ongoing"].includes(activity.status)).length;
    return `<section class="party-summary-grid" aria-label="党建概览"><article class="party-summary-item"><span>政治面貌</span><strong>${escapeHtml(current)}</strong><small>当前身份</small></article><article class="party-summary-item"><span>待参加活动</span><strong>${upcoming}</strong><small>已发布或进行中</small></article><article class="party-summary-item"><span>参与记录</span><strong>${records.length}</strong><small>报名与签到</small></article></section>`;
  }

  function politicalMaterialsPanel() {
    return `<section class="panel"><div class="panel-header"><div><h2>政治学习资料</h2><p>按你的政治面貌展示已发布资料</p></div></div><div class="panel-body">${politicalMaterials.length ? `<div class="quick-list">${politicalMaterials.map(item => {
      const materialAttachments = attachments(item.attachments);
      return `<article class="quick-item party-learning-material"><span class="quick-item-icon">${icon("file", 16)}</span><div class="party-learning-material-main"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.description || "暂无说明")}</span>${materialAttachments.length ? `<ul class="party-attachment-list">${materialAttachments.map(attachment => {
        const fileId = attachment?.stored_name || attachment?.file_id || "";
        const fileName = attachmentName(attachment);
        return `<li><span>${icon("file", 14)} ${escapeHtml(fileName)}</span><button class="icon-button" type="button" data-political-material="${Number(item.id)}" data-political-file="${escapeHtml(fileId)}" data-political-name="${escapeHtml(fileName)}" aria-label="下载 ${escapeHtml(fileName)}" title="下载">${icon("download", 15)}</button></li>`;
      }).join("")}</ul>` : '<small>暂无附件</small>'}</div></article>`;
    }).join("")}</div>` : '<p class="muted">暂无适用的政治学习资料。</p>'}</div></section>`;
  }

  function politicalStatusPanel() {
    if (political?.unavailable) return "";
    const current = political?.political_status || "群众";
    const latest = political?.latest_review;
    const pending = latest?.status === "pending";
    const reviewText = latest ? `最近申请：${latest.to_status} · ${latest.status === "pending" ? "待审核" : latest.status === "approved" ? "已通过" : "已拒绝"}` : "暂无身份变更申请";
    return `<section class="panel party-political-status-panel"><div class="panel-header"><div><h2>我的政治面貌</h2><p>当前状态与身份变更申请</p></div><button class="button button-secondary button-small" id="party-edit-political-status" ${pending ? "disabled" : ""}>${icon("edit")} ${pending ? "审核中" : "申请变更"}</button></div><div class="panel-body"><strong>${escapeHtml(current)}</strong><p class="muted">${escapeHtml(reviewText)}</p>${pending ? '<p class="muted">已有申请在审核中，请等待管理员处理。</p>' : ""}</div></section>`;
  }

  function draw() {
    if (!active) return;
    const panels = minePanels();
    container.innerHTML = `${pageHeader("党建", "查看活动安排、完成报名签到并管理个人参与记录。")}
      <div class="tabs party-tabs"><button class="tab active" type="button">活动与档案</button></div>
      <div class="party-workbench">
        <section class="party-main-column" aria-label="党建活动">
          ${partySummary()}
          <form class="toolbar party-filter" id="party-filter">
            <select class="select" name="status"><option value="">全部状态</option>${Object.entries(STATUS_LABELS).filter(([value]) => value !== "draft").map(([value, label]) => `<option value="${value}" ${status === value ? "selected" : ""}>${label}</option>`).join("")}</select>
            <select class="select" name="category"><option value="">全部类别</option>${CATEGORY_LABELS.map(value => `<option value="${value}" ${category === value ? "selected" : ""}>${value}</option>`).join("")}</select>
            <input class="input" name="year" type="number" min="2000" max="2100" value="${escapeHtml(year)}" placeholder="年份">
            <button class="button button-secondary" type="submit">${icon("search")} 筛选</button>
          </form>
          ${activityCards()}
        </section>
        <aside class="party-support-rail">
          ${politicalStatusPanel()}
          ${politicalMaterialsPanel()}
          ${panels.records}
        </aside>
      </div>
      <div class="party-profile-section">${panels.profile}</div>`;
    bind();
  }

  function editPoliticalStatus() {
    const current = political?.political_status || "群众";
    showModal({
      title: "申请政治面貌变更",
      submitText: "提交审核",
      content: `<label class="field"><span>申请面貌</span><select class="select" name="to_status" required><option value="共青团员" ${current === "共青团员" ? "selected" : ""}>共青团员</option><option value="群众" ${current === "群众" ? "selected" : ""}>群众</option></select></label><label class="field"><span>说明</span><textarea class="textarea" name="remark" maxlength="1000" placeholder="可填写补充说明"></textarea></label>`,
      onSubmit: async form => {
        await api("/api/v1/party/political-status/mine", { method: "POST", body: JSON.stringify({ to_status: form.get("to_status"), remark: form.get("remark") || null }) });
        await load(); draw(); toast("政治面貌申请已提交");
      },
    });
  }

  function openDetail(activity) {
    const participant = participantOf(activity);
    showModal({
      title: activity.title || "活动详情", submitText: "关闭", size: "wide",
      content: `<div class="party-detail-head">${activityBadge(activity.status)}<span class="tag">${escapeHtml(activity.category || "其他")}</span></div>
        <dl class="party-detail-grid"><div><dt>活动时间</dt><dd>${escapeHtml(formatDate(activity.start_at))} 至 ${escapeHtml(formatDate(activity.end_at))}</dd></div><div><dt>活动地点</dt><dd>${escapeHtml(activity.location || "待定")}</dd></div><div><dt>参加对象</dt><dd>${escapeHtml(activity.target_roles || "未设置")}</dd></div><div><dt>报名截止</dt><dd>${escapeHtml(formatDate(activity.registration_deadline))}</dd></div></dl>
        <section class="party-detail-section"><h3>活动通知</h3><p>${escapeHtml(activity.content || "暂无活动说明")}</p></section>
        <section class="party-detail-section"><h3>学习材料</h3>${renderAttachments(activity.materials_json || activity.materials)}</section>
        ${activity.summary ? `<section class="party-detail-section"><h3>活动总结</h3><p>${escapeHtml(activity.summary)}</p>${renderAttachments(activity.summary_attachments_json || activity.summary_attachments)}</section>` : ""}
        ${participant ? `<p class="party-participation-note">我的状态：${escapeHtml(recordStatus(participant))}</p>` : ""}`,
      onSubmit: async () => {},
    });
  }

  async function detail(id) {
    try { const result = await api(`/api/v1/party/activities/${encodeURIComponent(id)}`); openDetail(result.activity || result); }
    catch (error) { toast(error.message, "danger"); }
  }

  async function mutate(path, options, message) {
    try {
      await api(path, options);
      toast(message);
      await load();
      draw();
    } catch (error) { toast(error.message, "danger"); }
  }

  function bind() {
    container.querySelector("#party-filter")?.addEventListener("submit", async event => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      status = String(form.get("status") || "");
      category = String(form.get("category") || "");
      year = String(form.get("year") || "");
      container.querySelector(".party-activity-list")?.replaceWith(document.createRange().createContextualFragment(loadingState("正在筛选活动")));
      try { await load(); draw(); } catch (error) { toast(error.message, "danger"); }
    });
    container.querySelector("#party-clear-filters")?.addEventListener("click", async () => { status = ""; category = ""; year = ""; await load(); draw(); });
    container.querySelector("#party-edit-political-status")?.addEventListener("click", editPoliticalStatus);
    container.querySelectorAll("[data-party-detail]").forEach(node => node.addEventListener("click", () => detail(node.dataset.partyDetail)));
    container.querySelectorAll("[data-party-register]").forEach(node => node.addEventListener("click", () => mutate(`/api/v1/party/activities/${node.dataset.partyRegister}/register`, { method: "POST", body: "{}" }, "报名成功")));
    container.querySelectorAll("[data-party-cancel]").forEach(node => node.addEventListener("click", () => confirmAction("确认取消本次活动报名？", () => mutate(`/api/v1/party/activities/${node.dataset.partyCancel}/register`, { method: "DELETE" }, "已取消报名"), "取消报名")));
    container.querySelectorAll("[data-party-signin]").forEach(node => node.addEventListener("click", () => mutate(`/api/v1/party/activities/${node.dataset.partySignin}/sign-in`, { method: "POST", body: JSON.stringify({ sign_in_method: "self" }) }, "签到成功")));
    container.querySelectorAll("[data-political-file]").forEach(node => node.addEventListener("click", async () => {
      const path = `/api/v1/party/learning-materials/${node.dataset.politicalMaterial}/attachments/${encodeURIComponent(node.dataset.politicalFile)}`;
      try { await download(path, node.dataset.politicalName); } catch (error) { toast(error.message, "danger"); }
    }));
  }

  try { await load(); draw(); }
  catch (error) { container.innerHTML = pageHeader("党建", "查看活动安排、完成报名签到并管理个人参与记录。") + emptyState("党建数据加载失败", error.message, '<button class="button button-primary" id="party-retry">重新加载</button>'); container.querySelector("#party-retry")?.addEventListener("click", () => renderParty(container)); }
  return () => { active = false; };
}
