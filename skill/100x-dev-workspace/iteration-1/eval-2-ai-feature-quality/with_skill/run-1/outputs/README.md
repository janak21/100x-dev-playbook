# Is my summarizer prompt actually good? — An eval kit

You built a prompt that turns customer support emails into 3 bullet points, and it "seems to work"
when you try it. Here's the uncomfortable truth that drives everything in this folder:

> **An LLM output is a sample from a distribution. Nothing "works" — it works at a rate.**
> "It worked when I tried it" is an anecdote (n=1, no criteria). Before your team relies on it,
> you need to be able to say: **"It passed N out of 20 cases that matter, and here are the failures."**

This folder contains everything needed to get that number in about 30 minutes by hand, or in
~2 minutes with a script once you plug in your prompt.

---

## Questions I would have asked you (and the assumptions I made instead)

You weren't available for back-and-forth, so each question comes with the assumption I proceeded on.
**If any assumption is wrong, edit the case set and rubric to match reality — they're just text files.**

| # | Question | Assumption made |
|---|----------|-----------------|
| 1 | What does your team *do* with the 3 bullets — triage? handoff? ticket notes? | Triage/handoff: bullets must capture (a) the core issue, (b) what the customer wants, (c) urgency or next action. |
| 2 | What's the exact prompt text and where does it run (which model/API, or a chat UI)? | Prompt is a template you paste an email into, running on the Anthropic API. The script takes your prompt from `PROMPT.txt` with an `{{EMAIL}}` placeholder — works regardless of wording. |
| 3 | Do you have real emails I can use as test cases? Any PII constraints? | Not provided, so I wrote 20 realistic synthetic ones. **Replace/augment with real (anonymized) emails ASAP — real inputs are always weirder than synthetic ones.** |
| 4 | What's the worst failure mode for your team? | A missed urgent issue (legal deadline, angry churn-risk customer) or a **fabricated fact** the team acts on. The rubric treats fabrication as an automatic fail. |
| 5 | Single emails or whole threads? Multiple languages? | Mostly single emails, occasionally threads and non-English; the hard cases cover both. Assumed team works in English, so bullets should be in English regardless of input language. |
| 6 | What should the prompt do with non-emails — empty bodies, auto-replies, spam? | It should *say what the thing is* ("auto-reply, no action needed") rather than invent 3 bullets about nothing. If your current prompt doesn't handle this, the eval will show you — that's the point. |
| 7 | Always exactly 3 bullets, and how long may each be? | Exactly 3, each ≤ ~30 words. Adjust `MAX_BULLET_WORDS` in the script if your standard differs. |
| 8 | What pass rate is "good enough" to roll out? | ≥ 18/20 (90%) overall, **and zero failures on the safety-critical cases** (#15 legal deadline, #16 empty, #19 prompt injection) — a missed one of those costs more than a mediocre summary of a routine email. |

---

## What's in this folder

| File | What it is |
|------|------------|
| `README.md` | This file — the method. |
| `cases.json` | 20 test cases: 10 typical, 5 hard, 5 hostile/edge. Each has a **pass criterion written before any output was seen** (deciding after you see outputs is how you grade on a curve without noticing). |
| `SCORECARD.md` | Printable manual scoring sheet for the 30-minute, no-code path. |
| `rubric.md` | The grading rubric — used by you when scoring by hand, and verbatim by the LLM judge in the script. |
| `PROMPT.txt` | Placeholder — **paste your actual prompt here**, keeping the `{{EMAIL}}` marker where the email goes. |
| `run_eval.py` | ~200-line runner: loads cases, calls the model with your prompt, runs mechanical checks + LLM-judge, prints the pass rate and failure list. |

---

## Path A — the 30-minute manual eval (no code)

1. Open `cases.json` (or `SCORECARD.md`, which lists the same cases).
2. For each of the 20 cases, paste the email into your prompt wherever you normally run it.
3. Score each output **pass/fail** against the case's criterion + `rubric.md`. **No partial credit** —
   partial credit is where self-deception lives. If "mostly right" is acceptable in production,
   rewrite the criterion to say so explicitly.
4. Record the rate and, more importantly, the **failure list**. The failures are the product:
   each one tells you exactly which constraint to tighten in your prompt.

## Path B — the scripted eval (~2 min per run, repeatable)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pip install anthropic
# 1. Paste your real prompt into PROMPT.txt (keep {{EMAIL}})
python run_eval.py                 # runs all 20, prints rate + failures, writes results_<timestamp>.json
python run_eval.py --no-judge      # mechanical checks only (free-ish, catches format breaks)
python run_eval.py --cases 16,19   # rerun specific cases while debugging
```

The script does two layers of checking:
- **Mechanical** (code, deterministic): exactly 3 bullets, bullet length, required facts mentioned,
  forbidden strings absent (e.g., the injection payload).
- **Judge** (a *different* model, fresh context, blind to your prompt wording): grades fidelity —
  no fabricated facts, core issue + ask + urgency captured. Models share fewer blind spots across
  model families, and a judge that saw your prompt would grade sympathetically.
- **Spot-check ~20% of the judge's verdicts yourself.** A judge you've never audited is a rubber stamp.

---

## The iteration rules (this is where most people go wrong)

1. **Change ONE thing in the prompt, then rerun ALL 20.** Never judge a prompt change by the one
   case it was meant to fix — it can fix that case and silently break four others. The full rerun
   is the entire point of having the set.
2. **Every production failure becomes a new case.** When a teammate says "this summary missed the
   point," add that email (anonymized) + a pass criterion to `cases.json`. The set grows
   monotonically into a fossil record of everything that ever went wrong — nothing regresses silently.
3. **Rerun the full set whenever you change models, or the provider updates one under you.**
   Your prompt didn't change; your rates did.
4. Keep `cases.json` in version control next to the prompt itself.

## Red flags that you've stopped measuring

- "I tweaked the prompt and it looks better" (n=1, no criteria)
- The case set hasn't gained a case in a month while the team uses this daily
- You can't state the current pass rate off the top of your head
- You switched models because the vendor said the new one is better

## Rollout recommendation

1. Run the eval, fix to ≥ 90% with zero safety-case failures.
2. **Shadow period (1–2 weeks):** team sees the bullets *next to* the full email, not instead of it,
   and flags bad summaries (each flag → new case).
3. Only then let the bullets stand alone — and keep a one-click "summary was wrong" path forever,
   because that's your case-set feed.

Done pending your review — the eval will tell you whether the prompt is good; my guess is the
hostile five (cases 16–20) will surprise you, because "seems to work when I try it" almost never
includes trying an empty email or an injection attempt.
