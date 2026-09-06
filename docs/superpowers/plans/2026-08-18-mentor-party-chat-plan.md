# 导师双选、党建与 AI 对话优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除前端学校公告入口，分别优化导师双选与党建工作台布局，并更新后端 AI key，同时保留现有业务流程。

**Architecture:** 继续使用当前 vanilla ES module 前端和 FastAPI 后端。公告只从前端 app shell/overview 移除；导师双选和党建仅调整各自 view 的 DOM 组织与共享样式；AI 继续由后端 `GenericAdapter` 读取 `.env`，不改变 API 契约。

**Tech Stack:** Vanilla JavaScript ES modules, CSS, FastAPI, pytest, existing browser/runtime checks.

---

### Task 1: Add regression contracts for the requested surface

**Files:**
- Modify: `backend/tests/test_frontend_app_shell_contract.py`
- Modify: `backend/tests/test_frontend_overview_contract.py`
- Modify: `backend/tests/test_frontend_pages_contract.py`
- Create: `backend/tests/test_frontend_workspace_layout_contract.py`

- [ ] **Step 1: Write failing assertions**

Add assertions that `app.js` no longer registers `announcements`, `overview.js` no longer contains the school-announcement request/panel, and the mentor/party views expose the new workspace class hooks (`mentor-workbench`, `party-workbench`, `party-summary-grid`).

- [ ] **Step 2: Run the focused tests**

Run `python -m pytest backend/tests/test_frontend_app_shell_contract.py backend/tests/test_frontend_overview_contract.py backend/tests/test_frontend_pages_contract.py backend/tests/test_frontend_workspace_layout_contract.py -q`.

Expected: new layout/removal assertions fail against the current source.

### Task 2: Remove school announcements from the frontend shell

**Files:**
- Modify: `frontend/js/app.js`
- Modify: `frontend/js/views/overview.js`
- Leave unchanged: `backend/app/api/routes/school_announcements.py` and announcement persistence code.

- [ ] **Step 1: Remove the frontend route and import**

Delete the `renderAnnouncements` import and the `announcements` route entry. Remove only the sidebar registration and route-level surface; do not touch backend announcement routes.

- [ ] **Step 2: Remove overview loading and panel**

Remove the `announcements` request from the overview `Promise.allSettled` group and remove the `notificationPanel`/announcement panel branch that renders “学校公告”. Preserve other notifications and loading/error behavior.

- [ ] **Step 3: Run focused contracts**

Run the Task 1 command and confirm announcement assertions pass while all existing route/layout contracts remain green.

### Task 3: Implement the mentor selection workbench layout

**Files:**
- Modify: `frontend/js/mentor_selection.js`
- Modify: `frontend/js/views/mentorship.js`
- Modify: `frontend/assets/styles.css`

- [ ] **Step 1: Wrap the independent selection workspace**

Keep the existing page-level tabs. Add `mentor-workbench` around the selection workspace and use `mentor-summary-grid`, `mentor-main-panel`, and `mentor-side-panel` hooks around existing batch header, student/teacher/admin content, preserving all existing API calls, form names, data attributes, and action handlers.

- [ ] **Step 2: Recompose student selection content**

Keep the current statement, mentor fields, draft submit, formal submit, waiting state, and published result. Render the mentor list in the main column and the statement/submission controls in the side column on wide screens; use a single column below 860px.

- [ ] **Step 3: Add shared responsive styles**

Add stable grid rules, compact summary spacing, side-panel ordering, and mobile breakpoints. Reuse existing tokens and avoid changing button semantics or API behavior.

- [ ] **Step 4: Run mentor contracts and syntax checks**

Run `python -m pytest backend/tests/test_mentor_selection.py backend/tests/test_mentor_match_skill.py backend/tests/test_frontend_workspace_layout_contract.py -q` and `python -m compileall -q backend`.

### Task 4: Implement the party activity workbench layout

**Files:**
- Modify: `frontend/js/views/party.js`
- Modify: `frontend/assets/styles.css`
- Modify: `backend/tests/test_frontend_workspace_layout_contract.py`

- [ ] **Step 1: Add independent party workbench regions**

Keep the party route separate. Wrap the political status, filters, activity list, materials, participation records, and profile in `party-workbench`; add a summary strip from already-loaded `political`, `activities`, and record data without new API calls.

- [ ] **Step 2: Replace the three-column activity card grid with the workbench list/rail**

Keep every existing activity action data attribute and detail modal. Use a primary activity list and a secondary rail for learning materials/participation records; leave the full profile panel below. Preserve registration, cancellation, sign-in, attachment download, and political-status edit handlers.

- [ ] **Step 3: Add responsive party styles**

Use a two-column desktop grid and a single-column mobile layout. Ensure filters become full-width controls below 760px and activity action rows wrap without overflow.

- [ ] **Step 4: Run party contracts**

Run `python -m pytest backend/tests/test_party_activity.py backend/tests/test_party_profile.py backend/tests/test_party_query_skill.py backend/tests/test_frontend_workspace_layout_contract.py -q`.

### Task 5: Update AI configuration and preserve safe error behavior

**Files:**
- Modify: `.env`
- Modify: `.env.example` only if needed to document the existing variable names; never place a real key there.
- Modify: `backend/app/ai/generic_adapter.py` only if focused tests expose an error-classification regression.
- Test: `backend/tests/test_chat_frontend_contract.py` and existing chat service tests.

- [ ] **Step 1: Update the backend-only key**

Set `.env` `AI_API_KEY` to the user-provided value while keeping `AI_BASE_URL=https://api.deepseek.com` and `AI_MODEL=deepseek-chat`. Verify `rg` finds the literal key only in `.env` and not under `frontend/`.

- [ ] **Step 2: Verify the adapter failure path**

Run existing chat tests and a local adapter smoke test with a blocked endpoint or mocked `httpx` connection error. Confirm the stream emits `[AI 请求失败: 无法连接到 AI 服务器，请检查网络]` and does not raise an unhandled exception.

### Task 6: Full verification and visual smoke check

**Files:**
- No production file changes expected.

- [ ] **Step 1: Run the relevant test suite**

Run `python -m pytest backend/tests/test_frontend_*_contract.py backend/tests/test_chat_frontend_contract.py backend/tests/test_mentor_selection.py backend/tests/test_party_*.py -q`.

- [ ] **Step 2: Check app startup and health**

Use the existing running server or start `python run.py`; verify `GET http://127.0.0.1:8000/health` returns success and the frontend static page loads.

- [ ] **Step 3: Inspect responsive DOM/screenshot evidence**

Check desktop and mobile-sized renderings for `#mentorship` and `#party`, confirm no announcement nav/panel remains, and check console logs for new errors. Record the DeepSeek connectivity limitation separately if TCP 443 remains unreachable.

- [ ] **Step 4: Review the diff and sensitive data boundary**

Run `rg -n "sk-[A-Za-z0-9]" frontend backend docs` and confirm no real key appears outside `.env`; inspect the final file diff for unrelated changes.
