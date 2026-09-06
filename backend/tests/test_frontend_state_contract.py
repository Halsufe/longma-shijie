from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_JS = PROJECT_ROOT / "frontend" / "js" / "state.js"
APP_JS = PROJECT_ROOT / "frontend" / "js" / "app.js"


def test_state_module_exposes_auth_route_and_drawer_contract() -> None:
    source = STATE_JS.read_text(encoding="utf-8")

    for symbol in (
        "accessToken",
        "user",
        "route",
        "sidebarOpen",
        "unreadCount",
        "setAuth",
        "setCurrentUser",
        "updateTokens",
        "clearAuth",
        "navigate",
        "setSidebarOpen",
        "toggleSidebar",
        "syncRouteFromHash",
    ):
        assert symbol in source
    assert "document." not in source
    assert "innerHTML" not in source


def test_state_module_persists_auth_and_handles_route_and_drawer_transitions() -> None:
    script = r'''
const storage = new Map([
  ["longma.auth", JSON.stringify({accessToken: "cached", refreshToken: "refresh", user: {role: "student"}})],
]);
let currentHash = "#chat";
globalThis.location = {};
Object.defineProperty(globalThis.location, "hash", {
  get: () => currentHash,
  set: value => { currentHash = value.startsWith("#") ? value : `#${value}`; },
});
globalThis.sessionStorage = {
  getItem: key => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, value),
  removeItem: key => storage.delete(key),
};
const stateModule = await import("./frontend/js/state.js?state-contract");
const {state, setAuth, setCurrentUser, updateTokens, clearAuth, navigate,
  setSidebarOpen, toggleSidebar, syncRouteFromHash} = stateModule;
if (state.route !== "chat" || state.accessToken !== "cached") throw new Error("stored state was not restored");
setAuth({access_token: "access", refresh_token: "next-refresh", user: {id: 1}});
if (state.accessToken !== "access" || state.refreshToken !== "next-refresh") throw new Error("setAuth failed");
setCurrentUser({id: 2});
updateTokens("rotated", "rotated-refresh");
const persisted = JSON.parse(storage.get("longma.auth"));
if (persisted.accessToken !== "rotated" || persisted.user.id !== 2) throw new Error("auth was not persisted");
if (!setSidebarOpen(true) || !state.sidebarOpen) throw new Error("drawer did not open");
if (toggleSidebar() !== false || state.sidebarOpen) throw new Error("drawer did not toggle");
if (navigate("knowledge") !== "knowledge" || state.route !== "knowledge" || location.hash !== "#knowledge") throw new Error("navigate failed");
location.hash = "#admin";
if (syncRouteFromHash(route => route === "overview" || route === "chat") !== "overview") throw new Error("invalid route did not fall back");
clearAuth();
if (state.accessToken !== null || state.user !== null || storage.has("longma.auth")) throw new Error("clearAuth failed");
'''
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_app_keeps_permission_fallback_and_logout_auth_failure_flow() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert 'routeKey = "overview"' in source
    assert 'location.hash.slice(1) || "overview"' in source
    assert 'location.hash = ""' in source
    assert "clearAuth();" in source
