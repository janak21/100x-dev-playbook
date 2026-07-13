# Prompt Patterns

The reusable structures. Model-agnostic: these work because of *what information they force into the exchange*, not because of magic words. Adapt freely; keep the structure.

The universal anatomy of a strong prompt: **context** (what exists) + **intent** (what you want and why) + **constraints** (what must/mustn't happen) + **output shape** (what form the answer takes) + **verification hook** (how you'll check it). Weak prompts are missing 3+ of these.

---

## 1. The Interview (when your idea is fuzzy)
Use before writing a spec. Makes the AI extract precision from you instead of you guessing.

> I want to build [rough idea]. Before anything else, interview me: one question at a time, focusing on what I actually need, who uses it, and what I'm not thinking about. After ~8 questions, draft a spec using this template: [paste SPEC.md]. Flag anything I said that seems contradictory or naive.

## 2. The Plan Request (Phase 1, every project)
> Read SPEC.md. Propose an implementation plan: components and how they connect, data flow, files to create, technology choices with one-line reasoning each, build order, and the 3 riskiest parts. Ask me anything ambiguous. Do NOT write code yet.

## 3. The Plan Interrogation (where judgment gets built)
Stress-test any plan with these — they work without deep technical knowledge:
> - What happens when [external service] is down or slow?
> - What happens if two users do [action] at the same time?
> - What's the simplest version that still meets the spec? What did you include that we could cut?
> - Where will this break first as usage grows 100x?
> - If a security researcher attacked this, where would they start?
> - Argue against your own plan: what would a critical senior engineer object to?

## 4. The Scoped Step (Phase 2, every build prompt)
> Next step: [one step from plan]. Constraints: [relevant rules — e.g., "no new dependencies"]. Touch only [files]. Write the test first and show me it before implementing. When done, tell me exactly how to run and verify.

## 5. The Explanation Extraction (the learning engine)
After any accepted change:
> Explain what you just built: (a) what it does in plain language, (b) why this approach over the obvious alternative, (c) the 2 most likely ways it breaks, (d) any term you used that a non-developer should learn, with a one-line definition each.

Append (d) to your GLOSSARY.md. This is how vocabulary compounds.

## 6. The Confession (after every working step)
> Any hacks, hardcoded values, skipped edge cases, or things a senior engineer would flag in what you just wrote? Be specific; don't defend them, just list them.

## 7. The Precise Bug Report (never say "it's broken, fix it")
> Bug. Input/action: [exactly what you did]. Expected: [what should happen]. Observed: [what happened, exact error text]. Started after: [last change if known]. First: explain the mechanism of this failure. Then propose the fix. Don't write code until the explanation makes sense to me.

If you can't fill in the triple: "Add logging around [area] so we can capture what's actually happening when [symptom]."

## 8. The Fresh-Session Boot (context engineering)
First message of any new session on an ongoing project:
> Read AGENTS.md, SPEC.md, and SESSION-STATE.md. Summarize in 5 lines where the project stands and what's next, so I can confirm you've got it. Then we'll continue with: [today's goal].

## 9. The Red-Team Review (before anything faces real users)
> Act as a hostile security reviewer and a picky QA engineer. Attack this feature: malformed input, missing auth, injection, what happens under double-submits and slow networks. List findings ranked by severity, with a one-line fix each. Do not soften findings.

## 10. The Second Opinion (cheap, high-value, tool-agnostic)
Paste a diff or plan into a *different* model than the one that wrote it:
> Review this [plan/code] written by another AI for [context]. Find: bugs, security issues, overcomplication, and anything that will bite in maintenance. Rank by importance.

Models share blind spots with themselves, much less with each other. This is the closest thing you have to a colleague's code review.

## 11. The Taste Builder (UI/UX, where slop is most visible)
Never say "make it look good." Instead:
> Here's the interaction: [flow]. Reference quality bar: how [Linear / Stripe / iOS Settings — pick a product you admire in this category] handles similar. Specify: empty state, loading state, error state, and what happens on slow networks. Mobile first. No decorative elements that don't carry information.

The habit behind the prompt: when you use a product that feels great, stop and articulate *why* — then it becomes vocabulary you can specify.

## 12. The Simplification Pass (run monthly on any living project)
> Read [module/project]. Propose deletions: dead code, unnecessary abstractions, dependencies we barely use, features nobody needs. What would this look like with 30% less code and identical behavior?

Code is now cheap to produce and expensive to own. Deleting is the most senior move available.
