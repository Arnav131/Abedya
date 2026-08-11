# Abhedya — Full Remediation Task List (Single-Pass Execution Prompt)

**Audience:** Autonomous coding agent (Codex / Antigravity / similar).
**Mode:** Execute end-to-end without asking clarifying questions. Every decision point below already has a resolved default — follow it. Do not pause to confirm scope; just implement, then self-verify using the acceptance criteria listed per task, then move to the next task.
**Repo:** `Arnav131/Abhedya` (Django backend in `api/`, React+Vite frontend in `frontend/`, misc scratch code in `local_llm/`).
**Do not** re-explain the codebase back to the user, do not ask "should I proceed", do not produce a summary mid-way — just work through the list top to bottom and report a final changelog at the end.

---

## Global Rules (apply to every task below)

1. Never break existing working functionality (zero-knowledge encryption flow, vault CRUD, JWT auth, heuristic auditor) while fixing other things. Run/inspect existing tests before and after each change.
2. Never log, print, or persist plaintext secrets, passwords, or honeypot fake-secret values anywhere (console, files, git history). This constraint is already respected in the existing code — preserve it.
3. Prefer environment-variable-driven configuration over hardcoded values for anything environment-specific.
4. After each numbered task, run the relevant test/verification command listed in that task's "Verify" line before moving on. If a test file doesn't exist yet, create it as part of that task — don't defer test-writing to a separate pass.
5. Commit granularly: one commit per numbered task below, with a commit message matching the task title. Do not squash everything into one commit.
6. Do not add new heavy dependencies unless explicitly instructed in a task.
7. Final deliverable: a single changelog block at the very end listing every file touched and every task's pass/fail verification result. No other commentary needed.

---

## PRIORITY 1 — Pitch/Demo-Breaking Issues (fix these first, in order)

### 1.1 Make the hosted honeypot LLM status truthful and visible in the product UI
**Problem:** `render.yaml` forces `HONEYPOT_LLM_BACKEND=fallback` and `HONEYPOT_USE_LLM_ON_REGISTRATION=False` in production because `torch`/`transformers` aren't in `requirements.free.txt`. The frontend never surfaces which tier is actually active, so the product silently claims "AI LLM honeypot" while running pure `secrets`-module fallback in production.

**Fix:**
- Add a small frontend component (or extend `SafetySettings.jsx` / relevant settings page) that calls `GET /api/honeypot/llm-status/` and displays the `effective_mode` value (`ollama` / `transformers` / `fallback`) as a visible badge, e.g. "Deception Engine: Fallback Mode (local LLM not connected in this deployment)".
- Do not hide or misrepresent fallback mode — the badge text must accurately reflect whichever mode `llm-status` reports.
- Backend: confirm `HoneypotLLMStatusView` (`api/vault/honeypot_views.py`) already exposes `effective_mode`; if the field name differs from what's documented, keep backend as source of truth and adjust frontend to match actual response shape (inspect the view before wiring the UI).

**Verify:** Manually call `/api/honeypot/llm-status/` against a running local server with `HONEYPOT_LLM_BACKEND=fallback` set, confirm the UI badge renders "Fallback" correctly. Add a frontend test (or Playwright/RTL snapshot if a test runner exists in `frontend/`; if none exists, skip UI test and just verify manually, noting this in the changelog) confirming the badge component renders each of the three states correctly given mocked API responses.

---

### 1.2 Add automatic JWT access-token refresh (currently completely missing)
**Problem:** `frontend/src/utils/auditApi.js`, `vaultCrypto.js`, and the fetch calls inside `Sidebar.jsx`, `ItemDetails.jsx`, `SafetySettings.jsx`, `AddItem.jsx`, `SecurityHealth.jsx`, `MyVault.jsx` all read `sessionStorage.getItem("sv_access_token")` directly and call `fetch()` raw, with no refresh-on-401 logic. Refresh token is stored (`sv_refresh_token` — confirm exact key by grepping) but never used.

**Fix:**
- Create one centralized API client module: `frontend/src/utils/apiClient.js`, exporting an `apiFetch(path, options)` function that:
  1. Attaches `Authorization: Bearer <sv_access_token>` automatically.
  2. On a `401` response, calls `POST /api/auth/token/refresh/` with the stored refresh token, stores the new access token in `sessionStorage`, and retries the original request exactly once.
  3. If refresh also fails (refresh token expired/invalid), clears session storage and redirects to the login route (inspect `App.js`/router for the correct login path — do not guess a path that doesn't exist in the routing config).
- Replace every raw `fetch(`${API_BASE}...)` call in the files listed above (`Sidebar.jsx`, `auditApi.js`, `vaultCrypto.js`, `ItemDetails.jsx`, `SafetySettings.jsx`, `AddItem.jsx`, `SecurityHealth.jsx`, `MyVault.jsx`) with calls through `apiFetch`. Preserve each call's existing request body/method/headers exactly — only change the transport layer, not the API contract.
- Do not change encryption logic inside `vaultCrypto.js` — only the network-call wrapper.

**Verify:** Simulate an expired access token (manually set an invalid/expired JWT in `sessionStorage`) and confirm a vault list request transparently refreshes and succeeds without the user noticing. Add a unit test for `apiClient.js` covering: (a) success on first try, (b) 401 → refresh → retry succeeds, (c) 401 → refresh fails → redirect/logout triggered.

---

### 1.3 Environment-configure the frontend API base URL for the actual deployed backend
**Problem:** `frontend/src/utils/config.js` defaults to `http://localhost:8000/api` if `VITE_API_BASE_URL` isn't set. Confirm whether the deployed frontend (Vercel/Netlify/wherever it's hosted) actually has this env var set.

**Fix:**
- Add a `.env.production` (or platform-specific env config, e.g. `vercel.json` / `netlify.toml` env section — inspect repo for which host is actually used; if no hosting config file exists in the repo, add a `.env.example` documenting `VITE_API_BASE_URL` and note in `README.md` that production deploys must set it) pointing `VITE_API_BASE_URL` at the deployed Render backend URL.
- Do not hardcode the production URL into `config.js` itself — keep it env-driven.

**Verify:** Build the frontend (`npm run build`) with `VITE_API_BASE_URL` set to a dummy value and confirm the built bundle references that value, not `localhost:8000`.

---

## Status Tracker

| Task | Description | Status |
|---|---|---|
| 1.1 | Make hosted honeypot LLM status truthful and visible in the product UI | Not started |
| 1.2 | Add automatic JWT access-token refresh in frontend API client | Completed |
| 1.3 | Environment-configure the frontend API base URL | In progress |
| 2.1 | Stop honeypot generation from blocking user registration | Completed |
| 2.2 | Backend test coverage for auth, vault CRUD, audit analysis | Completed |
| 2.3 | Frontend test coverage with Vitest + RTL and login/add-item flow tests | Completed |
| 3.1 | Quarantine duplicate local_llm directory | Completed |
| 3.2 | Document password-model weight files | Completed |
| 3.3 | Align privacy/security messaging copy across frontend | Completed |
| 3.4 | Enable SMTP breach alerts configuration in render.yaml | Completed |

## PRIORITY 2 — Reliability / Correctness

### 2.1 Stop honeypot generation from blocking user registration
**Problem:** `api/vault/signals.py` runs `_generate_and_store_honeypots()` synchronously inside the `post_save` signal on `User` creation. If Ollama is configured and slow/unreachable, `MAX_RETRIES=3` with backoff inside `honeypot_llm.py`'s `OllamaClient.generate()` can add several seconds of latency directly to the registration HTTP request, and a full timeout (`OLLAMA_TIMEOUT`, default 30s) could make registration appear to hang or fail.

**Fix:**
- If Celery (or another task queue) is already a dependency in `requirements.txt` — check first — move `_generate_and_store_honeypots(user_id)` into an async task and dispatch it from the signal handler instead of calling it inline.
- If no task queue exists in the project (expected, based on current `requirements.txt`), do NOT introduce a new heavy dependency (Celery + broker) just for this. Instead: spawn the generation in a background `threading.Thread` (daemon=True) from the signal handler so the HTTP response for registration returns immediately while generation completes in the background. Wrap the threaded call in the same try/except-and-log pattern already used in `_generate_and_store_honeypots` so failures still can't crash anything.
- Add a short comment in `signals.py` explaining that this is an interim solution and a proper task queue (Celery/RQ) should replace it before scaling past hackathon/demo usage.

**Verify:** Time a registration request with `HONEYPOT_LLM_BACKEND=ollama` pointed at an unreachable Ollama URL before and after the fix — after the fix, registration should return in well under 1 second regardless of Ollama's reachability. Add a backend test asserting the registration endpoint responds quickly (assert response time or assert the response doesn't block on a mocked slow honeypot generator).

---

### 2.2 Backend test coverage (currently only `vault/tests.py`, 98 lines, honeypot-trigger-only)
**Problem:** No tests exist for auth, vault CRUD ownership isolation, encryption/decryption round-trip consistency (frontend-side, but at minimum test that ciphertext/iv/salt fields round-trip through the API unmodified), or the `/api/audit/` detector chain.

**Fix — add these test files (Django `TestCase` / DRF `APITestCase`):**
- `api/vault/tests.py` (extend existing file, don't replace): add tests for
  - Register → login → obtain JWT → access protected vault endpoint succeeds.
  - Unauthenticated request to any vault endpoint returns 401.
  - User A cannot read/update/delete User B's vault entries (ownership isolation) — create two users, two entries, assert cross-access returns 403/404.
  - Vault entry create/list/detail/update/delete each work and persist exactly the ciphertext/iv/salt fields sent (no server-side mutation of these opaque fields).
- `api/ai_engine/tests.py` (new file): add tests for `analyze()` in `auditor.py` covering at minimum:
  - A JWT-shaped string → `identified_type == "JSON Web Token (JWT)"`, `risk_level == "critical"`.
  - An AWS access key pattern (`AKIA` + 16 chars) → critical risk.
  - A GitHub `ghp_...` token → critical risk.
  - A Stripe `sk_live_...` key → critical risk, `sk_test_...` → warning, not critical.
  - A weak password (e.g. `"password"`, `"123456"`) → high risk score, `risk_level in {"critical","warning"}`.
  - A strong random password (e.g. generated via `secrets.token_urlsafe(24)`) → low risk score, `risk_level in {"safe","info"}`.
  - Empty string input → `identified_type == "Empty Input"`, `risk_score == 0`.
  - Confirm `analyze()` never raises on malformed/very long/unicode input — add a fuzz-style test with a few edge-case strings (very long string >10000 chars, string with only emoji/unicode, string with null bytes).

**Verify:** `python manage.py test` from `api/` must pass with 0 failures, and must include the new test modules above. Report the total test count added.

### 2.3 Frontend test coverage (currently none detected)
**Fix:**
- Check `frontend/package.json` for an existing test runner (Vitest/Jest). If none is configured, add Vitest (lightweight, Vite-native — this is the one new dependency allowed by this task list) plus `@testing-library/react`.
- Add tests for: login flow (mock API, assert token stored), Add Item flow (assert `auditSecret` is called with debounce and result renders), and the new `apiClient.js` refresh logic from Task 1.2 (already covered there, just ensure it lives under this same test runner setup).

**Verify:** `npm test` (or whatever script name you configure) runs and passes in `frontend/`.

---

## PRIORITY 3 — Cleanup / Consistency (do last, lowest risk of breaking anything)

### 3.1 Remove or clearly quarantine the duplicate `local_llm/` directory
**Problem:** `local_llm/ai_engine/honeypot_llm.py` and `local_llm/honeypot_test/` are a disconnected, smaller duplicate of the real, wired-in `api/ai_engine/honeypot_llm.py`. This creates ambiguity about which is authoritative.

**Fix:** Move the entire `local_llm/` directory to `experiments/local_llm_scratch/` and add a one-line `README.md` inside it stating it is not imported by the live Django app and is kept only for reference/prototyping history. Do not delete it outright (it may contain useful prototyping notes) — just clearly quarantine it so no future contributor confuses it with the real integration.

**Verify:** `grep -r "local_llm" api/ frontend/` returns no import references (confirm nothing in the live app actually imports from the old path before moving it).

### 3.2 Document the two password-model weight files
**Problem:** `bilstm_password_weights.pth` (repo root, legacy) and `api/ai_engine/weights/password_rnn.pt` (current) both exist and are both handled by compatibility code in `pytorch_model.py` (`_model_kind == "bilstm_compat"` branch), but nothing documents why both exist.

**Fix:** Add a short section to `api/ai_engine/README.md` (create this file if it doesn't exist) explaining: `password_rnn.pt` is the current model format loaded by default; `bilstm_password_weights.pth` is a legacy checkpoint from an earlier architecture kept for backward-compatibility inference via `tokenize_fixed()`/`BILSTM_COMPAT_SEQ_LEN`; state which one is actually loaded by default in production (check `DEFAULT_WEIGHTS_PATH` resolution logic in `pytorch_model.py` to confirm before writing this).

**Verify:** No code change required here beyond the new README — just confirm the documented behavior matches what `_resolve_weights_path()` actually does by reading that function, not by guessing.

### 3.3 Align privacy/security messaging copy across all frontend pages
**Problem:** Some pages state "100% local, nothing ever leaves your device" style claims while `AddItem.jsx` correctly discloses that plaintext is sent ephemerally to `/api/audit/` for risk analysis. This inconsistency was already self-identified in `PROJECT_STATUS_REPORT_FOR_JUDGES.md` section 5.6.

**Fix:** Grep all frontend copy (`grep -rn "never leaves\|100% local\|zero-knowledge\|local only" frontend/src`) and normalize the wording to one accurate, consistent statement across every page: encryption/decryption is 100% client-side and the server never sees plaintext of stored vault data; the one explicit exception is the real-time audit feature, which ephemerally receives plaintext for analysis only and never persists it.

**Verify:** Re-run the grep after the change and confirm every match uses consistent, accurate wording (paste the before/after list of matched lines in the final changelog).

### 3.4 Enable SMTP breach alerts for any environment where credentials are actually configured
**Problem:** `HONEYPOT_ALERT_ENABLED=False` is hardcoded in `render.yaml`, meaning even if `SMTP_EMAIL`/`SMTP_PASSWORD` are later configured, alerts stay off unless this flag is manually flipped.

**Fix:** Change the `render.yaml` env var default so `HONEYPOT_ALERT_ENABLED` is read from an actual env var with `sync: false` (like `SMTP_EMAIL`/`SMTP_PASSWORD` already are) instead of a hardcoded `"False"` string, so ops can turn it on without a code change once real SMTP credentials are provisioned. Leave the effective default behavior as disabled until credentials exist (don't force it on), just make it configurable rather than hardcoded off.

**Verify:** Confirm `render.yaml` no longer hardcodes `"False"` for this key and instead mirrors the `sync: false` pattern used by `SMTP_EMAIL`.

---

## Final Step — Changelog Output

After completing all tasks above, output a single markdown table:

| Task | Files Changed | Verification Result |
|---|---|---|
| 1.1 | ... | Pass/Fail + brief note |
| 1.2 | ... | ... |
| ... | ... | ... |

Nothing else after this table. Do not re-summarize the whole project again.
