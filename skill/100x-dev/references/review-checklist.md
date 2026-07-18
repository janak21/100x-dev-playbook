# Review Checklist — the Anti-Slop Gate

Run before accepting any significant AI output as "done." Takes 10–15 minutes. This gate is the difference between a demo and a product; roughly 45% of AI-generated changes carry at least one serious security issue, and they *look* clean — plausibility is exactly what models are trained to produce.

You can run most of this by asking the AI itself the questions (it audits honestly when asked directly), then spot-checking by actually using the software.

## Gate 1 — Did it build the right thing?
- [ ] Re-read the spec section for this feature. Does the built thing match, or did it drift?
- [ ] Walk the core flow yourself, as a user, on the actual running software. Not "the code looks right" — the flow works.
- [ ] Anything built that wasn't asked for? (Scope creep is slop's front door.)

## Gate 2 — Hostile-input pass (where slop hides)
Try these on every input/action the feature has:
- [ ] Empty. Submit nothing. Blank fields.
- [ ] Wrong type/shape. Text where numbers go, absurd lengths, emoji, `<script>alert(1)</script>`.
- [ ] Double-submit. Click the button twice, fast.
- [ ] The back button, refresh mid-action, a stale open tab.
- [ ] Big volume: what if there are 10,000 items instead of 10?

## Gate 3 — Failure behavior
- [ ] Kill the thing it depends on (turn off network, use a wrong API key). Does it fail with a useful message or hang/lie/crash?
- [ ] Any silent `catch` blocks or swallowed errors? Ask: "list every place where an error is caught and what happens to it."
- [ ] Do user-facing errors avoid leaking internals (stack traces, file paths)?

## Gate 4 — Security floor
Ask the AI directly, per the Red-Team pattern, plus verify:
- [ ] No secrets in code (grep for `key`, `secret`, `password`, `token`).
- [ ] Every route/endpoint that should require auth actually checks it server-side (not just hidden in the UI).
- [ ] Database queries parameterized; user content escaped where rendered.
- [ ] Anything touching money, auth, or personal data got the full Red-Team Review (PROMPT-PATTERNS.md #9), ideally from a second model.

## Gate 5 — Tests
- [ ] Tests exist and pass.
- [ ] At least one test per unhappy path found in Gates 2–3. AI-written tests default to happy paths; demand the rest.
- [ ] You've read the tests and they test behavior you care about, not implementation trivia.

## Gate 6 — The understanding test (non-negotiable)
- [ ] You can explain every change: what, why this way, what breaks it. If not → Explanation Extraction (PROMPT-PATTERNS.md #5) until you can.
- [ ] Trade-offs confessed and recorded (Confession pattern #6) — either fixed or written into SESSION-STATE.md as known debt.

## Gate 7 — Housekeeping
- [ ] Committed with a message that says why, not just what.
- [ ] SPEC.md decision log updated if any decision was made.
- [ ] New vocabulary → GLOSSARY.md.

---
**Failing a gate is the system working.** Each failure caught here is a bug your users never see and a pattern you'll recognize in the plan phase next time — which is the actual mechanism by which you become the person who "knows where the bugs will be."
