import { api, download, streamChat } from "../api.js";
import { confirmAction, emptyState, escapeHtml, formatBytes, formatDate, icon, loadingState, renderBusinessResult, renderConfirmationCard, showModal, toast } from "../ui.js";

const FALLBACK_SKILLS = ["@agent", "@总结", "@翻译", "@思维导图", "@代码解释", "@代码生成", "@润色", "@竞赛推荐", "@导师匹配", "@党建查询", "@成果管理"];
const RAG_SCOPES = new Set(["personal", "class", "none"]);
const RAG_SCOPE_STORAGE_KEY = "longma.chat.ragScope";

export async function renderChat(container) {
  let sessions = [];
  let currentSession = null;
  let messages = [];
  let controller = null;
  let disposed = false;
  let skills = FALLBACK_SKILLS;
  let selectedFiles = [];
  let regeneratingId = null;
  let usage = null;
  let ragScope = sessionStorage.getItem(RAG_SCOPE_STORAGE_KEY) || "personal";
  if (!RAG_SCOPES.has(ragScope)) ragScope = "personal";

  function quotaResetLabel(value) {
    if (!value) return "今日 24:00 重置";
    const resetAt = new Date(value);
    if (Number.isNaN(resetAt.getTime())) return "今日 24:00 重置";
    return `${resetAt.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })} 重置`;
  }

  function quotaReminder() {
    if (!usage) return `<span class="chat-usage-reminder muted">额度加载中</span>`;
    const remaining = Math.max(0, Number(usage.remaining_tokens ?? usage.quota ?? 0));
    const quota = Number(usage.quota || 0);
    const exhausted = quota > 0 && remaining <= 0;
    return `<span class="chat-usage-reminder ${exhausted ? "exhausted" : ""}" title="已用 ${Number(usage.used_tokens || 0).toLocaleString()} Token，${quotaResetLabel(usage.reset_at)}">今日剩余 <strong>${remaining.toLocaleString()}</strong> Token · ${quotaResetLabel(usage.reset_at)}</span>`;
  }

  container.innerHTML = loadingState("正在载入对话");

  async function loadSessions(selectFirst = true) {
    const [result, usageResult] = await Promise.all([
      api("/api/v1/chat/sessions?page_size=100"),
      api("/api/v1/chat/usage/me").catch(() => null),
    ]);
    sessions = result.items;
    usage = usageResult;
    if (selectFirst && !currentSession && sessions.length) currentSession = sessions[0];
  }

  async function loadMessages() {
    if (!currentSession) { messages = []; return; }
    const result = await api(`/api/v1/chat/sessions/${currentSession.id}/messages?page_size=200`);
    messages = result.items;
    await Promise.all(messages.filter(message => message.role === "user").map(async message => {
      try { message.attachments = await api(`/api/v1/chat/messages/${message.id}/attachments`); } catch { message.attachments = []; }
    }));
  }

  async function loadSkills() {
    try {
      const result = await api("/api/v1/skills");
      const triggers = result.items.map(item => item.triggers?.[0]).filter(Boolean);
      skills = ["@agent", ...triggers.filter(trigger => trigger !== "@agent")];
    } catch {
      skills = FALLBACK_SKILLS;
    }
  }

  function sessionListHtml() {
    return sessions.length ? sessions.map(session => `
      <button class="session-item ${currentSession?.id === session.id ? "active" : ""}" data-session="${session.id}">
        <strong>${escapeHtml(session.title)}</strong><span>${escapeHtml(session.last_message_preview || "暂无消息")}</span>
      </button>`).join("") : emptyState("暂无会话", "新建会话后开始与 AI 对话。");
  }

  function messageHtml(message) {
    const isUser = message.role === "user";
    let citations = "";
    if (message.citations) {
      try {
        const parsed = typeof message.citations === "string" ? JSON.parse(message.citations) : message.citations;
        if (Array.isArray(parsed) && parsed.length) citations = `<div class="message-meta">引用：${parsed.map(item => escapeHtml(item.file_name || item.name || "知识库资料")).join("、")}</div>`;
      } catch { citations = '<div class="message-meta">已引用知识库资料</div>'; }
    }
    const structured = isUser ? "" : renderBusinessResult(message.structured_result) + renderConfirmationCard(message.structured_result);
    const content = isUser ? escapeHtml(message.content) : window.DOMPurify.sanitize(window.marked.parse(message.content || ""));
    const attachments = (message.attachments || []).length ? `<div class="message-attachments">${message.attachments.map(item => `<button type="button" class="attachment-chip" data-chat-download="${item.id}" data-name="${escapeHtml(item.original_name)}">${icon("file", 14)}<span>${escapeHtml(item.original_name)}</span><small>${formatBytes(item.size)}</small></button>`).join("")}</div>` : "";
    const regenerate = !isUser && message.id && !message.streaming ? `<button type="button" class="message-action" data-regenerate="${message.id}" ${regeneratingId ? "disabled" : ""}>${icon("sparkles", 14)} 重新生成</button>` : "";
    const recovery = !isUser && message.request_id && ["failed", "interrupted"].includes(message.status) ? `<button type="button" class="message-action" data-recover="${escapeHtml(message.request_id)}" data-recover-mode="${message.status === "interrupted" ? "continue" : "retry"}">${icon("refresh", 14)} ${message.status === "interrupted" ? "继续生成" : "重新发送"}</button>` : "";
    return `<article class="message ${isUser ? "user" : "assistant"}">
      <span class="message-avatar">${isUser ? "我" : icon("sparkles", 16)}</span>
      <div class="message-bubble"><div class="message-content markdown-body">${content}</div>${attachments}${structured}${citations}<div class="message-meta"><span>${formatDate(message.created_at)}</span>${message.skill_name ? `<span>${escapeHtml(message.skill_name)}</span>` : ""}${message.duration_ms ? `<span>${message.duration_ms} ms</span>` : ""}${message.status && message.status !== "completed" ? `<span>${escapeHtml(message.status)}</span>` : ""}${message.regenerated_at ? "<span>已重新生成</span>" : ""}${regenerate}${recovery}</div></div>
    </article>`;
  }

  function renderLayout() {
    if (disposed) return;
    container.innerHTML = `
      <section class="chat-layout">
        <aside class="chat-sidebar">
          <div class="chat-sidebar-head"><button class="button button-primary button-full" id="new-session">${icon("plus")} 新建会话</button><button class="icon-button mobile-only" id="chat-close" type="button" aria-label="关闭会话列表" title="关闭会话列表">${icon("close")}</button></div>
          <div class="session-list">${sessionListHtml()}</div>
        </aside>
        <button class="chat-drawer-scrim" id="chat-drawer-scrim" type="button" aria-label="关闭会话列表"></button>
        <div class="chat-main">
          <header class="chat-head">
            <button class="icon-button mobile-only" id="chat-menu" aria-label="会话列表">${icon("menu")}</button>
            <div><strong>${escapeHtml(currentSession?.title || "选择一个会话")}</strong><span>${currentSession ? `${messages.length} 条消息` : "新建会话后开始"}</span>${quotaReminder()}</div>
            ${currentSession ? `<button class="icon-button" id="rename-session" aria-label="重命名">${icon("edit")}</button><button class="icon-button danger" id="delete-session" aria-label="删除">${icon("trash")}</button>` : ""}
            <select class="select" id="rag-scope" aria-label="知识库范围"><option value="personal" ${ragScope === "personal" ? "selected" : ""}>个人知识库</option><option value="class" ${ragScope === "class" ? "selected" : ""}>班级知识库</option><option value="none" ${ragScope === "none" ? "selected" : ""}>不使用知识库</option></select>
          </header>
          <div class="message-list" id="message-list">
            ${currentSession ? (messages.length ? messages.map(messageHtml).join("") : emptyState("开始新的对话", "你可以直接提问，或选择一个 Skill 快速开始。")) : emptyState("还没有会话", "新建一个会话，与 AI 开始学习和协作。", '<button class="button button-primary" id="empty-new-session">新建会话</button>')}
          </div>
          <form class="chat-compose" id="message-form">
            <div class="skill-chips">${skills.map(skill => `<button type="button" class="skill-chip" data-skill="${escapeHtml(skill)}">${escapeHtml(skill)}</button>`).join("")}</div>
            ${selectedFiles.length ? `<div class="composer-files">${selectedFiles.map((file, index) => `<span class="attachment-chip">${escapeHtml(file.name)}<button type="button" data-remove-file="${index}" aria-label="移除">${icon("close", 13)}</button></span>`).join("")}</div>` : ""}
            <div class="composer-row"><input type="file" id="chat-files" multiple hidden><button class="icon-button" type="button" id="attach-chat" aria-label="添加附件" title="添加附件">${icon("upload")}</button><textarea class="textarea" id="message-input" name="content" rows="1" placeholder="输入消息，Enter 发送，Shift + Enter 换行" ${currentSession ? "" : "disabled"}></textarea><button class="button button-primary" type="submit" aria-label="发送" ${currentSession ? "" : "disabled"}>${icon("send")}</button></div>
          </form>
        </div>
      </section>`;
    bindEvents();
    const list = container.querySelector("#message-list");
    if (list) list.scrollTop = list.scrollHeight;
  }

  async function createSession(title = "新会话") {
    currentSession = await api("/api/v1/chat/sessions", { method: "POST", body: JSON.stringify({ title, knowledge_scope: ragScope, web_search_enabled: true }) });
    sessions.unshift(currentSession);
    messages = [];
    renderLayout();
  }

  function bindEvents() {
    container.querySelector("#new-session")?.addEventListener("click", () => createSession());
    container.querySelector("#empty-new-session")?.addEventListener("click", () => createSession());
    const setChatDrawer = open => {
      container.querySelector(".chat-sidebar")?.classList.toggle("mobile-open", open);
      container.querySelector("#chat-drawer-scrim")?.classList.toggle("open", open);
    };
    container.querySelector("#chat-menu")?.addEventListener("click", () => setChatDrawer(true));
    container.querySelector("#chat-close")?.addEventListener("click", () => setChatDrawer(false));
    container.querySelector("#chat-drawer-scrim")?.addEventListener("click", () => setChatDrawer(false));
    container.querySelector("#rag-scope")?.addEventListener("change", async event => {
      ragScope = event.currentTarget.value;
      sessionStorage.setItem(RAG_SCOPE_STORAGE_KEY, ragScope);
      if (currentSession) {
        currentSession = await api(`/api/v1/chat/sessions/${currentSession.id}`, {
          method: "PUT",
          body: JSON.stringify({ title: currentSession.title, knowledge_scope: ragScope }),
        });
      }
    });
    container.querySelectorAll("[data-session]").forEach(node => node.addEventListener("click", async () => {
      currentSession = sessions.find(item => item.id === Number(node.dataset.session));
      if (RAG_SCOPES.has(currentSession.knowledge_scope)) ragScope = currentSession.knowledge_scope;
      await loadMessages();
      renderLayout();
    }));
    container.querySelector("#rename-session")?.addEventListener("click", () => showModal({
      title: "重命名会话",
      content: `<label class="field"><span>会话标题</span><input class="input" name="title" value="${escapeHtml(currentSession.title)}" maxlength="200" required></label>`,
      submitText: "保存",
      onSubmit: async data => {
        currentSession = await api(`/api/v1/chat/sessions/${currentSession.id}`, { method: "PUT", body: JSON.stringify({ title: data.get("title") }) });
        const index = sessions.findIndex(item => item.id === currentSession.id);
        sessions[index] = currentSession;
        renderLayout();
      },
    }));
    container.querySelector("#delete-session")?.addEventListener("click", () => confirmAction("删除后该会话将不再显示，确认继续？", async () => {
      await api(`/api/v1/chat/sessions/${currentSession.id}`, { method: "DELETE" });
      sessions = sessions.filter(item => item.id !== currentSession.id);
      currentSession = sessions[0] || null;
      await loadMessages();
      renderLayout();
      toast("会话已删除");
    }, "删除"));
    container.querySelectorAll("[data-skill]").forEach(node => node.addEventListener("click", () => {
      const input = container.querySelector("#message-input");
      input.value = `${node.dataset.skill} ` + input.value.replace(/^@\S+\s*/, "");
      input.focus();
    }));
    container.querySelector("#attach-chat")?.addEventListener("click", () => container.querySelector("#chat-files").click());
    container.querySelector("#chat-files")?.addEventListener("change", event => { selectedFiles = [...event.target.files].slice(0, 3); renderLayout(); });
    container.querySelectorAll("[data-remove-file]").forEach(node => node.addEventListener("click", () => { selectedFiles.splice(Number(node.dataset.removeFile), 1); renderLayout(); }));
    container.querySelectorAll("[data-chat-download]").forEach(node => node.addEventListener("click", () => download(`/api/v1/chat/attachments/${node.dataset.chatDownload}/download`, node.dataset.name)));
    container.querySelectorAll("[data-regenerate]").forEach(node => node.addEventListener("click", async () => {
      regeneratingId = Number(node.dataset.regenerate); renderLayout();
      try { const updated = await api(`/api/v1/chat/sessions/${currentSession.id}/messages/${regeneratingId}/regenerate`, { method: "POST" }); messages[messages.findIndex(item => item.id === updated.id)] = updated; }
      catch (error) { toast(error.message, "danger"); }
      finally { regeneratingId = null; renderLayout(); }
    }));
    container.querySelectorAll("[data-recover]").forEach(node => node.addEventListener("click", async () => {
      const mode = node.dataset.recoverMode || "retry";
      node.disabled = true;
      try {
        const result = await api(`/api/v1/chat/requests/${node.dataset.recover}/${mode}`, { method: "POST" });
        await loadMessages();
        toast(result.status === "completed" ? "请求已恢复" : "恢复请求已提交");
      } catch (error) { toast(error.message, "danger"); }
      finally { renderLayout(); }
    }));
    container.querySelectorAll("[data-confirm-business]").forEach(node => node.addEventListener("click", () => {
      const payload = JSON.parse(decodeURIComponent(node.dataset.confirmBusiness));
      const actionLabels = { create: "新增成果", update: "修改成果", delete: "删除成果" };
      const fields = { ...payload.fields, confirmation_token: payload.confirmation_token };
      const input = container.querySelector("#message-input");
      input.value = `@成果管理 ${actionLabels[payload.intent] || "管理成果"} ${JSON.stringify(fields)}`;
      container.querySelector("#message-form").requestSubmit();
    }));
    container.querySelectorAll("[data-confirm-cancel]").forEach(node => node.addEventListener("click", () => {
      node.closest("[data-confirmation-card]")?.remove();
      toast("已取消操作", "warning");
    }));
    const input = container.querySelector("#message-input");
    input?.addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        container.querySelector("#message-form").requestSubmit();
      }
    });
    container.querySelector("#message-form")?.addEventListener("submit", sendMessage);
  }

  async function sendMessage(event) {
    event.preventDefault();
    if (controller) {
      controller.abort();
      controller = null;
      return;
    }
    const input = container.querySelector("#message-input");
    const content = input.value.trim();
    if ((!content && !selectedFiles.length) || !currentSession) return;
    if (usage && Number(usage.quota || 0) > 0 && Number(usage.remaining_tokens || 0) <= 0) {
      toast(`今日 Token 额度已用完，${quotaResetLabel(usage.reset_at)}`, "warning");
      return;
    }
    input.value = "";
    const now = new Date().toISOString();
    const outgoingFiles = [...selectedFiles];
    selectedFiles = [];
    messages.push({ role: "user", content, created_at: now, attachments: outgoingFiles.map((file, index) => ({ id: `pending-${index}`, original_name: file.name, size: file.size })) });
    messages.push({ role: "assistant", content: "", created_at: now, streaming: true });
    renderLayout();
    const sendButton = container.querySelector("#message-form button[type=submit]");
    sendButton.innerHTML = icon("close");
    sendButton.setAttribute("aria-label", "停止显示");
    const assistantContent = container.querySelector(".message-list .message:last-child .message-content");
    assistantContent.classList.add("typing-cursor");
    controller = new AbortController();
    try {
      const payload = outgoingFiles.length ? new FormData() : { content, knowledge_scope: ragScope, rag_scope: ragScope, web_search_enabled: true, idempotency_key: crypto.randomUUID() };
      if (payload instanceof FormData) { payload.append("content", content || "请查看附件"); payload.append("rag_scope", ragScope); outgoingFiles.forEach(file => payload.append("files", file)); }
      await streamChat(currentSession.id, payload, eventData => {
        if (eventData.type === "chunk") {
          messages[messages.length - 1].content += eventData.data;
          assistantContent.textContent = messages[messages.length - 1].content;
        } else if (eventData.type === "rag") {
          messages[messages.length - 1].rag = eventData.data.sources;
        } else if (eventData.type === "knowledge.not_found") {
          messages[messages.length - 1].knowledgeStatus = eventData.data.message || "未找到相关资料";
          toast(messages[messages.length - 1].knowledgeStatus, "warning");
        } else if (eventData.type === "done") {
          messages[messages.length - 1] = { ...messages[messages.length - 1], ...eventData.data, streaming: false };
        } else if (eventData.type === "error") {
          throw new Error(eventData.data);
        }
        container.querySelector("#message-list").scrollTop = container.querySelector("#message-list").scrollHeight;
      }, controller.signal);
      await loadSessions(false);
    } catch (error) {
      if (error.name !== "AbortError") {
        messages[messages.length - 1].content ||= `回复失败：${error.message}`;
        toast(error.message, "danger");
      }
    } finally {
      controller = null;
      renderLayout();
    }
  }

  try {
    await loadSessions();
    await loadSkills();
    await loadMessages();
    renderLayout();
  } catch (error) {
    container.innerHTML = emptyState("对话加载失败", error.message, '<button class="button button-secondary" id="retry-chat">重新加载</button>');
    container.querySelector("#retry-chat")?.addEventListener("click", () => renderChat(container));
  }

  return () => {
    disposed = true;
    controller?.abort();
  };
}
