# The Playbook

The principles behind the system. Model-agnostic by design: everything here operates on inputs (what you tell the model) and outputs (what you verify), not on any tool's features. Tool features change every quarter; this doesn't.

---

## Part 1: The mental model

### Why "prompting harder" fails

An AI coding model is a extremely capable engineer with severe amnesia and zero stake in your outcome. It doesn't know your project, your users, or your standards unless told, every time. It optimizes for *plausible-looking completion of your literal request*, not for your actual goal. Every failure you've had — "AI slop, a version that barely works" — traces to one of three gaps:

1. **Specification gap**: you asked for a vague thing, it built a vague thing. "Build me a dashboard" has ten thousand valid interpretations; the model picks the statistically average one. Average = slop, by definition.
2. **Context gap**: it didn't know a constraint that mattered (your data shape, an existing function, a performance requirement), so it hallucinated or contradicted it.
3. **Verification gap**: it produced something 80% right, you couldn't see which 20% was wrong, you asked for fixes in vague terms, and each iteration degraded the code further. This is the slop death spiral, and it's a verification failure, not a model failure.

The entire playbook is closing these three gaps.

### What "100x" actually is

The experienced developer's advantage decomposes into exactly four assets:

- **Vocabulary** — naming what you want ("debounce this input," "make this idempotent," "paginate server-side") collapses the model's search space from thousands of interpretations to one. This is the highest-leverage asset and the fastest to acquire.
- **Architecture sense** — knowing how systems are shaped: where state lives, what talks to what, what happens when a part fails. This is what lets someone review a plan in 60 seconds and say "no, that will break under concurrent writes."
- **Failure pattern recognition** — knowing where bugs live before they appear: boundaries (empty input, huge input, duplicate submission), trust boundaries (anything a user sends), async timing, and state that two things can modify.
- **Taste** — knowing the difference between works and good. Acquired only through exposure: using excellent products attentively and comparing them to yours.

None of these require writing code by hand for years. They require **reviewing code with intent for months**. The AI writes; you interrogate. That's the accelerated path — and it's the whole reason the "never accept what you can't explain" rule exists.

### The incentive trap to avoid

AI tools make it maximally easy to accept output and move on. Every acceptance-without-understanding feels like progress and compounds into nothing. The discipline of this system costs you ~20% speed today and buys you the entire skill curve. People who skip it stay permanently at "can produce a demo, can't produce a product." That's the actual line between the crowd with tool access and the 100x developer — not access, not prompts, but the compounding.

---

## Part 2: The Loop

Every non-trivial piece of work follows the same five phases. This is the professional workflow that has replaced "vibe coding" (its own inventor declared that era over). Skipping a phase is how slop happens.

### Phase 0 — Spec (before touching any AI tool)

Fill out `templates/SPEC.md`. For a small feature this takes 10 minutes; for a project, an hour. It forces answers to: what exactly is being built, for whom, what does "done" mean, what's explicitly out of scope, and what must not break.

If you can't fill out the spec, you don't have a building problem — you have a thinking problem, and the right move is a *conversation* with the AI first ("interview me about this idea, one question at a time, then draft a spec") rather than a build command.

The spec is version-controlled and lives in the repo. It's the source of truth, not the code. When you and the AI make decisions mid-project, update the spec.

### Phase 1 — Plan (the AI proposes, you dispose)

Never let the AI write code as its first act. First prompt is always some form of:

> Read the spec. Propose an implementation plan: components, data flow, files to create/change, technology choices with reasoning, and what could go wrong. Ask me anything ambiguous. Do not write code yet.

Then interrogate the plan. You don't need to be able to write the plan yourself — you need to stress-test it, which is much easier: "What happens if two users do this at once?" "What happens when this API call fails?" "Why this database and not a simpler option?" "What's the simplest version that still meets the spec?"

**The plan review is where 100x lives.** A wrong plan implemented perfectly is worthless; a right plan implemented imperfectly is fixable. Spend your attention here.

### Phase 2 — Build (small, sequenced, checkpointed)

- Break the plan into steps that each produce something **runnable and testable**. Never "build the whole thing." The single biggest predictor of slop is diff size per acceptance.
- One step per prompt. Run it. Verify it. Commit it (git after every working step — non-negotiable; it's your undo button and your fearlessness).
- Tests get written *with* each step, not after. Tell the AI: "write the test first, show me the test, then implement." A test you've read and understood is a spec fragment the model must satisfy.
- When a step works, ask the one-line question: "Any hacks, shortcuts, or things a senior engineer would flag in what you just wrote?" Models are surprisingly honest about their own corner-cutting when asked directly.

### Phase 3 — Verify (the anti-slop gate)

Run `templates/REVIEW-CHECKLIST.md` before considering anything done. Summary of the gate: does it handle empty/wrong/hostile input, does it fail loudly rather than silently, are secrets out of the code, do the tests test unhappy paths, can you explain every change.

Hard data on why this phase is not optional: AI-generated PRs carry ~1.7x more defects than human ones, and roughly 45% introduce at least one OWASP Top 10 security issue. The model's output *looks* clean and confident precisely when it's wrong — plausibility is what it's trained to produce. Verification is your only defense, and it's also your fastest teacher.

### Phase 4 — Learn (the compounding step)

End of each session, 5 minutes: what did the AI get wrong, what vocabulary did you pick up, what would you specify differently next time. Append terms you learned to your personal glossary (keep one file, `GLOSSARY.md`, forever). Update `SESSION-STATE.md` if the project continues.

This phase is why the same playbook makes you better every week while other people plateau. It's also the only phase nobody does.

---

## Part 3: Context engineering

The second discipline. Sessions degrade: after a few hours of back-and-forth, the model's context fills with dead ends and corrections, and it starts contradicting earlier decisions. Rules:

- **Fresh sessions liberally.** When a session goes sideways or gets long (~30+ exchanges), don't push through. Write decisions to `SESSION-STATE.md`, start clean, and have the new session read the state file plus the spec. Knowing when to throw away context is the most underrated skill in agentic work.
- **State lives in files, not in the conversation.** Spec, session state, glossary, rulebook — all on disk, all readable by any tool, any model, any session. The conversation is disposable; the files are the project's memory. This is also precisely what makes the system model-agnostic.
- **Scope what the model sees.** Point it at the relevant files, not the whole repo. Irrelevant context actively degrades output.
- **One task per session when possible.** Don't let a bug-fix session drift into a feature session; the contexts poison each other.

---

## Part 4: Escaping the slop spiral

When output is broken and iterating makes it worse, you're in the spiral. Recognize it by the feeling: "each fix breaks something else." Protocol (full version in `templates/DEBUGGING-PROTOCOL.md`):

1. **Stop prompting "fix it."** Vague fix requests on top of misunderstood code compound the misunderstanding.
2. Revert to the last committed working state (this is why you commit every step).
3. Make the failure precise: what exact input, what expected, what observed. If you can't state that triple, first ask the AI to add logging so you can.
4. Start a fresh session with the spec, the state, and the precise failure triple. A clean context with an exact problem statement outperforms a poisoned context with ten fix attempts, essentially always.
5. If it recurs: the problem is upstream — the plan was wrong, or the spec was ambiguous. Fix it there, not in code.

---

## Part 5: What differentiates you (since everyone has the tools)

The honest answer to your own question. Tools are commoditized; these are not:

1. **Problem selection.** Slop-producers build what's easy to build (another todo app, another chatbot wrapper). Choose problems where *you* know something the average person doesn't — your industry, your workflow pain, your users. Domain insight is the moat; AI cannot supply it.
2. **The last 20%.** Everyone can generate the 80% demo. Error states, edge cases, speed on bad networks, empty states, onboarding — the unglamorous last 20% is invisible in a demo, decisive in a product, and skipped by everyone without a verification discipline. Your Phase 3 *is* the differentiation.
3. **Judgment density.** Over months of running The Loop, you accumulate thousands of reviewed decisions. That's the same corpus a senior engineer has — acquired by review instead of authorship. Nobody skipping verification accumulates anything.
4. **Total cost of ownership awareness.** Code is now cheap; maintenance, security, and support are not ("free as in puppies"). Building less, deliberately, is a senior move the tools will never suggest.

---

## Part 6: Model-agnosticism, explicitly

Why this survives the next five years of model releases:

- It manipulates only two universal interfaces: **the instruction text you provide** and **the artifacts you verify**. Every coding model of any generation consumes instructions and emits artifacts. Better models raise the ceiling of what a given spec yields; they don't change the loop.
- All memory is **files in the repo** (spec, rulebook, state, glossary) in plain markdown — the one format every tool reads today (`AGENTS.md` is a Linux Foundation standard) and any future tool will read, because the repo is where the code is.
- As models improve, rebalance, don't rewrite: you'll delegate bigger steps per prompt and interrogate at a higher level (architecture instead of functions). The phases stay. Verification never becomes optional — it just moves up the stack, because a more capable model produces more plausible wrongness, not less.
