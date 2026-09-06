import { api } from "../api.js";
import { confirmAction, emptyState, escapeHtml, formatDate, icon, loadingState, pageHeader, showModal, statusBadge, toast } from "../ui.js";
import { setCurrentUser } from "../state.js";

export async function renderProfile(container, context) {
  let user = context.user;
  let sessions = [];
  let political = null;
  container.innerHTML = pageHeader("个人设置", "维护个人资料、密码和登录设备。") + loadingState();

  async function load() {
    const [userResult, sessionResult] = await Promise.all([api("/api/v1/users/me"), api("/api/v1/users/me/sessions")]);
    user = userResult;
    sessions = sessionResult.items;
    political = user.role === "student" ? await api("/api/v1/party/political-status/mine") : null;
    setCurrentUser(user);
  }

  function draw() {
    const profile = user.profile || {};
    container.innerHTML = `
      ${pageHeader("个人设置", "维护个人资料、密码和登录设备。", `${user.role === "student" ? `<button class="button button-secondary" id="alumni-request">申请转为校友</button>` : ""}<button class="button button-secondary" id="change-password">修改密码</button><button class="button button-primary" id="edit-profile">${icon("edit")} 编辑资料</button>`)}
      <div class="profile-layout">
        <aside class="panel profile-summary"><span class="avatar large">${escapeHtml((user.name || user.student_no).slice(0,1))}</span><h2>${escapeHtml(user.name)}</h2><p>${escapeHtml(user.student_no)}</p>${statusBadge(user.status)}<div class="profile-facts"><div class="profile-fact"><span>角色</span><strong>${escapeHtml({ student:"在校学生", alumni:"校友", teacher:"教师", admin:"管理员" }[user.role] || user.role)}</strong></div><div class="profile-fact"><span>专业</span><strong>${escapeHtml(profile.major || "未填写")}</strong></div><div class="profile-fact"><span>研究方向</span><strong>${escapeHtml(profile.research || profile.field || "未填写")}</strong></div>${user.role === "alumni" ? `<div class="profile-fact"><span>毕业年份</span><strong>${user.graduation_year || "未填写"}</strong></div>` : ""}<div class="profile-fact"><span>最近活跃</span><strong>${formatDate(user.last_active_at)}</strong></div></div></aside>
        <div style="display:grid;gap:18px">
          ${user.role === "student" ? `<section class="panel"><div class="panel-header"><div><h2>政治面貌</h2><p>提交后由管理员审核生效</p></div><button class="button button-secondary button-small" id="edit-political-status">${icon("edit")} 设置</button></div><div class="panel-body"><strong>${escapeHtml(political?.political_status || user.political_status || "群众")}</strong>${political?.latest_review ? `<p class="muted">最近申请：${escapeHtml(political.latest_review.to_status)} · ${escapeHtml(political.latest_review.status)}</p>` : ""}</div></section>` : ""}
          <section class="panel"><div class="panel-header"><div><h2>能力与方向</h2><p>用于教师和资源推荐</p></div></div><div class="panel-body"><div class="field"><span>兴趣领域</span><p>${escapeHtml((profile.interests || []).join("、") || "未填写")}</p></div><div class="field"><span>未来发展规划</span><p>${escapeHtml(profile.development_plan || "未填写")}</p></div><div class="field"><span>年级</span><p>${escapeHtml(profile.grade || "未填写")}</p></div><div class="field"><span>个人简介</span><p>${escapeHtml(profile.bio || "暂未填写个人简介")}</p></div><div class="field"><span>技能标签</span><div class="tag-list">${(profile.skills || []).length ? profile.skills.map(item => `<span class="tag">${escapeHtml(item)}</span>`).join("") : '<span class="muted">暂未填写</span>'}</div></div></div></section>
          ${user.role === "student" ? `<section class="panel"><div class="panel-header"><div><h2>双选档案</h2><p>正式提交志愿前至少填写 3 门课程成绩</p></div></div><div class="panel-body"><div class="form-row"><div class="field"><span>手机号</span><p>${escapeHtml(profile.phone || "未填写")}</p></div><div class="field"><span>邮箱</span><p>${escapeHtml(profile.email || "未填写")}</p></div></div><div class="field"><span>课程成绩</span>${(profile.course_grades || []).length ? `<div class="application-list">${profile.course_grades.map(item => `<div class="list-row"><div class="list-row-main"><strong>${escapeHtml(item.course_name)}</strong><p>${escapeHtml(item.score)}${item.remark ? ` · ${escapeHtml(item.remark)}` : ""}</p></div></div>`).join("")}</div>` : '<p class="muted">暂未填写</p>'}</div></div></section>` : ""}
          <section class="panel"><div class="panel-header"><div><h2>登录设备</h2><p>撤销后对应设备需要重新登录</p></div></div><div class="panel-body">${sessions.length ? sessions.map(session => `<div class="session-row"><span class="quick-item-icon">${icon("shield")}</span><div class="session-row-main"><strong>${escapeHtml(session.device_name || "未知设备")} ${session.is_current ? '<span class="badge badge-success">当前设备</span>' : ""}</strong><span>${escapeHtml(session.ip || "未知 IP")} · 最近活跃 ${formatDate(session.last_active_at)}</span></div>${session.is_current ? "" : `<button class="button button-danger button-small" data-revoke="${session.id}">下线</button>`}</div>`).join("") : emptyState("没有活跃设备", "当前没有可管理的登录会话。")}</div></section>
        </div>
      </div>`;
    bind();
  }

  function editProfile() {
    const profile = user.profile || {};
    showModal({ title: "编辑个人资料", submitText: "保存", size: "wide", content: `<div class="form-row"><label class="field"><span>姓名</span><input class="input" name="name" value="${escapeHtml(user.name)}" required></label><label class="field"><span>专业</span><input class="input" name="major" value="${escapeHtml(profile.major || "")}"></label></div><label class="field"><span>兴趣领域</span><input class="input" name="interests" value="${escapeHtml((profile.interests || []).join(", "))}" maxlength="1000"></label><label class="field"><span>未来发展规划</span><textarea class="textarea" name="development_plan" maxlength="2000">${escapeHtml(profile.development_plan || "")}</textarea></label><label class="field"><span>年级</span><input class="input" name="grade" value="${escapeHtml(profile.grade || "")}" maxlength="30"></label><label class="field"><span>研究方向</span><input class="input" name="research" value="${escapeHtml(profile.research || profile.field || "")}"></label><label class="field"><span>技能标签</span><input class="input" name="skills" value="${escapeHtml((profile.skills || []).join(", "))}" placeholder="Python, 数据分析, 机器学习"></label><label class="field"><span>个人简介</span><textarea class="textarea" name="bio">${escapeHtml(profile.bio || "")}</textarea></label>${user.role === "student" ? `<div class="form-row"><label class="field"><span>手机号</span><input class="input" name="phone" value="${escapeHtml(profile.phone || "")}"></label><label class="field"><span>邮箱</span><input class="input" name="email" value="${escapeHtml(profile.email || "")}"></label></div><label class="field"><span>课程成绩</span><textarea class="textarea" name="course_grades" placeholder="每行：课程名称 | 成绩 | 备注">${escapeHtml((profile.course_grades || []).map(item => [item.course_name, item.score, item.remark || ""].join(" | ")).join("\n"))}</textarea></label>` : ""}`, onSubmit: async data => {
      const courseGrades = data.get("course_grades") ? data.get("course_grades").split("\n").map(value => value.split("|").map(part => part.trim())).filter(parts => parts[0] && parts[1]).map(parts => ({ course_name: parts[0], score: parts[1], remark: parts[2] || "" })) : (profile.course_grades || []);
      const body = { name: data.get("name"), profile: { ...profile, major: data.get("major") || null, interests: data.get("interests").split(/[,，/]/).map(value => value.trim()).filter(Boolean), development_plan: data.get("development_plan") || null, grade: data.get("grade") || null, research: data.get("research") || null, skills: data.get("skills").split(/[,，]/).map(value => value.trim()).filter(Boolean), bio: data.get("bio") || null, phone: data.get("phone") || profile.phone || null, email: data.get("email") || profile.email || null, course_grades: courseGrades } };
      user = await api("/api/v1/users/me", { method: "PUT", body: JSON.stringify(body) });
      setCurrentUser(user); draw(); toast("个人资料已更新");
    }});
  }

  function changePassword() {
    showModal({ title: "修改密码", submitText: "修改", content: `<label class="field"><span>当前密码</span><input class="input" name="old_password" type="password" required></label><label class="field"><span>新密码</span><input class="input" name="new_password" type="password" minlength="8" required></label><label class="field"><span>确认新密码</span><input class="input" name="confirm_password" type="password" minlength="8" required></label>`, onSubmit: async data => { if (data.get("new_password") !== data.get("confirm_password")) throw new Error("两次输入的新密码不一致"); await api("/api/v1/auth/change-password", { method: "POST", body: JSON.stringify({ old_password: data.get("old_password"), new_password: data.get("new_password") }) }); toast("密码已修改，其他设备已下线"); await load(); draw(); } });
  }

  function editPoliticalStatus() {
    const current = political?.political_status || user.political_status || "群众";
    showModal({
      title: "设置政治面貌",
      submitText: "提交审核",
      content: `<label class="field"><span>政治面貌</span><select class="select" name="to_status" required><option value="共青团员" ${current === "共青团员" ? "selected" : ""}>共青团员</option><option value="群众" ${current === "群众" ? "selected" : ""}>群众</option></select></label><label class="field"><span>说明</span><textarea class="textarea" name="remark" maxlength="1000" placeholder="可填写补充说明"></textarea></label>`,
      onSubmit: async data => {
        await api("/api/v1/party/political-status/mine", { method: "POST", body: JSON.stringify({ to_status: data.get("to_status"), remark: data.get("remark") || null }) });
        await load(); draw(); toast("政治面貌申请已提交");
      },
    });
  }

  function bind() {
    container.querySelector("#edit-profile")?.addEventListener("click", editProfile);
    container.querySelector("#change-password")?.addEventListener("click", changePassword);
    container.querySelector("#alumni-request")?.addEventListener("click", () => showModal({ title: "申请转为校友", submitText: "提交申请", content: '<label class="field"><span>毕业年份</span><input class="input" name="graduation_year" type="number" min="1950" max="2100" required></label>', onSubmit: async data => { await api("/api/v1/users/me/alumni-request", { method: "POST", body: JSON.stringify({ graduation_year: Number(data.get("graduation_year")) }) }); toast("申请已提交"); await load(); draw(); } }));
    container.querySelector("#edit-political-status")?.addEventListener("click", editPoliticalStatus);
    container.querySelectorAll("[data-revoke]").forEach(node => node.addEventListener("click", () => confirmAction("确认让这个设备下线？", async () => { await api(`/api/v1/users/me/sessions/${node.dataset.revoke}`, { method: "DELETE" }); await load(); draw(); toast("设备会话已撤销"); }, "下线")));
  }

  try { await load(); draw(); } catch (error) { container.innerHTML = pageHeader("个人设置", "维护个人资料、密码和登录设备。") + emptyState("加载失败", error.message); }
}
