# TRANSCRIPT — "How do I know my summarizer prompt is actually good?"

Chronological record of what was done and communicated.

## 1. Read the skill

Read `100x-dev/SKILL.md` first, as instructed. The task matched its "When output quality matters
more than usual" rule verbatim: *"Reusable prompts, AI features, agent pipelines: read
references/evals.md. Nothing 'works' — it works at a rate; build the case set."* Read
`references/evals.md` in full, plus `references/prompt-patterns.md` (relevant: prompt anatomy,
#9 red-team thinking for the hostile cases, #10 second-opinion → cross-model judge).

## 2. Diagnosed the user's situation in skill terms

"It seems to work when I try it" = an anecdote: n=1, no written criteria, sampled from the easy
middle of the input distribution. The deliverable therefore isn't advice alone — it's a working
eval kit: a 20-case set with pre-written pass criteria, a rubric, a manual scoring path, and an
automated runner. (evals.md threshold: "If you'll run a prompt more than ~10 times, or a user
other than you will trigger it, it deserves an eval" — a team relying on it daily clears both.)

## 3. Stated the questions I would have asked (user unavailable)

Recorded in full in README.md with the assumption adopted for each. Summary:
1. What the team does with the bullets → assumed triage/handoff (issue + ask + urgency).
2. Exact prompt text / runtime → unknown; kit is prompt-agnostic via `PROMPT.txt` + `{{EMAIL}}`.
3. Real emails available? → no; wrote 20 realistic synthetic cases, told user to replace with
   real anonymized ones ASAP.
4. Worst failure mode → assumed missed urgent/legal issue or fabricated fact; rubric makes
   fabrication an automatic fail; cases 15/16/19 designated safety-critical.
5. Threads / languages → covered in hard cases; assumed English output required.
6. Desired behavior on non-emails → assumed "identify, don't invent"; flagged that the current
   prompt may not handle this and the eval will reveal it.
7. Format rules → assumed exactly 3 bullets, ≤30 words each (configurable).
8. Ship bar → assumed ≥18/20 and 3/3 on safety-critical cases, plus a shadow-mode rollout.

## 4. Built the deliverables (per evals.md's minimal + scored + automated eval)

- **README.md** — the method: works-at-a-rate framing, questions/assumptions table, 30-minute
  manual path, scripted path, iteration rules (change ONE thing → rerun ALL 20; every production
  failure becomes a case; rerun on model change), red flags, shadow-mode rollout plan.
- **cases.json** — 20 cases in evals.md's prescribed composition: 10 typical (billing, lockout,
  feature request, bug report, shipping, cancellation, escalation, praise+bug, how-to, invoice),
  5 hard (multi-issue thread with a resolved item, Spanish email, rambling buried ask,
  self-contradicting email, GDPR demand buried in pleasantries), 5 hostile (empty body,
  out-of-office auto-reply, phishing, prompt injection with a detectable payload string,
  misdirected job application). Each case has a one-line pass criterion **written before any
  output was generated**, plus machine-checkable `must_mention_any` / `must_not_contain` terms.
- **rubric.md** — binary PASS/FAIL rubric (fidelity, coverage, case criterion, format with a
  non-email exemption, safety), used identically by human graders and the LLM judge; judge is
  blind to the prompt; includes the "spot-check 20% of judge verdicts" audit obligation.
- **SCORECARD.md** — printable manual scoring sheet with results tally, failure-list section
  (each failure names the constraint to tighten), and a run log enforcing one-change-per-rerun.
- **PROMPT.txt** — placeholder file where the user pastes their real prompt (`{{EMAIL}}` marker);
  ships with a clearly-labeled stand-in so the script runs out of the box.
- **run_eval.py** — ~200-line runner: loads prompt + cases, calls the generator model, applies
  mechanical checks (3 bullets, word cap, required/forbidden strings), then a cross-model blind
  LLM judge; prints rate + failure list + safety-critical status; writes a timestamped
  results JSON as the audit trail. Flags: `--no-judge`, `--cases 16,19`.

## 5. Verified (Phase 3)

Ran offline verification in the sandbox: cases.json parses, exactly 20 cases at 10/5/5
composition, ids 1–20, all cases have criteria; script imports cleanly; bullet extraction and
mechanical checks behave correctly on a good output (pass), a malformed output (3 distinct
failures reported), an obeyed-injection output (forbidden strings caught), and a properly-flagged
empty email (format exemption honored); PROMPT.txt loads with comment lines stripped and the
placeholder present. Could not run the live API portion (no API key in this environment) — the
end-to-end model calls are **done pending the user's run**.

## 6. Confession (things a senior engineer would flag)

- The 20 cases are synthetic. Real inboxes are weirder; README tells the user to substitute real
  anonymized emails and treats the synthetic set as a starting scaffold.
- `must_mention_any` keyword checks are heuristics — a summary could pass them while being wrong
  (which is exactly why the judge layer exists) or phrase a correct idea in unlisted words (which
  would show as a false mechanical failure; the failure message makes this easy to spot and fix).
- Default model names in run_eval.py (`claude-sonnet-4-5` generator, `claude-haiku-4-5` judge)
  are assumptions; both are overridable via env vars, and the user should set the generator to
  whatever their feature actually uses — evaluating a different model than production is
  measuring the wrong distribution.
- Case 12's `must_not_contain: "reembolso completo"` is a weak proxy for "output is in English";
  the rubric/judge carries the real check.
- The ship bar (18/20 + 3/3 safety) is my stated assumption, not the user's decision; README
  says so explicitly.

## 7. What was communicated to the user

Everything in README.md (the primary hand-off document), closing with "done pending your review"
and the prediction that the hostile five (cases 16–20) are where "seems to work" will crack,
because casual testing never includes empty emails or injection attempts.
