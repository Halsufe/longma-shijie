import { api } from "./api.js";
import { clearAuth, navigate, setAuth, setCurrentUser, state } from "./state.js";
import { icon, toast } from "./ui.js";
import { renderOverview } from "./views/overview.js?v=20260818-workbench";
import { renderChat } from "./views/chat.js?v=20260807-frontend-revamp2";
import { renderKnowledge } from "./views/knowledge.js?v=20260807-frontend-revamp2";
import { renderCourses } from "./views/courses.js?v=20260807-frontend-revamp2";
import { renderCommunity } from "./views/community.js?v=20260807-achievement-groups";
import { renderMentorship } from "./views/mentorship.js?v=20260818-workbench";
import { renderNotifications } from "./views/notifications.js?v=20260807-frontend-revamp2";
import { renderProfile } from "./views/profile.js?v=20260807-frontend-revamp2";
import { renderAdmin } from "./views/admin.js?v=20260807-frontend-revamp2";
import { renderParty } from "./views/party.js?v=20260818-workbench";

const app = document.getElementById("app");
// Backend-hosted compatibility asset path: /static/assets/院徽.jpg
let currentCleanup = null;

const ROUTES = {
  overview: { label: "工作台", icon: "overview", render: renderOverview },
  chat: { label: "AI 对话", icon: "chat", render: renderChat },
  knowledge: { label: "知识库", icon: "library", render: renderKnowledge },
  courses: { label: "课程与作业", icon: "calendar", render: renderCourses },
  community: { label: "成果与社区", icon: "trophy", render: renderCommunity },
  mentorship: { label: "导师双选", icon: "users", render: renderMentorship },
  party: { label: "党建", icon: "flag", render: renderParty, roles: ["student", "admin"] },
  notifications: { label: "通知中心", icon: "bell", render: renderNotifications },
  profile: { label: "个人设置", icon: "settings", render: renderProfile },
  admin: { label: "管理后台", icon: "shield", render: renderAdmin, admin: true },
};

function roleLabel(role) {
  return { student: "在校学生", alumni: "校友", teacher: "教师", admin: "管理员" }[role] || role;
}

function renderLogin() {
  app.innerHTML = `
    <main class="login-shell">
      <div class="login-card">
        <section class="login-panel">
          <div class="login-form-wrap">
            <div class="brand-lockup">
              <img src="./assets/院徽.jpg" alt="中央财经大学管理科学与工程学院院徽">
              <div><strong>龙马·视界</strong><span>CampusMate 智慧学习协作平台</span></div>
            </div>
            <div class="login-heading">
              <h2>登录平台</h2>
              <p>使用管理员分配的学号或工号进入系统。</p>
            </div>
            <form id="login-form" class="form-stack">
              <label class="field"><span>学号 / 工号</span><input class="input" name="student_no" autocomplete="username" maxlength="50" required></label>
              <label class="field"><span>密码</span><span class="password-field"><input class="input" type="password" name="password" autocomplete="current-password" maxlength="128" required><button class="password-toggle" type="button" aria-label="显示密码">${icon("eye")}</button></span></label>
              <button class="button button-primary button-full" type="submit">登录</button>
            </form>
            <p class="login-note">首次登录需按提示修改初始密码。遇到账号问题请联系系统管理员。</p>
          </div>
        </section>
        <section class="login-brand" aria-label="平台寄语">
          <blockquote class="brand-message">
            <span class="quote-mark quote-open" aria-hidden="true">“</span>
            <p>把知识、课程<br>与成长，放进<br>同一个视界。</p>
            <span class="quote-mark quote-close" aria-hidden="true">”</span>
          </blockquote>
        </section>
      </div>
    </main>`;

  const form = document.getElementById("login-form");
  const passwordInput = form.elements.password;
  form.querySelector(".password-toggle").addEventListener("click", () => {
    passwordInput.type = passwordInput.type === "password" ? "text" : "password";
  });
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    button.textContent = "正在登录...";
    try {
      const payload = Object.fromEntries(new FormData(form));
      const result = await api("/api/v1/auth/login", { method: "POST", body: JSON.stringify(payload) });
      setAuth(result);
      if (result.user.status === "pending_change") {
        await renderShell();
      } else {
        const user = await api("/api/v1/users/me");
        setCurrentUser(user);
        navigate("overview");
        await renderShell();
      }
    } catch (error) {
      toast(error.message, "danger");
      button.disabled = false;
      button.textContent = "登录";
    }
  });
}

function renderRequiredPasswordChange() {
  // Keep the gate and its entered values intact if another render is triggered.
  if (app.querySelector("#required-password-form")) return;

  app.innerHTML = `
    <main class="login-shell">
      <div class="login-card">
        <section class="login-panel">
          <div class="login-form-wrap">
            <div class="brand-lockup">
              <img src="./assets/院徽.jpg" alt="中央财经大学管理科学与工程学院院徽">
              <div><strong>龙马·视界</strong><span>CampusMate 智慧学习协作平台</span></div>
            </div>
            <div class="login-heading">
              <h2>请修改初始密码</h2>
              <p>账号 ${state.user?.student_no || ""} 首次登录后才能进入平台。</p>
            </div>
            <form id="required-password-form" class="form-stack">
              <label class="field"><span>当前初始密码</span><input class="input" name="old_password" type="password" autocomplete="current-password" required></label>
              <label class="field"><span>新密码</span><input class="input" name="new_password" type="password" autocomplete="new-password" minlength="8" required></label>
              <label class="field"><span>确认新密码</span><input class="input" name="confirm_password" type="password" autocomplete="new-password" minlength="8" required></label>
              <p class="login-note" id="required-password-error" role="alert" hidden></p>
              <button class="button button-primary button-full" type="submit">完成修改</button>
            </form>
          </div>
        </section>
        <section class="login-brand" aria-label="平台寄语">
          <blockquote class="brand-message">
            <span class="quote-mark quote-open" aria-hidden="true">“</span>
            <p>把知识、课程<br>与成长，放进<br>同一个视界。</p>
            <span class="quote-mark quote-close" aria-hidden="true">”</span>
          </blockquote>
        </section>
      </div>
    </main>`;

  const form = document.getElementById("required-password-form");
  const errorNode = document.getElementById("required-password-error");
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const data = new FormData(form);
    const button = form.querySelector("button[type=submit]");
    errorNode.hidden = true;
    errorNode.textContent = "";

    if (data.get("new_password") !== data.get("confirm_password")) {
      errorNode.textContent = "两次输入的新密码不一致";
      errorNode.hidden = false;
      return;
    }

    button.disabled = true;
    button.textContent = "正在修改...";
    try {
      await api("/api/v1/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ old_password: data.get("old_password"), new_password: data.get("new_password") }),
      });
      const user = await api("/api/v1/users/me");
      setCurrentUser(user);
      toast("密码修改成功");
      navigate("overview");
      await renderShell();
    } catch (error) {
      errorNode.textContent = error.message || "密码修改失败，请重试";
      errorNode.hidden = false;
      button.disabled = false;
      button.textContent = "完成修改";
    }
  });
}

function navItems() {
  return Object.entries(ROUTES)
    .filter(([, route]) => (!route.admin || state.user?.role === "admin") && (!route.roles || route.roles.includes(state.user?.role)))
    .map(([key, route]) => `
      ${key === "admin" ? '<div class="nav-divider">管理</div>' : ""}
      <button class="nav-item ${state.route === key ? "active" : ""}" data-route="${key}">
        ${icon(route.icon)}<span>${route.label}</span>
        ${key === "notifications" && state.unreadCount ? `<span class="nav-badge">${state.unreadCount > 99 ? "99+" : state.unreadCount}</span>` : ""}
      </button>`).join("");
}

async function updateUnreadCount() {
  try {
    const result = await api("/api/v1/notifications/unread-count");
    state.unreadCount = result.unread_count || 0;
  } catch {
    state.unreadCount = 0;
  }
}

async function renderShell() {
  if (!state.user) return renderLogin();
  if (state.user.status === "pending_change") {
    if (currentCleanup) {
      currentCleanup();
      currentCleanup = null;
    }
    return renderRequiredPasswordChange();
  }
  if (currentCleanup) {
    currentCleanup();
    currentCleanup = null;
  }
  let routeKey = state.route;
  if (!ROUTES[routeKey] || (ROUTES[routeKey].admin && state.user.role !== "admin") || (ROUTES[routeKey].roles && !ROUTES[routeKey].roles.includes(state.user.role))) routeKey = "overview";
  state.route = routeKey;
  const route = ROUTES[routeKey];
  const initial = (state.user.name || state.user.student_no || "用").slice(0, 1);
  const today = new Intl.DateTimeFormat("zh-CN", { timeZone: "Asia/Shanghai", month: "long", day: "numeric", weekday: "long" }).format(new Date());

  app.innerHTML = `
    <div class="app-shell">
      <aside id="app-sidebar" class="sidebar ${state.sidebarOpen ? "open" : ""}">
        <div class="sidebar-brand"><img src="./assets/院徽.jpg" alt="中央财经大学管理科学与工程学院院徽"><div><strong>龙马·视界</strong><span>大数据管理与应用</span></div></div>
        <nav class="sidebar-nav" aria-label="主导航">${navItems()}</nav>
        <div class="sidebar-footer">
          <div class="user-mini"><span class="avatar">${initial}</span><div><strong>${state.user.name || state.user.student_no}</strong><span>${roleLabel(state.user.role)}</span></div><button class="icon-button logout-button" id="logout-button" aria-label="退出登录">${icon("logout")}</button></div>
        </div>
      </aside>
      <button class="sidebar-scrim ${state.sidebarOpen ? "open" : ""}" aria-label="关闭菜单"></button>
      <header class="topbar">
        <button class="icon-button mobile-menu" aria-label="打开菜单" aria-controls="app-sidebar" aria-expanded="${state.sidebarOpen}">${icon("menu")}</button>
        <span class="topbar-title">${route.label}</span>
        <span class="topbar-spacer"></span>
        <span class="topbar-date">${today}</span>
        <button class="icon-button" data-route="notifications" aria-label="通知中心">${icon("bell")}</button>
      </header>
      <main class="main-content"><div id="view-root" class="view-root"></div></main>
    </div>`;

  const closeSidebar = ({ restoreFocus = true } = {}) => {
    state.sidebarOpen = false;
    document.body.classList.remove("drawer-open");
    app.querySelector(".mobile-menu")?.setAttribute("aria-expanded", "false");
    app.querySelector(".sidebar")?.classList.remove("open");
    app.querySelector(".sidebar-scrim")?.classList.remove("open");
    if (restoreFocus) app.querySelector(".mobile-menu")?.focus();
  };
  app.querySelectorAll("[data-route]").forEach(node => node.addEventListener("click", () => {
    closeSidebar({ restoreFocus: false });
    navigate(node.dataset.route);
  }));
  app.querySelector(".mobile-menu").addEventListener("click", () => {
    state.sidebarOpen = true;
    document.body.classList.add("drawer-open");
    app.querySelector(".mobile-menu")?.setAttribute("aria-expanded", "true");
    app.querySelector(".sidebar").classList.add("open");
    app.querySelector(".sidebar-scrim").classList.add("open");
  });
  app.querySelector(".sidebar-scrim").addEventListener("click", closeSidebar);
  const onShellKeydown = event => {
    if (event.key === "Escape" && state.sidebarOpen) closeSidebar();
  };
  document.addEventListener("keydown", onShellKeydown);
  app.querySelector("#logout-button").addEventListener("click", async () => {
    try { await api("/api/v1/auth/logout", { method: "POST" }); } catch { /* local logout still applies */ }
    clearAuth();
    location.hash = "";
    renderLogin();
  });

  const cleanup = await route.render(document.getElementById("view-root"), { navigate, refresh: renderShell, user: state.user });
  currentCleanup = () => {
    document.removeEventListener("keydown", onShellKeydown);
    document.body.classList.remove("drawer-open");
    if (typeof cleanup === "function") cleanup();
  };
  updateUnreadCount().then(() => {
    const badge = app.querySelector('.nav-item[data-route="notifications"] .nav-badge');
    if (badge) badge.textContent = state.unreadCount;
  });
}

async function bootstrap() {
  if (!state.accessToken || !state.user) return renderLogin();
  if (state.user.status === "pending_change") {
    return renderShell();
  }
  try {
    const user = await api("/api/v1/users/me");
    setCurrentUser(user);
    await updateUnreadCount();
    await renderShell();
  } catch {
    clearAuth();
    renderLogin();
  }
}

window.addEventListener("hashchange", () => {
  state.route = location.hash.slice(1) || "overview";
  renderShell();
});

bootstrap();
