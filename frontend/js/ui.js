const ICONS = {
  overview: '<path d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"/>',
  chat: '<path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z"/>',
  library: '<path d="m4 19.5 8-4.5 8 4.5M4 4.5 12 9l8-4.5M4 4.5v15M20 4.5v15M12 9v6"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
  trophy: '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0zM7 6H4v2a4 4 0 0 0 4 4M17 6h3v2a4 4 0 0 1-4 4"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06-2.83 2.83-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21h-4v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06-2.83-2.83.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3v-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06 2.83-2.83.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3h4v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06 2.83 2.83-.06.06A1.65 1.65 0 0 0 19.4 9c.12.6.64 1.02 1.25 1.02H21v4h-.35c-.61 0-1.13.42-1.25 1Z"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/>',
  flag: '<path d="M5 22V4M5 4c5-3 9 3 14 0v10c-5 3-9-3-14 0"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  close: '<path d="M18 6 6 18M6 6l12 12"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  edit: '<path d="M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z"/>',
  trash: '<path d="M3 6h18M8 6V4h8v2M19 6l-1 15H6L5 6M10 11v6M14 11v6"/>',
  check: '<path d="m20 6-11 11-5-5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  heart: '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78L12 21.23l8.84-8.84a5.5 5.5 0 0 0 0-7.78Z"/>',
  bookmark: '<path d="M6 3h12v18l-6-4-6 4Z"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  sparkles: '<path d="m12 3-1.5 3.5L7 8l3.5 1.5L12 13l1.5-3.5L17 8l-3.5-1.5ZM5 14l-1 2.5L1.5 18 4 19.5 5 22l1-2.5L8.5 18 6 16.5ZM19 14l-1 2.5-2.5 1.5 2.5 1.5L19 22l1-2.5 2.5-1.5-2.5-1.5Z"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
};

let activeModalClose = null;

export function icon(name, size = 18) {
  return `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.file}</svg>`;
}

export function escapeHtml(value = "") {
  return String(value).replace(/[&<>"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char]));
}

export function formatDate(value, withTime = true) {
  if (!value) return "未设置";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

export function formatBytes(bytes = 0) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
}

export function statusBadge(status) {
  const map = {
    active: ["正常", "success"], disabled: ["已禁用", "danger"], pending_change: ["待改密", "warning"],
    pending: ["待处理", "warning"], approved: ["已通过", "success"], rejected: ["已拒绝", "danger"],
    published: ["已发布", "success"], draft: ["草稿", "muted"], withdrawn: ["已撤回", "danger"],
    submitted: ["已提交", "info"], graded: ["已批改", "success"], ready: ["已解析", "success"],
    processing: ["解析中", "info"], failed: ["失败", "danger"], accepted: ["已接受", "success"],
  };
  const [label, tone] = map[status] || [status || "未知", "muted"];
  return `<span class="badge badge-${tone}" data-status="${escapeHtml(status || "unknown")}"><span class="badge-dot" aria-hidden="true"></span>${escapeHtml(label)}</span>`;
}

export function toast(message, tone = "success") {
  const region = document.getElementById("toast-region");
  if (!region) return;
  const normalizedTone = ["success", "info", "warning", "danger"].includes(tone) ? tone : "info";
  const node = document.createElement("div");
  node.className = `toast toast-${normalizedTone}`;
  node.dataset.tone = normalizedTone;
  node.setAttribute("role", normalizedTone === "danger" ? "alert" : "status");
  node.setAttribute("aria-live", normalizedTone === "danger" ? "assertive" : "polite");
  const marker = document.createElement("span");
  marker.className = "toast-marker";
  marker.setAttribute("aria-hidden", "true");
  const copy = document.createElement("span");
  copy.className = "toast-copy";
  copy.textContent = String(message);
  node.append(marker, copy);
  region.appendChild(node);
  requestAnimationFrame(() => node.classList.add("show"));
  setTimeout(() => {
    node.classList.remove("show");
    setTimeout(() => node.remove(), 180);
  }, 3200);
}

export function showModal({ title, content, submitText = "确认", size = "normal", onSubmit }) {
  const root = document.getElementById("modal-root");
  if (!root) throw new Error("缺少弹窗挂载点");
  activeModalClose?.(false);
  const normalizedSize = size === "wide" ? "wide" : "normal";
  const previouslyFocused = document.activeElement;
  root.innerHTML = `
    <div class="modal-backdrop" data-modal-close>
      <section class="modal modal-${normalizedSize}" data-modal-size="${normalizedSize}" role="dialog" aria-modal="true" aria-labelledby="modal-title" aria-describedby="modal-error">
        <header class="modal-header">
          <h2 id="modal-title">${escapeHtml(title)}</h2>
          <button class="icon-button" type="button" data-modal-close aria-label="关闭弹窗" title="关闭弹窗">${icon("close")}</button>
        </header>
        <form class="modal-form">
          <div class="modal-content">${content}</div>
          <p class="modal-error" id="modal-error" role="alert" hidden></p>
          <footer class="modal-footer">
            <button class="button button-ghost" type="button" data-modal-close>取消</button>
            <button class="button button-primary" type="submit">${escapeHtml(submitText)}</button>
          </footer>
        </form>
      </section>
    </div>`;
  const dialog = root.querySelector("[role=dialog]");
  const focusableSelector = "button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), a[href], [tabindex]:not([tabindex='-1'])";
  const close = (restoreFocus = true) => {
    document.removeEventListener("keydown", handleKeydown);
    if (activeModalClose !== close) return;
    document.body.classList.remove("modal-open");
    root.innerHTML = "";
    activeModalClose = null;
    if (restoreFocus) previouslyFocused?.focus?.();
  };
  const handleKeydown = event => {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = [...dialog.querySelectorAll(focusableSelector)];
    if (!focusable.length) {
      event.preventDefault();
      dialog.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };
  activeModalClose = close;
  document.body.classList.add("modal-open");
  document.addEventListener("keydown", handleKeydown);
  root.querySelectorAll("[data-modal-close]").forEach(node => node.addEventListener("click", event => {
    if (event.currentTarget === event.target || event.currentTarget.matches("button")) close();
  }));
  const form = root.querySelector("form");
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const button = form.querySelector("button[type=submit]");
    const errorNode = form.querySelector(".modal-error");
    errorNode.hidden = true;
    errorNode.textContent = "";
    button.disabled = true;
    button.classList.add("is-loading");
    button.setAttribute("aria-busy", "true");
    button.textContent = "处理中...";
    try {
      await onSubmit(new FormData(form), form);
      close();
    } catch (error) {
      const errorMessage = error.message || "操作失败";
      errorNode.textContent = errorMessage;
      errorNode.hidden = false;
      toast(errorMessage, "danger");
      button.disabled = false;
      button.classList.remove("is-loading");
      button.removeAttribute("aria-busy");
      button.textContent = submitText;
    }
  });
  setTimeout(() => root.querySelector("input, textarea, select, button")?.focus(), 0);
}

export function confirmAction(message, onConfirm, confirmText = "确认") {
  showModal({
    title: "请确认",
    content: `<p class="confirm-copy">${escapeHtml(message)}</p>`,
    submitText: confirmText,
    onSubmit: onConfirm,
  });
}

export function loadingState(text = "正在加载") {
  return `<div class="state-panel state-loading" data-state="loading" role="status" aria-live="polite"><span class="spinner" aria-hidden="true"></span><p>${escapeHtml(text)}</p></div>`;
}

export function emptyState(title, description, action = "") {
  return `<div class="state-panel state-empty" data-state="empty" role="status">${icon("file", 28)}<h3>${escapeHtml(title)}</h3><p>${escapeHtml(description)}</p>${action}</div>`;
}

export function pageHeader(title, description, actions = "") {
  return `<header class="page-header" data-ui="page-header"><div class="page-heading"><h1>${escapeHtml(title)}</h1><p>${escapeHtml(description)}</p></div><div class="page-actions">${actions}</div></header>`;
}

export function renderBusinessResult(result) {
  const data = result?.data || result;
  const items = Array.isArray(data?.items) ? data.items : [];
  if (!items.length) return "";
  const isMentor = items.some(item => item.teacher_id);
  const rows = items.map(item => isMentor ? `
    <tr><td>${escapeHtml(item.name)}</td><td>${escapeHtml(item.title)}</td><td>${escapeHtml((item.tags || []).join("、"))}</td><td><strong>${escapeHtml(item.reason)}</strong></td></tr>` : `
    <tr><td>${escapeHtml(item.title)}</td><td>${escapeHtml((item.tags || []).join("、"))}</td><td>${escapeHtml(item.deadline ? formatDate(item.deadline, false) : "未设置")}</td><td><strong>${escapeHtml(item.reason)}</strong></td></tr>`).join("");
  return `<div class="business-result table-wrap"><table class="data-table"><thead><tr>${isMentor ? "<th>导师</th><th>研究方向</th><th>标签</th><th>匹配说明</th>" : "<th>比赛</th><th>标签</th><th>截止时间</th><th>推荐理由</th>"}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

export function renderConfirmationCard(result) {
  const data = result?.data || result;
  if (data?.status !== "pending_confirmation" || !data.preview) return "";
  const payload = encodeURIComponent(JSON.stringify({
    intent: data.intent,
    fields: data.preview.fields || {},
    confirmation_token: data.confirmation_token,
  }));
  return `<section class="confirmation-card" data-confirmation-card>
    <div><strong>${escapeHtml(data.preview.summary || "成果写操作")}</strong><p>${escapeHtml(data.preview.impact || "确认后将执行该操作。")}</p></div>
    <dl>${Object.entries(data.preview.fields || {}).slice(0, 8).map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(typeof value === "object" ? JSON.stringify(value) : value)}</dd></div>`).join("")}</dl>
    <div class="confirmation-actions"><button class="button button-ghost button-small" type="button" data-confirm-cancel>取消</button><button class="button button-primary button-small" type="button" data-confirm-business="${payload}">确认</button></div>
  </section>`;
}
