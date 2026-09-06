import { api, download, fetchBlob, qs } from "../api.js";
import { confirmAction, emptyState, escapeHtml, formatDate, icon, loadingState, pageHeader, showModal, statusBadge, toast } from "../ui.js";

const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五"];

export async function renderCourses(container, context) {
  let tab = "schedule";
  let courses = [];
  let week = [];
  let assignments = [];
  let courseFilter = "";
  const isAdmin = context.user.role === "admin";
  const canSubmit = ["student", "alumni"].includes(context.user.role);

  container.innerHTML = pageHeader("课程与作业", "查看课表、完成提交，并跟进课程任务。") + loadingState();

  async function load() {
    const [courseResult, weekResult, assignmentResult] = await Promise.all([
      api("/api/v1/courses?page_size=200"),
      api("/api/v1/schedule/week"),
      api(`/api/v1/assignments?page_size=200${isAdmin ? "" : "&status=published"}`),
    ]);
    courses = courseResult.items;
    week = weekResult;
    assignments = assignmentResult.items;
  }

  function scheduleGrid() {
    const slots = [1, 3, 5, 7, 9, 11];
    const cell = (weekday, start) => {
      const entries = week.flatMap(item => item.schedules.map(schedule => ({ course: item.course, schedule })))
        .filter(item => item.schedule.weekday === weekday && item.schedule.start_period >= start && item.schedule.start_period <= start + 1);
      return `<div class="schedule-cell">${entries.map(item => `<div class="schedule-block" style="border-color:${escapeHtml(item.course.color || "#167a57")}"><strong>${escapeHtml(item.course.name)}</strong><span>${item.schedule.start_period}-${item.schedule.end_period} 节</span><span>${escapeHtml(item.schedule.location || "地点待定")}</span></div>`).join("")}</div>`;
    };
    return `<div class="table-wrap"><div class="course-week"><div class="week-head">节次</div>${WEEKDAYS.map(day => `<div class="week-head">${day}</div>`).join("")}${slots.map(start => `<div class="period-cell">${start}-${start + 1}</div>${[1,2,3,4,5].map(day => cell(day, start)).join("")}`).join("")}</div></div>`;
  }

  function assignmentTable() {
    const visibleAssignments = courseFilter ? assignments.filter(item => String(item.course_id) === courseFilter) : assignments;
    if (!visibleAssignments.length) return emptyState(courseFilter ? "该课程暂无作业" : "暂无作业", isAdmin ? "创建作业后可发布给学生。" : "老师发布作业后会显示在这里。", isAdmin ? '<button class="button button-primary" id="empty-assignment">新建作业</button>' : "");
    return `<div class="table-wrap"><table class="data-table"><thead><tr><th>作业</th><th>课程</th><th>截止时间</th><th>满分</th><th>状态</th><th></th></tr></thead><tbody>${visibleAssignments.map(item => {
      const course = courses.find(course => course.id === item.course_id);
      return `<tr><td><div class="table-title"><span class="quick-item-icon">${icon("file")}</span><span><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.description || "暂无说明")}</span></span></div></td><td>${escapeHtml(course?.name || `课程 #${item.course_id}`)}</td><td class="nowrap">${formatDate(item.due_at)}</td><td>${item.total_score}</td><td>${statusBadge(item.status)}</td><td><div class="table-actions"><button class="button button-secondary button-small" data-open-assignment="${item.id}">查看</button>${isAdmin && item.status === "draft" ? `<button class="button button-primary button-small" data-publish="${item.id}">发布</button>` : ""}${isAdmin && item.status === "published" ? `<button class="button button-ghost button-small" data-withdraw="${item.id}">撤回</button>` : ""}${isAdmin ? `<button class="icon-button danger" data-delete-assignment="${item.id}" aria-label="删除">${icon("trash")}</button>` : ""}</div></td></tr>`;
    }).join("")}</tbody></table></div>`;
  }

  function draw() {
    container.innerHTML = `
      ${pageHeader("课程与作业", "查看课表、完成提交，并跟进课程任务。", isAdmin ? `<button class="button button-secondary" id="new-course">${icon("plus")} 新建课程</button>${tab === "assignments" ? `<button class="button button-primary" id="new-assignment">${icon("plus")} 新建作业</button>` : ""}` : "")}
      <div class="tabs"><button class="tab ${tab === "schedule" ? "active" : ""}" data-tab="schedule">本周课表</button><button class="tab ${tab === "assignments" ? "active" : ""}" data-tab="assignments">作业中心</button>${isAdmin ? `<button class="tab ${tab === "courses" ? "active" : ""}" data-tab="courses">课程管理</button>` : ""}</div>
      ${tab === "schedule" ? `<section class="panel"><div class="panel-header"><div><h2>本周课程</h2><p>按北京时间和课程安排展示</p></div><form id="nl-query" style="display:flex;gap:8px"><input class="input" name="text" placeholder="例如：今天有什么课"><button class="button button-secondary" type="submit">查询</button></form></div><div class="panel-body">${week.length ? scheduleGrid() : emptyState("暂无课表", "管理员添加课程时间后会显示在这里。")}</div></section>` : ""}
      ${tab === "assignments" ? `<div class="toolbar"><label class="field toolbar-field"><span>课程筛选</span><select class="select" id="assignment-course-filter"><option value="">全部课程</option>${courses.map(course => `<option value="${course.id}" ${courseFilter === String(course.id) ? "selected" : ""}>${escapeHtml(course.name)}</option>`).join("")}</select></label></div><section class="panel panel-flush">${assignmentTable()}</section>` : ""}
      ${tab === "courses" ? `<section class="panel panel-flush">${courses.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>课程</th><th>教师</th><th>学期</th><th>说明</th><th></th></tr></thead><tbody>${courses.map(course => `<tr><td><strong>${escapeHtml(course.name)}</strong></td><td>${escapeHtml(course.teacher || "未设置")}</td><td>${escapeHtml(course.semester || "未设置")}</td><td>${escapeHtml(course.description || "-")}</td><td><div class="table-actions"><button class="icon-button" data-edit-course="${course.id}" aria-label="编辑">${icon("edit")}</button><button class="button button-secondary button-small" data-schedule-course="${course.id}">排课</button><button class="icon-button danger" data-delete-course="${course.id}" aria-label="删除">${icon("trash")}</button></div></td></tr>`).join("")}</tbody></table></div>` : emptyState("暂无课程", "新建第一门课程后再设置上课时间。")}</section>` : ""}`;
    bind();
  }

  function courseModal(course = null) {
    showModal({
      title: course ? "编辑课程" : "新建课程", submitText: course ? "保存" : "创建",
      content: `<div class="form-row"><label class="field"><span>课程名称</span><input class="input" name="name" value="${escapeHtml(course?.name || "")}" required></label><label class="field"><span>授课教师</span><input class="input" name="teacher" value="${escapeHtml(course?.teacher || "")}"></label></div><div class="form-row"><label class="field"><span>学期</span><input class="input" name="semester" value="${escapeHtml(course?.semester || "")}" placeholder="2026-2027 第一学期"></label><label class="field"><span>课程颜色</span><input class="input" name="color" type="color" value="${escapeHtml(course?.color || "#167a57")}"></label></div><label class="field"><span>课程说明</span><textarea class="textarea" name="description">${escapeHtml(course?.description || "")}</textarea></label>`,
      onSubmit: async data => {
        const body = Object.fromEntries(data);
        if (course) await api(`/api/v1/courses/${course.id}`, { method: "PUT", body: JSON.stringify(body) });
        else await api("/api/v1/courses", { method: "POST", body: JSON.stringify(body) });
        await load(); draw(); toast(course ? "课程已更新" : "课程已创建");
      },
    });
  }

  async function scheduleModal(course) {
    const existing = await api(`/api/v1/courses/${course.id}/schedules`);
    const first = existing[0] || {};
    showModal({
      title: `设置课程时间 · ${course.name}`, submitText: "保存排课",
      content: `<p class="muted">当前界面设置一个固定时间段，保存后将覆盖该课程已有排课。</p><div class="form-row"><label class="field"><span>星期</span><select class="select" name="weekday">${WEEKDAYS.map((day, index) => `<option value="${index + 1}" ${first.weekday === index + 1 ? "selected" : ""}>${day}</option>`).join("")}</select></label><label class="field"><span>地点</span><input class="input" name="location" value="${escapeHtml(first.location || "")}"></label></div><div class="form-row"><label class="field"><span>开始节次</span><input class="input" type="number" name="start_period" min="1" max="12" value="${first.start_period || 1}" required></label><label class="field"><span>结束节次</span><input class="input" type="number" name="end_period" min="1" max="12" value="${first.end_period || 2}" required></label></div><label class="field"><span>教学周</span><input class="input" name="weeks_pattern" value="${escapeHtml(first.weeks_pattern || "1-18周")}"></label>`,
      onSubmit: async data => {
        const body = [{ weekday: Number(data.get("weekday")), start_period: Number(data.get("start_period")), end_period: Number(data.get("end_period")), location: data.get("location") || null, weeks_pattern: data.get("weeks_pattern") || null }];
        await api(`/api/v1/courses/${course.id}/schedules`, { method: "PUT", body: JSON.stringify(body) });
        await load(); draw(); toast("排课已更新");
      },
    });
  }

  function assignmentModal() {
    if (!courses.length) return toast("请先创建课程", "warning");
    showModal({
      title: "新建作业", submitText: "保存草稿", size: "wide",
      content: `<div class="form-row"><label class="field"><span>课程</span><select class="select" name="course_id">${courses.map(course => `<option value="${course.id}">${escapeHtml(course.name)}</option>`).join("")}</select></label><label class="field"><span>满分</span><input class="input" name="total_score" type="number" min="1" max="1000" value="100"></label></div><label class="field"><span>作业标题</span><input class="input" name="title" required></label><label class="field"><span>说明</span><textarea class="textarea" name="description"></textarea></label><div class="form-row"><label class="field"><span>截止时间</span><input class="input" name="due_at" type="datetime-local"></label><label class="field"><span>附件链接（兼容）</span><input class="input" name="attachment_url" type="url"></label></div><label class="field"><span>作业材料</span><input class="input" name="files" type="file" multiple><small class="muted">最多 10 个文件，单文件不超过 50MB。</small><div class="tag-list" data-selected-files></div></label>`,
      onSubmit: async data => {
        const body = { course_id: Number(data.get("course_id")), title: data.get("title"), description: data.get("description") || null, due_at: data.get("due_at") ? new Date(data.get("due_at")).toISOString() : null, total_score: Number(data.get("total_score")), attachment_url: data.get("attachment_url") || null };
        const assignment = await api("/api/v1/assignments", { method: "POST", body: JSON.stringify(body) });
        const files = data.getAll("files").filter(file => file instanceof File && file.size);
        if (files.length) {
          const form = new FormData();
          files.forEach(file => form.append("files", file));
          await api(`/api/v1/assignments/${assignment.id}/attachments`, { method: "POST", body: form });
        }
        await load(); draw(); toast("作业草稿已创建");
      },
    });
    bindFilePicker();
  }

  function bindFilePicker() {
    const input = document.querySelector('#modal-root input[type="file"][name="files"]');
    const list = document.querySelector("#modal-root [data-selected-files]");
    if (!input || !list) return;
    let selected = [];
    const render = () => { list.innerHTML = selected.map((file, index) => `<span class="tag">${escapeHtml(file.name)}<button type="button" class="icon-button danger" data-remove-selected="${index}" aria-label="移除">${icon("close", 12)}</button></span>`).join(""); list.querySelectorAll("[data-remove-selected]").forEach(node => node.addEventListener("click", () => { selected.splice(Number(node.dataset.removeSelected), 1); const transfer = new DataTransfer(); selected.forEach(file => transfer.items.add(file)); input.files = transfer.files; render(); })); };
    input.addEventListener("change", () => { selected = Array.from(input.files); render(); });
  }

  async function previewAttachment(path, name) {
    const url = URL.createObjectURL(await fetchBlob(path));
    const link = document.createElement("a"); link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  function attachmentList(items, base, removable = false) {
    if (!items?.length) return '<p class="muted">暂无附件</p>';
    return `<div class="tag-list attachment-list">${items.map(file => `<span class="tag"><span>${escapeHtml(file.original_name)} · ${Math.round((file.size || 0) / 1024)}KB</span><button type="button" class="icon-button" data-attachment-preview="${file.id}" data-attachment-path="${base}/${file.id}/preview" aria-label="预览">${icon("eye", 14)}</button><button type="button" class="icon-button" data-attachment-download="${file.id}" data-attachment-path="${base}/${file.id}/download" data-attachment-name="${escapeHtml(file.original_name)}" aria-label="下载">${icon("download", 14)}</button>${removable ? `<button type="button" class="icon-button danger" data-attachment-delete="${file.id}" aria-label="删除">${icon("trash", 14)}</button>` : ""}</span>`).join("")}</div>`;
  }

  function bindAttachmentActions() {
    document.querySelectorAll("#modal-root [data-attachment-preview]").forEach(node => node.addEventListener("click", async () => { try { await previewAttachment(node.dataset.attachmentPath, node.closest(".tag")?.textContent || "附件"); } catch (error) { toast(error.message, "danger"); } }));
    document.querySelectorAll("#modal-root [data-attachment-download]").forEach(node => node.addEventListener("click", async () => { try { await download(node.dataset.attachmentPath, node.dataset.attachmentName); } catch (error) { toast(error.message, "danger"); } }));
    document.querySelectorAll("#modal-root [data-attachment-delete]").forEach(node => node.addEventListener("click", async () => { try { await api(`/api/v1/assignments/attachments/${node.dataset.attachmentDelete}`, { method: "DELETE" }); node.closest(".tag")?.remove(); toast("附件已删除"); } catch (error) { toast(error.message, "danger"); } }));
  }

  async function openAssignment(item) {
    let submission = null;
    if (canSubmit && item.status === "published") {
      try { submission = await api(`/api/v1/assignments/${item.id}/submission`); } catch { submission = null; }
    }
    if (isAdmin) {
      let stats = null;
      try { stats = await api(`/api/v1/assignments/${item.id}/stats`); } catch { stats = null; }
      const submissions = await api(`/api/v1/assignments/${item.id}/submissions`).catch(() => []);
      const attachments = await api(`/api/v1/assignments/${item.id}/attachments`).catch(() => []);
      showModal({ title: item.title, submitText: "关闭", size: "wide", content: `<p>${escapeHtml(item.description || "暂无作业说明")}</p>${item.attachment_url ? `<p>附件链接：<a href="${escapeHtml(item.attachment_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.attachment_url)}</a></p>` : ""}<div class="field"><span>作业材料</span>${attachmentList(attachments, "/api/v1/assignments/attachments", true)}</div><div class="metric-row"><div class="metric"><strong>${stats?.submitted_count || 0}</strong><span>已提交</span></div><div class="metric"><strong>${stats?.graded_count || 0}</strong><span>已批改</span></div><div class="metric"><strong>${stats?.total_students || 0}</strong><span>学生总数</span></div></div>${submissions.length ? `<div class="field"><span>提交记录</span><div class="table-wrap"><table class="data-table"><thead><tr><th>学生</th><th>时间</th><th>状态</th><th></th></tr></thead><tbody>${submissions.map(submission => `<tr><td>用户 #${submission.user_id}</td><td>${formatDate(submission.updated_at)}</td><td>${statusBadge(submission.status)}</td><td><button type="button" class="button button-secondary button-small" data-submission-history="${submission.id}">版本与附件</button></td></tr>`).join("")}</tbody></table></div></div>` : ""}${stats?.not_submitted?.length ? `<div class="field"><span>未交名单</span><div class="tag-list">${stats.not_submitted.map(user => `<span class="tag">${escapeHtml(user.name)} · ${escapeHtml(user.student_no)}</span>`).join("")}</div></div>` : ""}`, onSubmit: async () => {} });
      bindAttachmentActions();
      document.querySelectorAll("#modal-root [data-submission-history]").forEach(node => node.addEventListener("click", () => openSubmissionHistory(Number(node.dataset.submissionHistory))));
    } else {
      const assignmentAttachments = await api(`/api/v1/assignments/${item.id}/attachments`).catch(() => []);
      let history = [];
      if (submission) history = await api(`/api/v1/submissions/${submission.id}/versions`).catch(() => []);
      showModal({ title: item.title, submitText: "提交作业", size: "wide", content: `<p>${escapeHtml(item.description || "暂无作业说明")}</p><p class="muted">截止：${formatDate(item.due_at)} · 满分 ${item.total_score}</p>${item.attachment_url ? `<p>附件链接：<a href="${escapeHtml(item.attachment_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.attachment_url)}</a></p>` : ""}<div class="field"><span>作业材料</span>${attachmentList(assignmentAttachments, "/api/v1/assignments/attachments")}</div><label class="field"><span>提交内容</span><textarea class="textarea" name="content" maxlength="20000" ${canSubmit ? "" : "disabled"}>${escapeHtml(submission?.content || "")}</textarea></label><label class="field"><span>附件名称（兼容）</span><input class="input" name="attachment_name" value="${escapeHtml(submission?.attachment_name || "")}" ${canSubmit ? "" : "disabled"}></label><label class="field"><span>提交附件</span><input class="input" name="files" type="file" multiple ${canSubmit ? "" : "disabled"}><small class="muted">历史版本附件会保留，可在版本历史中查看。</small><div class="tag-list" data-selected-files></div></label>${history.length ? `<div class="field"><span>版本历史</span><div class="table-wrap"><table class="data-table"><thead><tr><th>版本</th><th>提交时间</th><th>附件</th></tr></thead><tbody>${history.map(version => `<tr><td>v${version.version}</td><td>${formatDate(version.created_at)}</td><td><button type="button" class="button button-secondary button-small" data-version-attachments="${version.version}" data-submission-id="${submission.id}">查看附件</button></td></tr>`).join("")}</tbody></table></div></div>` : ""}`, onSubmit: async data => {
        if (!canSubmit) return;
        const files = data.getAll("files").filter(file => file instanceof File && file.size);
        if (files.length) {
          const form = new FormData(); form.append("content", data.get("content") || ""); files.forEach(file => form.append("files", file));
          await api(`/api/v1/assignments/${item.id}/submit-files`, { method: "POST", body: form });
        } else await api(`/api/v1/assignments/${item.id}/submit`, { method: "POST", body: JSON.stringify({ content: data.get("content"), attachment_name: data.get("attachment_name") || null }) });
        toast(submission ? "提交已更新并保留版本" : "作业提交成功");
      }});
      bindFilePicker();
      bindAttachmentActions();
      document.querySelectorAll("#modal-root [data-version-attachments]").forEach(node => node.addEventListener("click", async () => { try { const files = await api(`/api/v1/submissions/${node.dataset.submissionId}/attachments?version=${node.dataset.versionAttachments}`); showModal({ title: `提交附件 · v${node.dataset.versionAttachments}`, submitText: "关闭", content: attachmentList(files, "/api/v1/submissions/attachments"), onSubmit: async () => {} }); bindAttachmentActions(); } catch (error) { toast(error.message, "danger"); } }));
    }
  }

  async function openSubmissionHistory(submissionId) {
    try {
      const versions = await api(`/api/v1/submissions/${submissionId}/versions`);
      const groups = await Promise.all(versions.map(async version => ({ version, files: await api(`/api/v1/submissions/${submissionId}/attachments?version=${version.version}`) })));
      showModal({ title: "提交版本与附件", submitText: "关闭", size: "wide", content: groups.map(({ version, files }) => `<section class="field"><span>v${version.version} · ${formatDate(version.created_at)}</span><p>${escapeHtml(version.content || "无文字内容")}</p>${attachmentList(files, "/api/v1/submissions/attachments")}</section>`).join("") || '<p class="muted">暂无历史版本</p>', onSubmit: async () => {} });
      bindAttachmentActions();
    } catch (error) { toast(error.message, "danger"); }
  }

  function bind() {
    container.querySelectorAll("[data-tab]").forEach(node => node.addEventListener("click", () => { tab = node.dataset.tab; draw(); }));
    container.querySelector("#assignment-course-filter")?.addEventListener("change", event => { courseFilter = event.currentTarget.value; draw(); });
    container.querySelector("#new-course")?.addEventListener("click", () => courseModal());
    container.querySelector("#new-assignment")?.addEventListener("click", assignmentModal);
    container.querySelector("#empty-assignment")?.addEventListener("click", assignmentModal);
    container.querySelectorAll("[data-edit-course]").forEach(node => node.addEventListener("click", () => courseModal(courses.find(item => item.id === Number(node.dataset.editCourse)))));
    container.querySelectorAll("[data-schedule-course]").forEach(node => node.addEventListener("click", () => scheduleModal(courses.find(item => item.id === Number(node.dataset.scheduleCourse)))));
    container.querySelectorAll("[data-delete-course]").forEach(node => node.addEventListener("click", () => confirmAction("确认删除这门课程？", async () => { await api(`/api/v1/courses/${node.dataset.deleteCourse}`, { method: "DELETE" }); await load(); draw(); }, "删除")));
    container.querySelectorAll("[data-open-assignment]").forEach(node => node.addEventListener("click", () => openAssignment(assignments.find(item => item.id === Number(node.dataset.openAssignment)))));
    container.querySelectorAll("[data-publish]").forEach(node => node.addEventListener("click", async () => { await api(`/api/v1/assignments/${node.dataset.publish}/publish`, { method: "POST" }); await load(); draw(); toast("作业已发布并发送通知"); }));
    container.querySelectorAll("[data-withdraw]").forEach(node => node.addEventListener("click", async () => { await api(`/api/v1/assignments/${node.dataset.withdraw}/withdraw`, { method: "POST" }); await load(); draw(); toast("作业已撤回"); }));
    container.querySelectorAll("[data-delete-assignment]").forEach(node => node.addEventListener("click", () => confirmAction("确认删除这项作业？", async () => { await api(`/api/v1/assignments/${node.dataset.deleteAssignment}`, { method: "DELETE" }); await load(); draw(); }, "删除")));
    container.querySelector("#nl-query")?.addEventListener("submit", async event => {
      event.preventDefault();
      try { const result = await api("/api/v1/courses/query-nl", { method: "POST", body: JSON.stringify({ text: new FormData(event.currentTarget).get("text") }) }); showModal({ title: "课程查询结果", content: `<pre style="white-space:pre-wrap;margin:0">${escapeHtml(JSON.stringify(result, null, 2))}</pre>`, submitText: "关闭", onSubmit: async () => {} }); } catch (error) { toast(error.message, "danger"); }
    });
  }

  try { await load(); draw(); } catch (error) { container.innerHTML = pageHeader("课程与作业", "查看课表、完成提交，并跟进课程任务。") + emptyState("加载失败", error.message); }
}
