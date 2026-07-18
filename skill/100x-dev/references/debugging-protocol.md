# Debugging Protocol — escaping the slop spiral

**Trigger:** output is broken AND your fix attempts are making it worse or moving the breakage around. That feeling of "every fix breaks something else" = you're in the spiral. The cause is almost never the model; it's a poisoned context plus vague fix requests. Stop prompting harder.

## The protocol

### Step 1 — Freeze
Stop sending "fix it" / "still broken" / "try again" messages. Each one adds noise to a context that's already contradicting itself. Three failed fix attempts on the same bug = mandatory stop.

### Step 2 — Retreat to solid ground
`git log` → find the last commit where things worked → check out / revert to it. You lose minutes of broken work and regain a known-good state. (If you haven't been committing every working step: that's the actual bug in your process. Fix that first.)

### Step 3 — Make the failure precise
Fill this triple. It is the single highest-leverage act in debugging:
- **Input/action:** exactly what was done (steps, data, environment)
- **Expected:** what should have happened
- **Observed:** what happened instead — exact error text, exact wrong behavior

Can't fill it? Then the real problem is observability. In a fresh session: "Add logging around [area] so we can see [the values/flow] when [symptom] happens." Reproduce, collect, then fill the triple.

### Step 4 — Fresh session, clean ammunition
New session (new chat / cleared context). Give it: the rulebook, the spec, SESSION-STATE.md, the precise failure triple, and the relevant files only. Then:

> Explain the mechanism of this failure before proposing any fix. If you cannot determine the mechanism from what I've given you, tell me what evidence you need — do not guess.

A clean context with a precise problem beats a poisoned context with ten fix attempts, essentially always.

### Step 5 — Mechanism before medicine
Do not accept a fix until the explanation of *why it broke* makes sense to you. Fixes without mechanisms are symptom-patches; they're how codebases rot. If the AI's explanation is hand-wavy, ask: "Prove it — add a log line / write a failing test that demonstrates this mechanism."

The failing-test version is gold: mechanism confirmed, regression armed, forever.

### Step 6 — If the same area breaks repeatedly
Three spirals in the same module = the problem is upstream of the code:
- The **plan** was wrong (wrong shape, state in the wrong place, two things fighting over one job) → back to Phase 1, re-plan that component. Rebuilding a component from a corrected plan is usually *faster* than the fourth debugging round — code is cheap now; your time isn't.
- Or the **spec** was ambiguous and the code embodies two interpretations at once → fix the spec sentence, then the code.

### Step 7 — Harvest
Every resolved spiral goes in SESSION-STATE.md's "lessons" line and, if it taught vocabulary, GLOSSARY.md. Spirals are expensive; refuse to pay for the same one twice.

## Quick reference — anti-patterns and replacements

| Anti-pattern | Replacement |
|---|---|
| "It's broken, fix it" | The failure triple (Step 3) |
| Fix attempt #4 in the same chat | Fresh session (Step 4) |
| Accepting "try this, it should work now" | "Explain the mechanism first" (Step 5) |
| Adding special-cases until symptoms stop | Find mechanism or re-plan (Step 6) |
| Debugging on top of uncommitted changes | Revert to last good commit (Step 2) |
