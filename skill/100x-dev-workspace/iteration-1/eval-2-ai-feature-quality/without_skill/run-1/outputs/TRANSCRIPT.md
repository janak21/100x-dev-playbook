# TRANSCRIPT

Task: User built a prompt that summarizes customer support emails into 3 bullet points
for their team. It "seems to work" when they try it. They asked how to make sure it's
actually good before the team relies on it, and to set up whatever is needed. User was
not available for back-and-forth.

## 1. Stated the questions I would have asked

Since no back-and-forth was possible, I stated the clarifying questions up front and
proceeded on explicit assumptions (full detail in `QUESTIONS_AND_ASSUMPTIONS.md`):

1. Exact prompt text and where it runs (model/API/no-code tool)?
   → Assumed: pasteable into `prompt.txt`, runs on Claude via Anthropic API (configurable).
2. What does the team do with the bullets (triage vs digest vs CRM logging)?
   → Assumed: triage/handoff — bullets replace reading the email.
3. Cost of a bad summary?
   → Assumed: worst failures are hallucinated facts and dropped urgency/legal/security/
   churn signals; held to a 100% bar.
4. What do real emails look like (length, language, threads, PII)?
   → Assumed: English-primary SaaS-style inbox with occasional Spanish, threads, mess.
5. Any historical emails available for a test set?
   → Assumed no; built a 20-case synthetic adversarial dataset and told the user to
   replace/augment with 30–50 real anonymized emails as the highest-value next step.
6. Who can spend ~1 hour on human grading to calibrate the LLM judge?
   → Assumed the user or a senior support teammate can grade ~10 cases.
7. Volume and post-launch monitoring?
   → Assumed enough volume to need a frozen regression suite + lightweight team
   feedback loop.

## 2. Diagnosed the core problem and framed the approach

"It works when I try it" = anecdotal testing on easy cases. The fix is a repeatable
evaluation: (a) a written definition of "good" (rubric), (b) a fixed test set including
edge cases and traps, (c) automated + LLM-judge grading, (d) human calibration of the
judge, (e) explicit launch bar, (f) regression suite + feedback loop after launch.

## 3. Files created (all in this outputs folder)

- `README.md` — the full workflow: paste prompt → tune rubric → build/extend test set →
  run eval → calibrate judge with human review → apply launch bar → keep the set as a
  regression suite and add a team feedback loop. Includes a no-API manual path.
- `QUESTIONS_AND_ASSUMPTIONS.md` — the 7 questions above with stated assumptions.
- `prompt.txt` — placeholder the user replaces with their verbatim prompt; uses an
  `{{EMAIL_BODY}}` insertion token. Includes an example of the expected shape.
- `eval/rubric.md` — definition of a good summary: 5 hard pass/fail requirements
  (H1 faithfulness/no hallucination, H2 no prompt-injection compliance, H3 critical
  signals never dropped, H4 exactly-3-bullets format, H5 graceful handling of
  empty/spam/misdirected email) plus 3 scored dimensions (coverage, nuance,
  actionability, 1–5) and a suggested launch bar (100% on H1–H3, ≥95% format,
  ≥90% rated 4+ on coverage/actionability).
- `eval/test_emails.jsonl` — 20 test emails with `key_facts` and `traps` per case:
  baseline refund; angry churn threat with deadline; multi-issue email; long quoted
  thread; vague "it's not working"; Spanish billing issue; prompt-injection attempt;
  PII oversharing (card/SSN); empty email; misdirected personal email; positive
  feedback; legal/FTC threat with exact figures; technical API detail (numbers-swap
  trap); follow-up chaser on existing ticket; neutral cancellation (reverse sentiment
  trap); cross-account security exposure; sarcasm; dense-numbers invoice discrepancy;
  bug-vs-feature ambiguity; urgent welfare-related lockout.
- `eval/run_eval.py` — self-contained script (anthropic SDK): generates summaries from
  the user's prompt for all cases, runs deterministic format checks (exactly 3 bullets,
  no preamble, word cap, non-empty), runs an LLM judge fed the rubric + email +
  key facts, and writes `outputs/results.jsonl`, `outputs/results.csv`, and
  `outputs/summary.md` with pass rates, average scores, and launch-blocking failures.
  Supports `--skip-judge` (cheap format-only run) and `--skip-generate` (re-judge after
  rubric edits). Model configurable via `ANTHROPIC_MODEL` / `ANTHROPIC_JUDGE_MODEL`.
- `eval/review_sheet.csv` — manual grading sheet pre-filled with all 20 case IDs and
  what each tests; used to calibrate the LLM judge (grade ~10 cases by hand) or as the
  full manual path if the user has no API access.

## 4. Verification performed

Ran in the sandbox: `py_compile` on `run_eval.py` passed; loaded the dataset (20 cases,
all with required fields); unit-tested `format_checks` on good output, preamble-polluted
output, empty output, and numbered-list bullets — all behaved correctly; verified the
judge prompt template formats without errors.

## 5. What I communicated to the user (summary of guidance)

- Anecdotal success is not evidence; you need a fixed test set, a written rubric, and
  every case graded — before the team relies on it and after every prompt/model change.
- The single highest-value action: replace the synthetic emails with 30–50 real
  anonymized ones, keeping the ugly cases.
- Do not skip human calibration of the LLM judge (~10 cases); an uncalibrated judge
  gives confident nonsense percentages.
- Launch bar: zero tolerance for hallucination, injection compliance, and dropped
  critical signals; ~95% format; ~90% quality; every individual failure reviewed.
- After launch: freeze the test set as a regression suite, add a thumbs-up/down team
  feedback loop, and re-run on model version changes.
