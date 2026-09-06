import { api } from "./api.js";
import { confirmAction, emptyState, escapeHtml, formatDate, pageHeader, showModal, toast } from "./ui.js";
import { roundLabel, stageLabel } from "./mentor_selection_common.js";

function batchHeader(current) {
  const batch = current.batch;
  return '<section class="panel mentor-summary-card"><div class="panel-header"><div><h2>' +
    escapeHtml(batch.name) + '</h2><p>' + escapeHtml(batch.academic_year) + ' · ' +
    escapeHtml(batch.term) + '</p></div><span class="badge badge-info">' +
    stageLabel(current.stage) + '</span></div><div class="panel-body"><div class="stats-grid mentor-summary-grid">' +
    '<div class="stat-card"><span>当前轮次</span><strong>' + roundLabel(current.round) +
    '</strong></div><div class="stat-card"><span>主选发布</span><strong>' +
    formatDate(batch.main_publish_at) + '</strong></div></div></div></section>';
}

function mentorContextPanel(current) {
  const batch = current.batch || {};
  return '<section class="panel mentor-context-card"><div class="panel-header"><div><h2>当前阶段</h2><p>按批次规则完成下一步操作</p></div></div><div class="panel-body"><span class="badge badge-info">' +
    escapeHtml(stageLabel(current.stage)) + '</span><dl class="mentor-context-list"><div><dt>轮次</dt><dd>' + escapeHtml(roundLabel(current.round)) +
    '</dd></div><div><dt>主选发布</dt><dd>' + escapeHtml(formatDate(batch.main_publish_at)) +
    '</dd></div><div><dt>补录发布</dt><dd>' + escapeHtml(formatDate(batch.supplement_publish_at)) +
    '</dd></div></dl></div></section>';
}

async function studentView(root, current, context) {
  const mainRoot = root.querySelector(".mentor-main-panel") || root;
  const sideRoot = root.querySelector(".mentor-side-panel") || root;
  const id = current.batch.id;
  const publishedStages = ["main_published", "supplement_published", "completed"];
  const waitingStages = ["mentor_select", "main_pending", "supplement_mentor_select", "supplement_pending"];
  if (publishedStages.includes(current.stage)) {
    const result = await api("/api/v1/mentor-selection/batches/" + id + "/results/mine");
    const teacher = result?.teacher;
    mainRoot.innerHTML += '<section class="panel"><div class="panel-header"><div><h2>匹配结果</h2><p>导师双选结果已发布</p></div></div><div class="panel-body">' +
      (teacher ? '<article class="resource-card"><h3>' + escapeHtml(teacher.name) + '</h3><p>' + escapeHtml(teacher.profile?.research || teacher.profile?.bio || "导师信息已确认") + '</p>' +
        ((teacher.directions || []).map(function (direction) { return '<div class="field"><strong>' + escapeHtml(direction.title) + '</strong><p>' + escapeHtml(direction.description || "暂无方向说明") + '</p></div>'; }).join("")) +
        '</article>' : '<p class="muted">本轮暂未匹配到导师，请关注补录安排。</p>') + '</div></section>';
    return;
  }
  if (waitingStages.includes(current.stage)) {
    mainRoot.innerHTML += '<section class="panel"><div class="panel-header"><div><h2>等待批次推进</h2><p>志愿已提交，导师完成选择后由管理员计算并发布匹配结果。</p></div><span class="badge badge-info">' + stageLabel(current.stage) + '</span></div><div class="panel-body"><p class="muted">当前阶段不允许修改志愿。结果发布后，这里会显示匹配导师。</p></div></section>';
    return;
  }
  const mentors = await api("/api/v1/mentor-selection/batches/" + id + "/mentors");
  const editable = ["student_apply", "supplement_student_apply"].includes(current.stage);
  const mentorCards = mentors.items.map(function (mentor) {
    return '<article class="resource-card"><h3>' + escapeHtml(mentor.name) + '</h3><p>' +
      escapeHtml(mentor.profile?.research || mentor.profile?.bio || "暂无简介") + '</p>' +
      ((mentor.directions || []).map(function (direction) {
        return '<div class="field"><strong>' + escapeHtml(direction.title) + '</strong><p>' + escapeHtml(direction.description || "暂无方向说明") + '</p></div>';
      }).join("")) + '<div class="resource-meta"><span>剩余名额 ' + mentor.remaining_quota +
      '</span></div><label class="field"><span>志愿顺序</span><input class="input" type="number" min="1" data-rank="' +
      mentor.id + '"></label><label class="field"><span>申请理由</span><textarea class="textarea" data-reason="' +
      mentor.id + '"></textarea></label></article>';
  }).join("");
  mainRoot.innerHTML += '<section class="panel mentor-preferences-panel"><div class="panel-header"><div><h2>可选导师</h2>' +
    '<p>主选填写 3-4 个志愿，补录至少填写 1 个志愿</p></div><span class="muted">' + mentors.items.length + ' 位</span></div><div class="panel-body">' +
    '<div class="resource-grid">' + (mentorCards || '<p class="muted">当前批次还没有可选导师，请联系管理员确认导师名单。</p>') + '</div></div></section>';
  sideRoot.innerHTML += '<section class="panel mentor-submit-panel"><div class="panel-header"><div><h2>提交信息</h2><p>先填写陈述，再保存或正式提交志愿。</p></div></div><div class="panel-body">' +
    '<label class="field"><span>个人陈述</span><textarea class="textarea" id="ms-statement"></textarea></label>' +
    (editable ? '<div class="form-actions"><button class="button button-secondary" id="ms-draft">保存草稿</button><button class="button button-primary" id="ms-submit">正式提交</button></div>' : '<p class="muted">当前阶段不可修改志愿。</p>') + '</div></section>';
  async function save(submit) {
    const items = mentors.items.map(function (mentor) {
      const rank = Number(root.querySelector('[data-rank="' + mentor.id + '"]').value || 0);
      return rank ? {
        teacher_id: mentor.id,
        rank: rank,
        reason: root.querySelector('[data-reason="' + mentor.id + '"]').value,
      } : null;
    }).filter(Boolean).sort(function (a, b) { return a.rank - b.rank; });
    if (submit) {
      const minimum = current.round === "main" ? 3 : 1;
      const maximum = current.round === "main" ? 4 : null;
      if (items.length < minimum || maximum !== null && items.length > maximum) {
        throw new Error(current.round === "main" ? "主选需选择 3 至 4 位导师" : "补录至少选择 1 位导师");
      }
      if (!root.querySelector("#ms-statement").value.trim() || items.some(function (item) { return !item.reason.trim(); })) {
        throw new Error("请填写个人陈述和每位导师的申请理由");
      }
    }
    await api("/api/v1/mentor-selection/batches/" + id + "/preferences/mine", {
      method: "PUT",
      body: JSON.stringify({
        round: current.round,
        personal_statement: root.querySelector("#ms-statement").value,
        items: items,
        submit: submit,
      }),
    });
    toast(submit ? "志愿已正式提交" : "草稿已保存");
    if (submit) await renderMentorSelection(root, context);
  }
  root.querySelector("#ms-draft")?.addEventListener("click", async function () {
    try { await save(false); } catch (error) { toast(error.message, "danger"); }
  });
  root.querySelector("#ms-submit")?.addEventListener("click", async function () {
    try { await save(true); } catch (error) { toast(error.message, "danger"); }
  });
}

async function teacherView(root, current, context) {
  const id = current.batch.id;
  if (["main_published", "supplement_published", "completed"].includes(current.stage)) {
    const result = await api("/api/v1/mentor-selection/batches/" + id + "/results/mine");
    const students = result?.students || [];
    root.innerHTML += '<section class="panel"><div class="panel-header"><div><h2>最终匹配学生</h2><p>结果发布后不再展示未匹配候选档案</p></div><span class="badge badge-info">' + students.length + ' 人</span></div><div class="panel-body"><div class="application-list">' + students.map(function (student) { return '<article class="list-row"><div class="list-row-main"><h3>' + escapeHtml(student.name) + '</h3><p>' + escapeHtml(student.student_no) + '</p></div></article>'; }).join("") + '</div></div></section>';
    return;
  }
  const candidates = await api("/api/v1/mentor-selection/batches/" + id + "/candidates?round=" + current.round);
  const editable = ["mentor_select", "supplement_mentor_select"].includes(current.stage);
  root.innerHTML += '<section class="panel"><div class="panel-header"><div><h2>候选学生</h2>' +
    '<p>查看获授权档案后再做接收或拒绝决定；不显示志愿顺序和其他导师信息</p></div><span class="badge badge-info">' +
    candidates.total + ' 人</span></div><div class="panel-body"><div class="application-list">' +
    candidates.items.map(function (item) {
      return '<article class="list-row"><div class="list-row-main"><h3>' + escapeHtml(item.name) +
        '</h3><p>' + escapeHtml(item.reason || "未填写理由") + '</p><div class="list-row-meta"><span>' +
        escapeHtml(item.student_no) + '</span><span>' + escapeHtml(item.profile?.major || "专业未填写") +
        '</span></div></div><div class="resource-actions">' +
        '<button class="button button-secondary button-small" data-candidate-detail="' + item.student_id + '">查看详情</button>' +
        (editable ? '<div class="button-group candidate-decision" data-decision="' + item.student_id +
        '" data-value=""><button type="button" class="button button-secondary button-small" data-reject="' +
        item.student_id + '">拒绝</button><button type="button" class="button button-secondary button-small" data-accept="' +
        item.student_id + '">接收</button></div>' : '') + '</div></article>';
    }).join("") + (candidates.total ? '' : '<p class="muted">暂无候选学生。学生完成正式志愿提交后会显示在这里。</p>') + '</div>' + (editable ? '<div class="form-actions"><button class="button button-secondary" id="ms-save-list">保存名单</button><button class="button button-primary" id="ms-final-list">最终提交</button></div>' : '') + '</div></section>';
  async function showCandidateDetail(studentId) {
    const detail = await api("/api/v1/mentor-selection/batches/" + id + "/candidates/" + studentId + "?round=" + current.round);
    const profile = detail.profile || {};
    const grades = (profile.course_grades || []).map(function (grade) {
      return '<li>' + escapeHtml(grade.course_name) + '：' + escapeHtml(grade.score) +
        (grade.remark ? '（' + escapeHtml(grade.remark) + '）' : '') + '</li>';
    }).join("") || '<li>暂无课程成绩</li>';
    const achievements = (detail.achievements || []).map(function (achievement) {
      return '<li><strong>' + escapeHtml(achievement.title) + '</strong> · ' +
        escapeHtml(achievement.level || achievement.category || "已审核成果") + '</li>';
    }).join("") || '<li>暂无已审核成果</li>';
    showModal({
      title: detail.name + " 的候选档案",
      submitText: "关闭",
      size: "wide",
      content: '<div class="field"><span>学号 / 专业</span><p>' + escapeHtml(detail.student_no) + ' · ' +
        escapeHtml(profile.major || "未填写") + '</p></div><div class="form-row"><div class="field"><span>手机号</span><p>' +
        escapeHtml(profile.phone || "未填写") + '</p></div><div class="field"><span>邮箱</span><p>' +
        escapeHtml(profile.email || "未填写") + '</p></div></div><div class="field"><span>个人简介</span><p>' +
        escapeHtml(profile.bio || "未填写") + '</p></div><div class="field"><span>个人陈述</span><p>' +
        escapeHtml(detail.personal_statement || "未填写") + '</p></div><div class="field"><span>给我的申请理由</span><p>' +
        escapeHtml(detail.reason || "未填写") + '</p></div><div class="field"><span>课程成绩</span><ul>' +
        grades + '</ul></div><div class="field"><span>已审核成果</span><ul>' + achievements + '</ul></div>',
      onSubmit: async function () {},
    });
  }
  async function save(submit) {
    const items = [...root.querySelectorAll(".candidate-decision")].map(function (node) {
      return { student_id: Number(node.dataset.decision), decision: node.dataset.value };
    }).filter(function (item) { return item.decision; });
    await api("/api/v1/mentor-selection/batches/" + id + "/decisions/mine", {
      method: "PUT",
      body: JSON.stringify({ round: current.round, items: items, submit: submit }),
    });
    toast(submit ? "接收名单已最终提交" : "接收名单已保存");
  }
  function showDecision(group, decision) {
    const accept = group.querySelector("[data-accept]");
    const reject = group.querySelector("[data-reject]");
    group.dataset.value = decision;
    accept.classList.toggle("button-primary", decision === "accepted");
    accept.classList.toggle("button-secondary", decision !== "accepted");
    reject.classList.toggle("button-danger", decision === "rejected");
    reject.classList.toggle("button-secondary", decision !== "rejected");
    accept.textContent = decision === "accepted" ? "已接收" : "接收";
    reject.textContent = decision === "rejected" ? "已拒绝" : "拒绝";
  }
  root.querySelector("#ms-save-list")?.addEventListener("click", async function () {
    try { await save(false); } catch (error) { toast(error.message, "danger"); }
  });
  root.querySelector("#ms-final-list")?.addEventListener("click", async function () {
    try { await save(true); await renderMentorSelection(root, context); } catch (error) { toast(error.message, "danger"); }
  });
  root.querySelectorAll("[data-candidate-detail]").forEach(function (node) {
    node.addEventListener("click", function () { showCandidateDetail(Number(node.dataset.candidateDetail)); });
  });
  root.querySelectorAll("[data-accept]").forEach(function (node) {
    node.addEventListener("click", async function () {
      const group = root.querySelector('.candidate-decision[data-decision="' + node.dataset.accept + '"]');
      showDecision(group, "accepted");
      try { await save(false); } catch (error) { toast(error.message, "danger"); }
    });
  });
  root.querySelectorAll("[data-reject]").forEach(function (node) {
    node.addEventListener("click", async function () {
      const group = root.querySelector('.candidate-decision[data-decision="' + node.dataset.reject + '"]');
      showDecision(group, "rejected");
      try { await save(false); } catch (error) { toast(error.message, "danger"); }
    });
  });
}

async function adminView(root, current, context) {
  const id = current.batch.id;
  if (current.stage === "draft") {
    const candidates = await api("/api/v1/mentor-selection/batches/" + id + "/mentors/candidates");
    root.innerHTML += '<section class="panel"><div class="panel-header"><div><h2>批次名单</h2><p>上传 Excel 后先预检名单，再选择至少 3 名导师并开放主选</p></div></div><div class="panel-body"><label class="field"><span>学生 Excel 名单</span><input class="input" id="ms-roster-file" type="file" accept=".xlsx,.xls,.csv" required><small class="muted">表头支持：学号、姓名、班级（或 student_no、name、class_name）</small></label><button class="button button-secondary" id="ms-import">预检并导入</button><div class="field"><span>参与导师</span><div class="application-list">' + candidates.items.map(function (teacher) { return '<label class="list-row"><input type="checkbox" data-mentor="' + teacher.id + '"><div class="list-row-main"><strong>' + escapeHtml(teacher.name) + '</strong><p>' + escapeHtml(teacher.profile?.research || teacher.profile?.department || "暂无方向信息") + '</p>' + (teacher.directions || []).map(function (direction) { return '<small>' + escapeHtml(direction.title) + '：' + escapeHtml(direction.description || "暂无说明") + '</small>'; }).join("") + '</div></label>'; }).join("") + '</div></div><div class="form-actions"><button class="button button-secondary" id="ms-save-mentors">保存导师名单</button><button class="button button-primary" id="ms-open">开放主选</button></div></div></section>';
    root.querySelector("#ms-import").addEventListener("click", async function () {
      const file = root.querySelector("#ms-roster-file").files[0];
      if (!file) { toast("请选择 CSV、XLSX 或 XLS 文件", "danger"); return; }
      try {
        const form = new FormData();
        form.append("file", file);
        const preview = await api("/api/v1/mentor-selection/batches/" + id + "/students/import/preview", { method: "POST", body: form });
        if (preview.errors) {
          const firstError = preview.rows.find(function (row) { return row.error; });
          throw new Error("名单预检失败：" + (firstError?.error || (preview.errors + " 行存在错误")));
        }
        await api("/api/v1/mentor-selection/batches/" + id + "/students/import/confirm", { method: "POST", body: JSON.stringify({ rows: preview.rows }) });
        toast("学生名单已导入");
        await renderMentorSelection(root, context);
      } catch (error) {
        toast(error.message, "danger");
      }
    });
    root.querySelector("#ms-save-mentors").addEventListener("click", async function () {
      const teacherIds = [...root.querySelectorAll("[data-mentor]:checked")].map(function (node) { return Number(node.dataset.mentor); });
      if (teacherIds.length < 3) { toast("至少选择 3 名导师", "danger"); return; }
      try {
        await api("/api/v1/mentor-selection/batches/" + id + "/mentors", { method: "PUT", body: JSON.stringify({ teacher_ids: teacherIds }) });
        toast("导师名单已保存");
      } catch (error) { toast(error.message, "danger"); }
    });
    root.querySelector("#ms-open").addEventListener("click", async function () {
      try {
        await api("/api/v1/mentor-selection/batches/" + id + "/open", { method: "POST" });
        toast("主选已开放");
        await renderMentorSelection(root, context);
      } catch (error) { toast(error.message, "danger"); }
    });
    return;
  }
  const summary = await api("/api/v1/mentor-selection/batches/" + id + "/summary");
  const roster = await api("/api/v1/mentor-selection/batches/" + id + "/students");
  const selectedMentors = await api("/api/v1/mentor-selection/batches/" + id + "/mentors");
  const stageNames = {
    student_apply: "结束学生填报并进入导师选择",
    mentor_select: "结束导师选择并计算主选结果",
    main_pending: "发布主选结果",
    main_published: "开放补录学生填报",
    supplement_student_apply: "结束补录填报并进入导师选择",
    supplement_mentor_select: "结束补录导师选择并计算结果",
    supplement_pending: "发布补录结果并结束批次",
  };
  const extendStages = {
    student_apply: "student",
    mentor_select: "mentor",
    supplement_student_apply: "supplement_student",
    supplement_mentor_select: "supplement_mentor",
  };
  const canReopen = ["main_published", "supplement_published", "completed"].includes(current.stage);
  root.innerHTML += '<section class="panel"><div class="panel-header"><div><h2>只读汇总</h2>' +
    '<p>系统按学生志愿顺序匹配，管理员不可手工改配</p></div></div><div class="panel-body">' +
    '<div class="stats-grid"><div class="stat-card"><span>已匹配</span><strong>' + summary.matched +
    '</strong></div><div class="stat-card"><span>未匹配</span><strong>' + summary.unmatched +
    '</strong></div></div><div class="form-actions">' +
    (stageNames[current.stage] ? '<button class="button button-primary" id="ms-advance">' + stageNames[current.stage] + '</button>' : '') +
    (extendStages[current.stage] ? '<button class="button button-secondary" id="ms-extend">延长当前阶段</button>' : '') +
    (current.stage === "supplement_blocked" ? '<button class="button button-secondary" id="ms-extend">延长补录阶段</button>' : '') +
    (canReopen ? '<button class="button button-danger" id="ms-reopen">撤回并重开</button>' : '') +
    '</div><p class="muted">阶段推进会锁定对应提交并自动计算或发布结果，不能手工改变匹配归属。</p></div></section>' +
    '<section class="panel"><div class="panel-header"><div><h2>批次配置</h2><p>草稿阶段可导入学生并选择导师，批次开放后配置自动锁定。</p></div></div><div class="panel-body"><div class="stats-grid"><div class="stat-card"><span>学生名单</span><strong>' + roster.total + ' 人</strong></div><div class="stat-card"><span>参与导师</span><strong>' + selectedMentors.total + ' 人</strong></div></div><div class="application-list">' +
    roster.items.map(function (student) { return '<div class="list-row"><div class="list-row-main"><strong>' + escapeHtml(student.name) + '</strong><p>' + escapeHtml(student.student_no) + ' · ' + escapeHtml(student.class_name) + '</p></div></div>'; }).join("") +
    '</div></div></section>';
  root.querySelector("#ms-advance")?.addEventListener("click", function () {
    confirmAction("确认执行“" + stageNames[current.stage] + "”吗？", async function () {
      await api("/api/v1/mentor-selection/batches/" + id + "/advance", {
        method: "POST",
        body: JSON.stringify({ confirm: true }),
      });
      toast("批次已推进");
      await renderMentorSelection(root, context);
    }, "推进");
  });
  root.querySelector("#ms-extend")?.addEventListener("click", function () {
    const stage = extendStages[current.stage] || "supplement_student";
    showModal({
      title: "延长当前阶段",
      submitText: "延长",
      content: '<label class="field"><span>新的截止时间</span><input class="input" type="datetime-local" name="new_end" required></label>',
      onSubmit: async function (data) {
        await api("/api/v1/mentor-selection/batches/" + id + "/extend", {
          method: "POST",
          body: JSON.stringify({ stage: stage, new_end: new Date(data.get("new_end")).toISOString() }),
        });
        toast("阶段已延长");
        await renderMentorSelection(root, context);
      },
    });
  });
  root.querySelector("#ms-reopen")?.addEventListener("click", function () {
    showModal({
      title: "撤回并重开",
      submitText: "确认重开",
      content: '<label class="field"><span>重开位置</span><select class="select" name="stage"><option value="student">学生重新填报志愿</option><option value="mentor">保留志愿，导师重新选择</option></select></label>',
      onSubmit: async function (data) {
        await api("/api/v1/mentor-selection/batches/" + id + "/reopen", {
          method: "POST",
          body: JSON.stringify({ stage: data.get("stage") }),
        });
        toast("结果已撤回，批次已重开");
        await renderMentorSelection(root, context);
      },
    });
  });
}

export async function renderMentorSelection(root, context) {
  const pageRoot = root.closest?.("[data-mentor-page]") || root;
  pageRoot.dataset.mentorPage = "true";
  pageRoot.innerHTML = pageHeader("学术导师双选", "学生填报、导师选择与匹配结果统一在此处理。");
  try {
    const current = await api("/api/v1/mentor-selection/current");
    if (!current.batch) {
      pageRoot.innerHTML += emptyState("当前没有进行中的双选批次", "管理员创建并开放批次后会显示在这里。", context.user.role === "admin" ? '<button class="button button-primary" id="ms-create-batch">创建批次</button>' : "");
      pageRoot.querySelector("#ms-create-batch")?.addEventListener("click", function () {
        showModal({
          title: "创建双选批次",
          submitText: "创建",
          size: "wide",
          content: '<div class="form-row"><label class="field"><span>批次名称</span><input class="input" name="name" required></label><label class="field"><span>学年</span><input class="input" name="academic_year" placeholder="2026-2027" required></label><label class="field"><span>学期</span><input class="input" name="term" required></label></div><div class="form-row"><label class="field"><span>学生开始</span><input class="input" type="datetime-local" name="student_apply_start" required></label><label class="field"><span>学生截止</span><input class="input" type="datetime-local" name="student_apply_end" required></label></div><div class="form-row"><label class="field"><span>导师开始</span><input class="input" type="datetime-local" name="mentor_select_start" required></label><label class="field"><span>导师截止</span><input class="input" type="datetime-local" name="mentor_select_end" required></label></div><label class="field"><span>主选发布时间</span><input class="input" type="datetime-local" name="main_publish_at" required></label><div class="form-row"><label class="field"><span>补录学生开始</span><input class="input" type="datetime-local" name="supplement_student_start" required></label><label class="field"><span>补录学生截止</span><input class="input" type="datetime-local" name="supplement_student_end" required></label></div><div class="form-row"><label class="field"><span>补录导师开始</span><input class="input" type="datetime-local" name="supplement_mentor_start" required></label><label class="field"><span>补录导师截止</span><input class="input" type="datetime-local" name="supplement_mentor_end" required></label></div><label class="field"><span>补录发布时间</span><input class="input" type="datetime-local" name="supplement_publish_at" required></label>',
          onSubmit: async function (data) {
            const body = { name: data.get("name"), academic_year: data.get("academic_year"), term: data.get("term"), student_apply_start: new Date(data.get("student_apply_start")).toISOString(), student_apply_end: new Date(data.get("student_apply_end")).toISOString(), mentor_select_start: new Date(data.get("mentor_select_start")).toISOString(), mentor_select_end: new Date(data.get("mentor_select_end")).toISOString(), main_publish_at: new Date(data.get("main_publish_at")).toISOString(), supplement_student_start: new Date(data.get("supplement_student_start")).toISOString(), supplement_student_end: new Date(data.get("supplement_student_end")).toISOString(), supplement_mentor_start: new Date(data.get("supplement_mentor_start")).toISOString(), supplement_mentor_end: new Date(data.get("supplement_mentor_end")).toISOString(), supplement_publish_at: new Date(data.get("supplement_publish_at")).toISOString() };
            await api("/api/v1/mentor-selection/batches", { method: "POST", body: JSON.stringify(body) });
            toast("双选批次已创建");
            await renderMentorSelection(pageRoot, context);
          },
        });
      });
      return;
    }
    pageRoot.innerHTML += '<div class="mentor-workbench"><div class="mentor-summary-slot"></div><section class="mentor-main-panel" aria-label="双选主任务"></section><aside class="mentor-side-panel" aria-label="双选辅助信息"></aside></div>';
    const workbench = pageRoot.querySelector(".mentor-workbench");
    const mainPanel = workbench.querySelector(".mentor-main-panel");
    const sidePanel = workbench.querySelector(".mentor-side-panel");
    workbench.querySelector(".mentor-summary-slot").innerHTML = batchHeader(current);
    sidePanel.innerHTML = mentorContextPanel(current);
    if (context.user.role === "student") await studentView(workbench, current, context);
    if (context.user.role === "teacher") await teacherView(mainPanel, current, context);
    if (context.user.role === "admin") await adminView(mainPanel, current, context);
  } catch (error) {
    pageRoot.innerHTML += emptyState("加载失败", error.message);
  }
}
