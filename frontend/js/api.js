import { clearAuth, state, updateTokens } from "./state.js";

const API_BASE_URL = (window.__LONGMA_API_BASE_URL__ || "").replace(/\/$/, "");
function apiUrl(path) {
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE_URL}${path}`;
}

// ============================================
// 调试日志工具
// ============================================
const DEBUG_API = true; // 设置为 false 可关闭详细日志

function log(...args) {
  if (DEBUG_API) console.log("[API]", ...args);
}

function logError(...args) {
  console.error("[API]", ...args);
}

function logRequest(method, url, headers, body) {
  const timestamp = new Date().toISOString();
  const maskedHeaders = {};
  headers.forEach((value, key) => {
    if (key.toLowerCase() === "authorization") {
      maskedHeaders[key] = value.slice(0, 20) + "...";
    } else {
      maskedHeaders[key] = value;
    }
  });
  log(`\n${timestamp}`);
  log(`→ REQUEST: ${method} ${url}`);
  log(`  Headers:`, maskedHeaders);
  if (body) {
    // 脱敏敏感字段
    try {
      const parsed = typeof body === "string" ? JSON.parse(body) : body;
      const masked = { ...parsed };
      if (masked.password) masked.password = "***";
      if (masked.old_password) masked.old_password = "***";
      if (masked.new_password) masked.new_password = "***";
      if (masked.refresh_token) masked.refresh_token = masked.refresh_token.slice(0, 20) + "...";
      log(`  Body:`, masked);
    } catch {
      log(`  Body:`, body);
    }
  }
}

function logResponse(method, url, response, data) {
  const timestamp = new Date().toISOString();
  log(`← RESPONSE: ${method} ${url}`);
  log(`  Status: ${response.status} ${response.statusText}`);
  log(`  Request-ID: ${response.headers.get("X-Request-ID") || "(none)"}`);
  log(`  Response-Time: ${response.headers.get("X-Response-Time") || "(none)"}`);
  if (data !== null && data !== undefined) {
    // 截断过长的响应
    const str = typeof data === "string" ? data : JSON.stringify(data);
    if (str.length > 500) {
      log(`  Data:`, str.slice(0, 500) + "...(truncated)");
    } else {
      log(`  Data:`, data);
    }
  }
}

// ============================================
// API 错误类
// ============================================
export class ApiError extends Error {
  constructor(message, status = 0, code = "REQUEST_FAILED", requestId = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

// ============================================
// 响应解析
// ============================================
async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (response.status === 204) return null;
  if (contentType.includes("application/json")) return response.json();
  return response.text();
}

// ============================================
// Token 刷新
// ============================================
async function refreshSession() {
  const url = "/api/v1/auth/refresh";
  const requestUrl = apiUrl(url);
  log("🔄 Token 刷新开始");
  log("  当前 refresh_token:", state.refreshToken?.slice(0, 30) + "...");

  if (!state.refreshToken) {
    logError("  失败: 无 refresh_token");
    return false;
  }

  const startTime = performance.now();
  const body = JSON.stringify({ refresh_token: state.refreshToken });

  logRequest("POST", url, new Headers({ "Content-Type": "application/json" }), body);

  try {
    const response = await fetch(requestUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });

    const data = await parseResponse(response);
    logResponse("POST", url, response, data);

    if (!response.ok) {
      logError("  失败: HTTP", response.status);
      clearAuth();
      return false;
    }

    const elapsed = performance.now() - startTime;
    log(`✅ Token 刷新成功 (${elapsed.toFixed(0)}ms)`);
    log("  新 access_token:", data.access_token?.slice(0, 30) + "...");
    log("  新 refresh_token:", data.refresh_token?.slice(0, 30) + "...");

    updateTokens(data.access_token, data.refresh_token);
    return true;
  } catch (error) {
    logError("  失败:", error.message);
    clearAuth();
    return false;
  }
}

// ============================================
// 通用 API 请求
// ============================================
export async function api(path, options = {}, retry = true) {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  const isForm = options.body instanceof FormData;
  const timeoutController = new AbortController();
  const timeoutId = setTimeout(() => timeoutController.abort(), 15000);
  const externalSignal = options.signal;
  const abortFromExternalSignal = () => timeoutController.abort();
  externalSignal?.addEventListener("abort", abortFromExternalSignal, { once: true });

  // 设置 Content-Type
  if (!isForm && options.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  // 设置 Authorization
  if (state.accessToken) {
    headers.set("Authorization", `Bearer ${state.accessToken}`);
  }

  // 设置幂等键（写操作防重复提交）
  if (["POST", "PUT", "PATCH"].includes(method) && !headers.has("Idempotency-Key")) {
    headers.set("Idempotency-Key", crypto.randomUUID());
  }

  const startTime = performance.now();
  logRequest(method, path, headers, options.body);

  try {
    const response = await fetch(apiUrl(path), { ...options, method, headers, signal: timeoutController.signal });

    // 401 且有 refresh_token 时尝试刷新
    if (response.status === 401 && retry && state.refreshToken) {
      log("⚠️ 收到 401，尝试刷新 token...");
      const refreshed = await refreshSession();
      if (refreshed) {
        log("🔄 Token 已刷新，重试请求...");
        // 用新 token 重试
        headers.set("Authorization", `Bearer ${state.accessToken}`);
        const retryResponse = await fetch(apiUrl(path), { ...options, method, headers, signal: timeoutController.signal });
        const retryData = await parseResponse(retryResponse);
        logResponse(method, path, retryResponse, retryData);

        if (!retryResponse.ok) {
          const error = retryData?.error || {};
          throw new ApiError(
            error.message || `请求失败 (${retryResponse.status})`,
            retryResponse.status,
            error.code,
            retryData?.request_id
          );
        }
        return retryData;
      } else {
        log("❌ Token 刷新失败，清除认证状态");
        clearAuth();
      }
    }

    const data = await parseResponse(response);
    logResponse(method, path, response, data);

    if (!response.ok) {
      const error = data?.error || {};
      if (response.status === 401) {
        log("⚠️ 401 错误，清除认证状态");
        clearAuth();
      }
      throw new ApiError(
        error.message || `请求失败 (${response.status})`,
        response.status,
        error.code,
        data?.request_id
      );
    }

    const elapsed = performance.now() - startTime;
    log(`✅ 请求完成 (${elapsed.toFixed(0)}ms)`);

    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    logError("❌ 网络错误:", error.message);
    if (error.name === "AbortError") {
      throw new ApiError("连接服务器超时，请确认服务已启动后重试", 0, "REQUEST_TIMEOUT");
    }
    throw new ApiError(error.message || "网络请求失败", 0, "NETWORK_ERROR");
  } finally {
    clearTimeout(timeoutId);
    externalSignal?.removeEventListener("abort", abortFromExternalSignal);
  }
}

// ============================================
// 文件下载
// ============================================
export async function download(path, filename) {
  const startTime = performance.now();
  log(`⬇️ DOWNLOAD: ${path}`);

  const headers = state.accessToken ? { Authorization: `Bearer ${state.accessToken}` } : {};
  const response = await fetch(apiUrl(path), { headers });

  if (!response.ok) {
    const data = await parseResponse(response);
    logError("  失败: HTTP", response.status);
    throw new ApiError(data?.error?.message || "下载失败", response.status, data?.error?.code);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "download";
  link.click();
  URL.revokeObjectURL(url);

  const elapsed = performance.now() - startTime;
  log(`✅ 下载完成 (${elapsed.toFixed(0)}ms, ${blob.size} bytes)`);
}

export async function fetchBlob(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (state.accessToken) headers.set("Authorization", `Bearer ${state.accessToken}`);
  const response = await fetch(apiUrl(path), { ...options, headers });
  if (!response.ok) {
    const data = await parseResponse(response);
    const error = data?.error || {};
    if (response.status === 401) clearAuth();
    throw new ApiError(error.message || "文件预览失败", response.status, error.code, data?.request_id);
  }
  return response.blob();
}

// ============================================
// SSE 流式聊天
// ============================================
export async function streamChat(sessionId, payload, onEvent, signal) {
  const url = `/api/v1/chat/sessions/${sessionId}/messages`;
  const startTime = performance.now();

  log(`\n📤 SSE CONNECT: POST ${url}`);
  log("  Payload:", payload);

  const isForm = payload instanceof FormData;
  const headers = { Authorization: `Bearer ${state.accessToken}` };
  if (!isForm) headers["Content-Type"] = "application/json";

  try {
    const response = await fetch(apiUrl(url), {
      method: "POST",
      headers,
      body: isForm ? payload : JSON.stringify(payload),
      signal,
    });

    if (!response.ok) {
      const data = await parseResponse(response);
      logError("  SSE 连接失败: HTTP", response.status);
      throw new ApiError(data?.error?.message || "发送失败", response.status, data?.error?.code);
    }

    log(`  SSE 连接成功，开始接收事件...`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let eventCount = 0;

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        log(`  SSE 流结束 (共 ${eventCount} 个事件)`);
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";

      for (const eventText of events) {
        const line = eventText.split("\n").find(line => line.startsWith("data:"));
        if (!line) continue;

        let eventData;
        try {
          eventData = JSON.parse(line.slice(5).trim());
        } catch (parseError) {
          logError("  SSE 解析失败:", parseError.message, line);
          continue;
        }
        eventCount++;

        // 根据事件类型打印不同日志
        if (eventData.type === "chunk") {
          log(`  📦 SSE event #${eventCount}: chunk "${eventData.data?.slice(0, 30)}..."`);
        } else if (eventData.type === "done") {
          log(`  ✅ SSE event #${eventCount}: done`, {
            duration_ms: eventData.data?.duration_ms,
            model: eventData.data?.model,
            skill: eventData.data?.skill_name,
          });
        } else if (eventData.type === "rag") {
          log(`  🔍 SSE event #${eventCount}: rag`, eventData.data);
        } else if (eventData.type === "error") {
          logError(`  ❌ SSE event #${eventCount}: error`, eventData.data);
        } else {
          log(`  📨 SSE event #${eventCount}:`, eventData);
        }

        // Do not swallow callback errors: the chat view must surface provider
        // failures and persist the failed request recovery state.
        onEvent(eventData);
      }
    }

    const elapsed = performance.now() - startTime;
    log(`✅ SSE 完成 (${elapsed.toFixed(0)}ms)`);
  } catch (error) {
    if (error.name === "AbortError") {
      log("  SSE 被用户中断");
    } else {
      logError("  SSE 错误:", error.message);
    }
    throw error;
  }
}

// ============================================
// 查询字符串构建
// ============================================
export function qs(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}
