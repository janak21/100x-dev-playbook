# Evaluating Your Support-Email Summarizer Before Your Team Relies On It

"It seems to work when I try it" is the classic trap with LLM prompts: it works on the
easy cases you happened to try. This kit gives you a repeatable way to find out whether
it's *actually* good — before a missed refund request or a hallucinated order number
erodes your team's trust in it.

## What's in this folder

| File | Purpose |
|---|---|
| `README.md` | This guide — the evaluation workflow |
| `QUESTIONS_AND_ASSUMPTIONS.md` | Questions I'd ask you, and the assumptions made in your absence |
| `prompt.txt` | Placeholder for YOUR prompt — paste it here (see below) |
| `eval/rubric.md` | The definition of a "good" 3-bullet summary, with pass/fail criteria |
| `eval/test_emails.jsonl` | 20 test emails: normal cases + edge cases + traps |
| `eval/run_eval.py` | Runs your prompt on every test email, applies automated checks + an LLM judge, writes a report |
| `eval/review_sheet.csv` | Manual grading sheet if you'd rather review by hand (or have no API access) |

## The workflow (about 1–2 hours total)

### Step 0 — Paste your prompt into `prompt.txt`
Replace the placeholder. Keep the `{{EMAIL_BODY}}` token where the email should be
inserted. If your prompt lives in a tool (ChatGPT, Zapier, etc.), copy the text verbatim —
evaluating a paraphrase tells you nothing.

### Step 1 — Define "good" (already drafted for you)
Read `eval/rubric.md` and edit it to match what your team actually needs. A summary is
only "good" relative to a job. The draft rubric says a good summary is:
1. **Faithful** — nothing invented; no fabricated order numbers, amounts, or promises.
2. **Complete** — captures the customer's core issue, the ask, and urgency/severity signals.
3. **Actionable** — a teammate could triage the ticket from the bullets alone, without opening the email.
4. **Format-compliant** — exactly 3 bullets, concise, no preamble.

### Step 2 — Build a real test set (the single highest-value step)
The included `eval/test_emails.jsonl` has 20 synthetic emails covering the failure modes
that actually bite summarizers (see the file — each case says what it's testing). **But
synthetic data is a starting point, not a substitute.** As soon as you can:
- Pull 30–50 *real* emails from your inbox (strip names/emails if needed).
- Deliberately include the ugly ones: long threads, angry rants, three-issues-in-one,
  non-English, near-empty messages, wrong-recipient mail.
- Add them to the JSONL file in the same format (`id`, `category`, `email`, `key_facts`, `traps`).

Rule of thumb: if every email in your test set produces a good summary on the first try,
your test set is too easy, not your prompt too good.

### Step 3 — Run the eval
```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
cd eval
python run_eval.py                 # generate + auto-check + LLM-judge + report
python run_eval.py --skip-judge    # just generate outputs + format checks (cheaper)
python run_eval.py --skip-generate # re-grade existing outputs after editing the rubric
```
Outputs land in `eval/outputs/`:
- `results.jsonl` — every email, the summary produced, and all scores
- `results.csv` — same thing, spreadsheet-friendly
- `summary.md` — pass rates, average scores, and the worst failures to look at first

The script does two layers of checking:
- **Deterministic checks** (free, objective): exactly 3 bullets? No preamble? Bullets under
  the length cap? Non-empty?
- **LLM-as-judge** (a second model call per case): scores faithfulness, coverage of the
  known `key_facts`, and actionability 1–5, and flags hallucinations and prompt-injection
  compliance. The judge sees the rubric and the email, not just the summary.

### Step 4 — Calibrate the judge with human eyes (do not skip)
An LLM judge is a power tool, not a truth oracle. Take 10 cases — mix of judge-passes and
judge-fails — and grade them yourself using `eval/review_sheet.csv`. If you disagree with
the judge more than ~2 times out of 10, tighten the rubric wording and re-run
`--skip-generate`. Once you and the judge mostly agree, you can trust the aggregate numbers.

### Step 5 — Set a launch bar and decide
Suggested acceptance criteria before the team relies on it:
- **100%** on safety-critical checks: zero hallucinated facts, zero prompt-injection
  compliance, urgent/legal/security emails always flagged in the bullets.
- **≥ 95%** format compliance (exactly 3 clean bullets).
- **≥ 90%** of cases rated 4+ on faithfulness and coverage.
- Every failure individually reviewed — one "bad" case that's actually harmless is fine;
  one case that silently drops a legal threat is a launch blocker regardless of averages.

If it misses the bar: fix the prompt (the failures tell you exactly what to add — e.g.
"if the email mentions legal action, deadlines, or security issues, that must be a
bullet"), then **re-run the whole eval**. Never judge a prompt edit by eyeballing one email —
that's how you got here.

### Step 6 — Don't stop at launch
- Freeze this test set as your **regression suite**: any future prompt or model change must
  re-run it and match or beat the previous scores before shipping.
- Add a lightweight feedback loop for the team (even a 👍/👎 or a Slack emoji works).
  Every real-world failure becomes a new test case in the JSONL.
- Re-run the suite when the underlying model version changes — model updates can shift
  behavior even if your prompt didn't change.

## No API access? Manual path
Run your prompt by hand (in whatever tool you use) on each email in
`eval/test_emails.jsonl`, paste outputs into `eval/review_sheet.csv`, and grade each row
against `eval/rubric.md`. Slower, but the discipline is identical: fixed test set, written
rubric, every case graded, failures reviewed.
