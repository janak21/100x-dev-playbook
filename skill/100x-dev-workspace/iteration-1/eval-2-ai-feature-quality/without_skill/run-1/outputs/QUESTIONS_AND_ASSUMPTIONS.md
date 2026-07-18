# Questions I Would Ask You (and the assumptions I made instead)

You weren't available for back-and-forth, so here are the questions that would sharpen
this setup, each with the assumption I proceeded on. Correct any wrong assumption and the
kit adapts easily.

## 1. What is the exact prompt, and where does it run?
**Why it matters:** The eval must test the real prompt verbatim, on the real model.
**Assumption:** You can paste your prompt into `prompt.txt` and it runs on Claude via the
Anthropic API (model configurable via `ANTHROPIC_MODEL`, default `claude-sonnet-4-5`).
If you use OpenAI or a no-code tool, the test set and rubric still apply — only the
API-call section of `eval/run_eval.py` needs swapping, or use the manual review sheet.

## 2. What does your team DO with the bullets?
**Why it matters:** "Good" for triage (must surface urgency and the ask) differs from
"good" for a daily digest (must be scannable) or for CRM logging (must capture IDs).
**Assumption:** Triage/handoff — a teammate reads the 3 bullets instead of the email and
decides what to do next. The rubric's "actionability" criterion reflects this.

## 3. What's the cost of a bad summary?
**Why it matters:** Determines which failures are launch blockers vs. annoyances.
**Assumption:** Worst failures are (a) hallucinated facts the team acts on, (b) silently
dropping urgency/legal/security/churn signals. These are held to a 100% bar; style issues
to a ~90–95% bar.

## 4. What do your real emails look like?
**Why it matters:** The test set should mirror your actual distribution — length,
languages, threads, product vocabulary.
**Assumption:** English-primary B2C/B2B SaaS-style support inbox with occasional Spanish,
long threads, and messy messages. The 20 synthetic cases reflect this; replace/augment
with 30–50 real anonymized emails as soon as possible (Step 2 of the README).

## 5. Do you have historical emails I could use?
**Assumption:** No, so the dataset is synthetic but adversarial — built around known
summarizer failure modes (hallucination traps, prompt injection, multi-issue emails,
sarcasm/sentiment traps, PII, near-empty input).

## 6. Who can spend ~1 hour on a human grading pass?
**Why it matters:** The LLM judge must be calibrated against human judgment once before
its numbers are trusted.
**Assumption:** You (or a senior support teammate) can grade ~10 cases using
`eval/review_sheet.csv`. This is the one step with no shortcut.

## 7. Volume and monitoring after launch?
**Assumption:** Enough volume that spot-checking everything is impractical, so the plan
includes a frozen regression suite plus a lightweight thumbs-up/down feedback loop from
the team (README Step 6).
