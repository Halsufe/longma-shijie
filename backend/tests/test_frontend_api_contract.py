from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _frontend_source(relative_path: str) -> str:
    return (PROJECT_ROOT / "frontend" / relative_path).read_text(encoding="utf-8")


def test_api_preserves_json_multipart_auth_and_error_contracts() -> None:
    source = _frontend_source("js/api.js")

    assert 'const isForm = options.body instanceof FormData;' in source
    assert 'headers.set("Content-Type", "application/json");' in source
    assert 'headers.set("Authorization", `Bearer ${state.accessToken}`);' in source
    assert 'headers.set("Idempotency-Key", crypto.randomUUID());' in source
    assert 'const url = "/api/v1/auth/refresh";' in source
    assert 'JSON.stringify({ refresh_token: state.refreshToken })' in source

    assert "export class ApiError extends Error" in source
    assert 'error.message || `请求失败 (${response.status})`' in source
    assert "response.status," in source
    assert "error.code," in source
    assert "data?.request_id" in source
    assert 'new ApiError("连接服务器超时，请确认服务已启动后重试"' in source
    assert 'new ApiError(error.message || "网络请求失败"' in source
    assert 'if (response.status === 401)' in source
    assert "clearAuth();" in source


def test_api_preserves_download_stream_and_query_string_contracts() -> None:
    source = _frontend_source("js/api.js")

    assert "export async function download(path, filename)" in source
    assert 'Authorization: `Bearer ${state.accessToken}`' in source
    assert "const blob = await response.blob();" in source
    assert 'link.download = filename || "download";' in source
    assert "URL.revokeObjectURL(url);" in source
    assert "export async function fetchBlob(path, options = {})" in source
    assert 'headers.set("Authorization", `Bearer ${state.accessToken}`);' in source
    assert 'error.message || "文件预览失败"' in source
    assert "return response.blob();" in source

    assert "export async function streamChat(sessionId, payload, onEvent, signal)" in source
    assert "`/api/v1/chat/sessions/${sessionId}/messages`" in source
    assert "body: isForm ? payload : JSON.stringify(payload)" in source
    assert "signal," in source

    assert "export function qs(params = {})" in source
    assert "const search = new URLSearchParams();" in source
    assert 'value !== undefined && value !== null && value !== ""' in source
    assert 'return query ? `?${query}` : "";' in source


def test_api_boundary_does_not_mix_static_asset_paths() -> None:
    source = _frontend_source("js/api.js")

    assert "/static" not in source
    assert "院徽" not in source
    assert "brand-mark" not in source


def test_views_do_not_bypass_the_api_boundary() -> None:
    for path in (PROJECT_ROOT / "frontend" / "js" / "views").glob("*.js"):
        assert "fetch(" not in path.read_text(encoding="utf-8"), path.name


def test_representative_page_request_parameters_are_preserved() -> None:
    expected_requests = {
        "js/app.js": [
            'api("/api/v1/auth/login"',
            'api("/api/v1/notifications/unread-count")',
        ],
        "js/views/overview.js": [
            'api("/api/v1/notifications?page_size=5")',
            'api("/api/v1/assignments?status=published&page_size=5")',
        ],
        "js/views/chat.js": [
            'api("/api/v1/chat/sessions?page_size=100")',
            "streamChat(currentSession.id, payload",
        ],
        "js/views/knowledge.js": [
            'qs({ page_size: 100, q: query, folder_id: folderId })',
            "download(`${endpoint()}/files/${file.id}/download`, file.original_name)",
        ],
        "js/views/courses.js": [
            'api("/api/v1/courses?page_size=200")',
            'api("/api/v1/schedule/week")',
        ],
        "js/views/community.js": [
            'qs({ page_size: 100, q: query, type: resourceType })',
            'const params = { page: 1, page_size: 100, year: selectedYear }',
        ],
        "js/views/party.js": [
            'qs({ page_size: 100, status, category, year })',
            'api("/api/v1/party/learning-materials")',
        ],
        "js/views/notifications.js": [
            'qs({ page_size: 100, is_read: filter === "all" ? null : filter === "read" })',
        ],
        "js/views/admin.js": [
            'qs({ page_size: 100, q: query, role: roleFilter, status: statusFilter })',
            'download("/api/v1/admin/stats/activity/export?days=30", "activity.csv")',
        ],
    }

    for relative_path, requests in expected_requests.items():
        source = _frontend_source(relative_path)
        for request in requests:
            assert request in source, f"{request!r} missing from {relative_path}"
