import { api, qs } from "../api.js";
import { emptyState, escapeHtml, icon, loadingState, pageHeader } from "../ui.js";

export async function renderAnnouncements(container) {
  let page = 1;
  let filters = { keyword: "", source_id: "", published_from: "", published_to: "" };
  let sources = [];
  let payload = { items: [], total: 0, page_size: 20 };
  let error = "";
  let sourceError = "";

  async function load() {
    error = "";
    sourceError = "";
    container.innerHTML = pageHeader("学校公告", "汇总校内公开通知，支持按来源与日期检索。") + loadingState("正在加载学校公告");
    const [sourceResult, listResult] = await Promise.allSettled([
      sources.length ? Promise.resolve(sources) : api("/api/v1/school-announcements/sources"),
      api(`/api/v1/school-announcements${qs({ ...filters, page, page_size: 20 })}`),
    ]);
    if (sourceResult.status === "fulfilled") {
      sources = Array.isArray(sourceResult.value) ? sourceResult.value : [];
    } else {
      sourceError = sourceResult.reason?.message || "来源加载失败";
    }
    if (listResult.status === "fulfilled") {
      payload = listResult.value;
    } else {
      error = listResult.reason?.message || "公告加载失败";
    }
  }

  function draw() {
    const items = Array.isArray(payload.items) ? payload.items : [];
    const totalPages = Math.max(1, Math.ceil(Number(payload.total || 0) / Number(payload.page_size || 20)));
    container.innerHTML = `${pageHeader("学校公告", "汇总校内公开通知，支持按来源与日期检索。")}
      <form class="toolbar announcement-toolbar" id="announcement-filter">
        <div class="search-box">${icon("search")}<input class="input" name="keyword" value="${escapeHtml(filters.keyword)}" placeholder="搜索标题或摘要"></div>
        <select class="select" name="source_id" title="${escapeHtml(sourceError)}"><option value="">${sourceError ? "来源加载失败" : "全部来源"}</option>${sources.map(source => `<option value="${source.id}" ${String(source.id) === filters.source_id ? "selected" : ""}>${escapeHtml(source.name)}</option>`).join("")}</select>
        <label class="compact-date"><span>开始</span><input class="input" type="date" name="published_from" value="${escapeHtml(filters.published_from)}" aria-label="开始日期"></label>
        <label class="compact-date"><span>结束</span><input class="input" type="date" name="published_to" value="${escapeHtml(filters.published_to)}" aria-label="结束日期"></label>
        <button class="button button-primary" type="submit">${icon("search")} 查询</button>
      </form>
      <section class="panel panel-flush">
        <div class="panel-header"><div><h2>公告列表</h2><p>共 ${Number(payload.total || 0)} 条</p></div><button class="button button-ghost button-small" id="announcement-refresh" type="button">刷新</button></div>
        <div class="panel-body">${error ? `<div class="state-panel state-error" role="alert"><h3>公告加载失败</h3><p>${escapeHtml(error)}</p></div>` : items.length ? `<div class="quick-list">${items.map(item => `<a class="quick-item" href="${escapeHtml(item.original_url || "#")}" target="_blank" rel="noopener"><span class="quick-item-icon">${icon("file")}</span><span><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.summary_text || "暂无摘要")}</span><span>${escapeHtml(item.published_at || "")}</span></span>${icon("arrow")}</a>`).join("")}</div>` : emptyState("暂无学校公告", "采集任务发现新公告后会显示在这里。")}</div>
        <div class="panel-header"><p>第 ${page} / ${totalPages} 页</p><div class="page-actions"><button class="button button-secondary button-small" id="announcement-prev" ${page <= 1 ? "disabled" : ""}>上一页</button><button class="button button-secondary button-small" id="announcement-next" ${page >= totalPages ? "disabled" : ""}>下一页</button></div></div>
      </section>`;
    container.querySelector("#announcement-filter").addEventListener("submit", async event => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      filters = Object.fromEntries(["keyword", "source_id", "published_from", "published_to"].map(key => [key, String(data.get(key) || "")]));
      page = 1;
      await load(); draw();
    });
    container.querySelector("#announcement-refresh").addEventListener("click", async () => { await load(); draw(); });
    container.querySelector("#announcement-prev")?.addEventListener("click", async () => { page -= 1; await load(); draw(); });
    container.querySelector("#announcement-next")?.addEventListener("click", async () => { page += 1; await load(); draw(); });
  }

  await load();
  draw();
}
