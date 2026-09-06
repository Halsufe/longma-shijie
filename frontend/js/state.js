const STORAGE_KEY = "longma.auth";
export const DEFAULT_ROUTE = "overview";

function normalizeRoute(route) {
  return typeof route === "string" && route.trim() ? route.trim() : DEFAULT_ROUTE;
}

function routeFromHash(hash = location.hash) {
  const value = typeof hash === "string" ? hash.replace(/^#/, "").trim() : "";
  return normalizeRoute(value);
}

function readStoredAuth() {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

const stored = readStoredAuth();

export const state = {
  accessToken: stored.accessToken || null,
  refreshToken: stored.refreshToken || null,
  user: stored.user || null,
  route: routeFromHash(),
  sidebarOpen: false,
  unreadCount: 0,
};

export function setAuth(payload) {
  state.accessToken = payload.access_token;
  state.refreshToken = payload.refresh_token || null;
  state.user = payload.user;
  persistAuth();
}

export function setCurrentUser(user) {
  state.user = user;
  persistAuth();
}

export function updateTokens(accessToken, refreshToken) {
  state.accessToken = accessToken;
  if (refreshToken) state.refreshToken = refreshToken;
  persistAuth();
}

export function clearAuth() {
  state.accessToken = null;
  state.refreshToken = null;
  state.user = null;
  state.unreadCount = 0;
  sessionStorage.removeItem(STORAGE_KEY);
}

/** Update the mobile drawer state without touching any view or DOM nodes. */
export function setSidebarOpen(open) {
  state.sidebarOpen = Boolean(open);
  return state.sidebarOpen;
}

export function toggleSidebar() {
  return setSidebarOpen(!state.sidebarOpen);
}

/**
 * Read the current hash and optionally validate it against the app shell's
 * route/permission registry. The state layer does not own route permissions.
 */
export function syncRouteFromHash(isAllowed) {
  const candidate = routeFromHash();
  state.route = typeof isAllowed === "function" && !isAllowed(candidate)
    ? DEFAULT_ROUTE
    : candidate;
  return state.route;
}

function persistAuth() {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
    accessToken: state.accessToken,
    refreshToken: state.refreshToken,
    user: state.user,
  }));
}

export function navigate(route) {
  const nextRoute = normalizeRoute(route);
  state.route = nextRoute;
  location.hash = nextRoute;
  return nextRoute;
}
