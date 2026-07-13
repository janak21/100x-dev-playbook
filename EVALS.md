# Evals — measuring the distribution

<!--
The operational half of the core insight: an LLM output is a sample from a
distribution, so nothing "works" — it works at a rate. This file is the minimal,
tool-agnostic practice for knowing that rate. Applies to: any prompt you reuse,
any AI feature you ship, any agent pipeline. If you'll run a prompt more than
~10 times, or a user other than you will trigger it, it deserves an eval.
-->

## The rule

**Never say "it works." Say "it worked N out of M times on cases that matter."**
Until you have N and M, you have an anecdote.

## Minimal eval, by hand (30 minutes, no code)

Good enough for reusable prompts and small features:

1. **Collect 20 cases.** Real inputs if you have them; realistic ones if not. Composition matters more than volume:
   - ~10 typical cases (the everyday middle of the distribution)
   - ~5 hard cases (long, messy, ambiguous, multilingual, huge)
   - ~5 hostile/edge cases (empty, malformed, adversarial, out-of-scope requests the system should refuse)
2. **Write the pass criteria per case, before running.** One line: what must be true of the output. Deciding after you see outputs is how you grade on a curve without noticing.
3. **Run all 20. Score pass/fail. No partial credit** — partial credit is where self-deception lives. If "partially right" is acceptable in production, make that explicit in the criterion.
4. **Record the rate and the failure list.** The failures are the product: each one tells you which constraint to tighten (see MECHANICS.md — schema? examples? decomposition? routing to code?).
5. **Change ONE thing, rerun all 20.** Never judge a prompt change by the case it was meant to fix — it can fix one case and break four. The rerun is the entire point of having the set.

## Scored eval, with the model as judge (when outputs are subjective)

For quality judgments (tone, helpfulness, summary fidelity) where pass/fail per case isn't mechanical:

- Have a model score each output against a written rubric, in a **fresh context**, ideally a **different model** than the generator (MECHANICS.md #8 — verification is a different task; cross-model judges share fewer blind spots).
- Give the judge the rubric, the input, and the output — never the knowledge of which prompt version produced it (blind grading, same reason as in school).
- Spot-check ~20% of the judge's scores yourself. A judge you've never audited is a rubber stamp.

## Automate when it repeats (Month 4 skill)

Once a feature matters, the hand process becomes a script: cases in a JSON/CSV file, a loop that calls the model, asserts or judge-scores, prints the rate. ~50 lines; the AI writes it in one step of The Loop. From then on, every prompt change is a script run — regression testing for the stochastic parts of your system, exactly parallel to unit tests for the deterministic parts.

## The composition trap (why pipelines need per-stage evals)

Chained steps multiply: ten stages at 95% each ≈ 60% end-to-end. Practical consequences:

- Eval each stage separately, plus end-to-end. When end-to-end drops, per-stage rates tell you where.
- A stage that must be ~100% reliable should not be an LLM call — route it to code (MECHANICS.md #10, #12).
- Raising a weak stage from 90%→99% usually beats raising a strong one from 98%→99.5%. Fix the lowest number first.

## Case file hygiene

- The case set is version-controlled, next to the spec. It grows monotonically: **every production failure becomes a case.** That's the compounding loop — your eval set becomes a fossil record of everything that ever went wrong, and nothing regresses silently.
- Re-run the full set when you change models or a provider updates one under you. Model swaps silently shift distributions; your prompt didn't change, your rates did.

## Red flags that you've stopped measuring

- "I tweaked the prompt and it looks better" (n=1, no criteria)
- The eval set hasn't gained a case in a month while the product shipped features
- You can't state the current pass rate of your most important prompt
- A model upgrade was rolled out because the vendor said it's better

---
**Relation to the rest of the system:** REVIEW-CHECKLIST.md gates one deliverable once; evals gate a behavior continuously. Deterministic code gets tests (Rulebook rule 3); stochastic behavior gets evals. A 100x dev runs both and knows which is which.
