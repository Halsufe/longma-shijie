import { api, qs } from "../api.js";
import { emptyState, escapeHtml, formatDate, icon, loadingState, pageHeader, toast } from "../ui.js";

const REF_ROUTES = { assignment: "courses", course: "courses", achievement: "community", resource: "community", party: "party" };

export async function renderNotifications(container, context) {
  let filter = "all";
  let result = { total: 0, unread_count: 0, items: [] };
  container.innerHTML = pageHeader("通知中心", "集中查看作业、批改和系统消息。") + loadingState();

  async function load() {
    result = await api(`/api/v1/notifications${qs({ page_size: 100, is_read: filter === "all" ? null : filter === "read" })}`);
  }

  function draw() {
    container.innerHTML = `
      ${pageHeader("通知中心", `共 ${result.total} 条通知，${result.unread_count} 条未读。`, result.unread_count ? `<button class="button button-secondary" id="read-all">${icon("check")} 全部已读</button>` : "")}
      <div class="toolbar"><div class="segmented"><button class="segment ${filter === "all" ? "active" : ""}" data-filter="all">全部</button><button class="segment ${filter === "unread" ? "active" : ""}" data-filter="unread">未读</button><button class="segment ${filter === "read" ? "active" : ""}" data-filter="read">已读</button></div></div>
      <section class="notification-list">${result.items.length ? result.items.map(item => {
        const route = REF_ROUTES[item.ref_type];
        return `<article class="list-row notification-row ${item.is_read ? "" : "unread"}" ${route ? `data-notification-route="${route}" role="link" tabindex="0"` : ""}><span class="quick-item-icon">${icon(item.type === "assignment" ? "file" : "bell")}</span><div class="list-row-main"><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.content)}</p><div class="list-row-meta"><span>${formatDate(item.created_at)}</span><span>${escapeHtml(item.type)}</span></div></div>${item.is_read ? "" : `<button class="button button-secondary button-small" data-read="${item.id}">标为已读</button>`}</article>`;
      }).join("") : emptyState("没有通知", filter === "unread" ? "目前没有未读消息。" : "新的作业和系统消息会显示在这里。")}</section>`;
    bind();
  }

  function bind() {
    container.querySelectorAll("[data-filter]").forEach(node => node.addEventListener("click", async () => { filter = node.dataset.filter; await load(); draw(); }));
    container.querySelector("#read-all")?.addEventListener("click", async () => { await api("/api/v1/notifications/read-all", { method: "PUT" }); await load(); draw(); await context?.refresh?.(); toast("已全部标记为已读"); });
    container.querySelectorAll("[data-read]").forEach(node => node.addEventListener("click", async () => { await api(`/api/v1/notifications/${node.dataset.read}/read`, { method: "PUT" }); await load(); draw(); await context?.refresh?.(); }));
    container.querySelectorAll("[data-notification-route]").forEach(node => {
      const open = () => context?.navigate(node.dataset.notificationRoute);
      node.addEventListener("click", event => { if (!event.target.closest("button")) open(); });
      node.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); } });
    });
  }

  try { await load(); draw(); } catch (error) { container.innerHTML = pageHeader("通知中心", "集中查看作业、批改和系统消息。") + emptyState("加载失败", error.message); }
}
