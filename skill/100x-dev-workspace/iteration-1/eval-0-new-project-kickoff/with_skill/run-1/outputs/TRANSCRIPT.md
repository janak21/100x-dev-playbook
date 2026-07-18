# TRANSCRIPT — Expense Tracker, Session 1 (2026-07-18)

Methodology: 100x Dev skill (spec-driven, plan-first, small verified steps, review gates, teach-as-you-go). The user was not available for back-and-forth, so at each point where I'd normally ask, I stated the questions and proceeded on explicit assumptions. Everything below is in the order it happened / was communicated.

---

## Step 0 — Read the skill

Read SKILL.md, the rulebook/spec/session-state templates, the review checklist, and the prompt patterns before doing anything else.

## Step 1 — Project setup (no code yet)

Created `expense-tracker/` with:
- `AGENTS.md` (the rulebook, Project Context filled in) + `CLAUDE.md` pointing to it
- `SPEC.md` — see step 2
- `SESSION-STATE.md`, `GLOSSARY.md`, `.gitignore`
- `git init`; committed. (5 commits total this session, one per working step — git is the undo button.)

**Communicated to the user:** "Before writing any code I'm setting up three files that will outlive this conversation: a rulebook (AGENTS.md) that governs how any AI works on this repo, a spec (SPEC.md) that is the source of truth for what we're building, and a session-state file so any future session resumes with full context."

## Step 2 — The interview I would have run (spec questions + stated assumptions)

**Communicated:** "Normally I'd interview you one question at a time before building. You're not here, so here are the 8 questions and the assumption I'm proceeding with for each — every one is cheap to change later, and they're recorded in SPEC.md §10 so we don't lose them:"

1. **Currency?** → Assumed INR (₹). One line of code to change.
2. **Which categories do you actually use?** → Assumed: Food, Groceries, Transport, Housing, Utilities, Entertainment, Health, Shopping, Other. Fixed list, because free-text categories fragment your totals ("food" vs "Food").
3. **Phone or desktop?** → Assumed both; layout is responsive.
4. **Is it OK that clearing browser data loses everything in v1?** → Assumed yes; export/backup is the natural v2 feature.
5. **Edit past expenses, or is delete + re-add enough?** → Assumed delete + re-add.
6. **Allow future-dated expenses (tomorrow's rent)?** → Assumed yes.
7. **Roughly how many expenses/month?** → Assumed under 200 (verified the app handles 10,000+ anyway).
8. **Will you eventually want this hosted/synced?** → Assumed local-only for now; the architecture doesn't block hosting later.

Also filled the spec's **out-of-scope** list aggressively (no login, no server, no charts, no budgets, no sync, no custom categories) — everything cut is slop avoided.

## Step 3 — Phase 1: Plan (presented before any code)

**Communicated the plan:**

- **Technology:** plain HTML + CSS + vanilla JavaScript, data in the browser's localStorage (a small key-value store built into every browser). *Why:* you're not a strong developer — this runs by double-clicking a file, has zero dependencies, zero build steps, no accounts, nothing to deploy, and every file stays readable. *Alternative rejected:* React/Vite (build tooling, node_modules) or Python+SQLite (needs a server running). For a single-user tracker they add moving parts and no capability.
- **Components / data flow:** `index.html` (structure) → `app.js` (glue: reads the form, calls logic, renders results) → `expenses.js` (ALL logic: validation, monthly math, storage parsing — pure functions with no browser code, so they're testable in Node) → localStorage (persistence). Tests: `expenses.test.js` (logic) + `smoke.mjs` (headless walkthrough of the real page).
- **Files to create:** the six above plus `style.css` and `README.md`.
- **Build order:** (1) logic + tests, (2) UI with add/list/delete, (3) verification gates.
- **The 3 riskiest parts:**
  1. **Data loss** — localStorage is per-browser; also, a bug that writes garbage could destroy history. Mitigation: validate everything read from storage, and if it's unreadable, warn and pause saving rather than overwrite.
  2. **Money math** — floating-point sums drift (0.1 + 0.2 ≠ 0.3 in binary). Mitigation: sum in whole paise as integers.
  3. **Losing the habit** — if logging an expense takes more than ~10 seconds you'll stop. Mitigation: one screen, date pre-filled, category/date kept between entries.

**Invited interrogation (the questions you should ask me about this plan):**
- "What's the simplest version that still meets the spec — what did you include that we could cut?" (Answer: the note field and delete-confirm are the only extras; both are cheap. Everything else is spec-mandated.)
- "What happens when the thing you depend on fails?" (Here the only dependency is localStorage — so: what exactly happens when it's full, blocked, or corrupted? That question shaped the design: warn + pause saving, never wipe.)
- "Where does this break first as data grows 100x?" (Full re-render per change — fine to ~10k items, measured later.)

## Step 4 — Phase 2, increment 1: logic module + tests

Wrote `expenses.js` (validation, add/delete, monthly totals, storage parse/serialize) and `expenses.test.js` — 21 tests covering the happy path, empty submits, non-numeric/negative/absurd amounts, fake dates like 2026-02-30, script-tag injection in category, float-exact totals, corrupted-storage handling, and double-delete. Ran `node --test`: **21/21 pass**. Committed.

**Teach note communicated:** "expenses.js contains only *pure functions* — output depends only on input, nothing else is touched. That's what lets us test the app's brain without opening a browser. Money is summed in integer paise because computers store decimals in binary and drift on sums. Storage is treated as a *trust boundary* — data crossing it gets re-validated, because a truncated write or hand-edit would otherwise crash the app or silently corrupt totals."

## Step 5 — Phase 2, increment 2: the UI

Wrote `index.html`, `style.css`, `app.js`. Choices communicated:
- Date pre-filled with **local** today (using `toISOString()` would give UTC — the wrong date before 5:30am in India; classic bug, avoided deliberately).
- After adding, the form keeps your category/date and refocuses amount — logging several expenses in a row is the common case.
- User text (the note) enters the page via `textContent` only, never `innerHTML`, so `<script>` in a note displays as text instead of running (*XSS*, cross-site scripting).
- If saved data is corrupt or storage is blocked, a visible warning appears and **saving pauses** so the app can never overwrite data it couldn't read.
- Months with no expenses show a friendly *empty state*, not a blank screen.

**Verification (not "the code looks right" — the flow works):** built a headless smoke test (`smoke.mjs`, jsdom — a fake browser DOM inside Node, dev-only, not an app dependency) that loads the real index.html, runs the real app.js, and walks: add valid expense → totals update → persisted; invalid submit → specific error, nothing saved; switch to empty month → empty state, ₹0.00; delete + stale second click → gone, no crash; reload with corrupted storage → warning shown, corrupt data left untouched. **SMOKE OK.** Committed.

**How you verify yourself:** double-click `index.html`, add an expense, refresh the page (it's still there), try submitting garbage, switch months.

## Step 6 — Phase 3: review gates (from the skill's checklist)

- **Gate 1 (right thing?):** all 3 spec flows work on the running page; nothing extra built (no charts, no edit — per spec §6).
- **Gate 2 (hostile input):** empty/wrong-type/absurd inputs → specific errors (tested); script tags rendered inert (tested); double-delete safe (tested); refresh safe (persisted); 10,000 items → monthly totals in 1 ms, load-validate in 17 ms.
- **Gate 3 (failure behavior):** storage blocked/full/corrupt each produce a specific visible message; zero silent catch blocks; no internals leaked in messages.
- **Gate 4 (security floor):** secrets grep — none; `innerHTML` grep — none (one comment); no SQL/server/auth to check; single-user local data.
- **Gate 5 (tests):** 21 unit + smoke test; unhappy paths outnumber happy paths.
- **Gate 6 (understanding):** explanations above + GLOSSARY.md (9 terms fed this session).
- **Gate 7 (housekeeping):** 4 commits with "why" messages; SPEC decision log has 4 entries; glossary updated.

**Confession (communicated unprompted):**
1. Double-clicking "Add" very fast creates a duplicate entry — not debounced. Low risk (delete fixes it), and a synchronous local save can't truly distinguish a double-click from an intentional identical re-add.
2. Two tabs open at once: last tab to save wins; an add in the other tab can be lost. Real but low-risk for one person.
3. Currency ₹/en-IN is hardcoded (assumption #1) — one line to change.
4. Delete uses the browser's plain `confirm()` dialog — dependable but ugly. Cosmetic debt.
5. No export yet — clearing browser data still loses everything (spec risk #1, deliberately deferred to v2).

All five recorded in SESSION-STATE.md as known debts.

## Step 6.5 — A caught bug (and the fix, communicated honestly)

A final end-to-end re-check of `node --test` showed **1 failing test**: the smoke test file was originally named `smoke-test.mjs`, and Node's test runner auto-runs anything matching `*-test.mjs` — so it tried to run the jsdom walkthrough and failed whenever the optional jsdom install was absent. That would have greeted the user with a bogus red failure on a green project.

**Fix:** renamed it to `smoke.mjs` (outside the runner's glob), updated README, re-ran both suites: `node --test` → 21/21 pass with zero installs; `node smoke.mjs` (with jsdom) → SMOKE OK. Committed with the why in the message.

**Communicated:** "This is exactly why the verify phase re-runs everything from a clean state at the end — the bug wasn't in the app, it was in how you'd experience the tests."

## Step 7 — Phase 4: session summary (communicated, and saved to SESSION-STATE.md)

- **Decisions and why:** no-framework stack (readability/zero setup), logic/UI split (testability), integer-paise money math (float drift), fixed categories (totals fragmentation), warn-and-pause on bad storage (never destroy unread data).
- **Known debts:** the 5 confessed above.
- **Next session:** confirm the 8 assumptions in SPEC.md §10 (currency and category list most likely to change), then build CSV/JSON export as the top v2 feature — it's the mitigation for the biggest risk (data loss).

**Closing message to the user:** "v1 is **done pending your review** — open `index.html` and use it. Before next session, skim SPEC.md §10 and tell me which assumptions are wrong; that's the whole agenda for session 2. You should be able to explain every file in this repo — if any of the explanations above didn't land, ask me to re-explain before we build more."

---

## Final state

`expense-tracker/` — 13 files, 5 commits, 21 passing tests + passing smoke test:
process files (AGENTS.md, CLAUDE.md, SPEC.md, SESSION-STATE.md, GLOSSARY.md, README.md), app (index.html, style.css, app.js, expenses.js), tests (expenses.test.js, smoke.mjs), .gitignore.
