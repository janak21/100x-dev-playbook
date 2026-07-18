# Mechanics — why the playbook works, at the transformer level

<!--
Twelve mechanical facts about how LLMs actually work, each paired with the tactic
it implies. None of this is secret — it's published research. The edge is that
almost nobody applies it consistently. Disproportionately effective on small/weak
models. Companion to PLAYBOOK.md; cross-references PROMPT-PATTERNS.md.
-->

## 1. The model is a distribution-matcher; your prompt selects the distribution
An LLM predicts the next token conditioned on everything before it. A sloppy, vague prompt statistically resembles low-quality documents, so the model completes in kind — it matches register, it doesn't judge you.
**Tactic:** write prompts in the register of the output you want — precise vocabulary, structured, like a senior engineer's ticket. The single most underrated lever, and free.

## 2. Compute per token is fixed; hard problems need tokens before the answer
Each token gets one forward pass. The model cannot "think longer" on a hard token — reasoning happens in the visible tokens (or hidden reasoning tokens).
**Tactic:** force reasoning before conclusions. Never ask "answer, then justify" — autoregression means the justification rationalizes whatever was sampled first; it doesn't audit it.

## 3. Attention is not uniform; the middle of context is the worst real estate
Models attend best to the start and end of context ("lost in the middle" — a measured effect).
**Tactic:** instructions at the top, bulk data in the middle, the 2–3 critical constraints restated at the very end. That's positioning, not redundancy.

## 4. Negation is weak; every token mentioned becomes an active feature
"Don't use placeholder data" activates the concept of placeholder data.
**Tactic:** positive instruction plus replacement behavior: "use only fields present in the schema; if one is missing, stop and ask."

## 5. Examples beat descriptions, and format consistency does much of the work
Two or three input→output examples act as an in-context program; the model infers the task from the pattern. Research finding most miss: format consistency of the examples matters as much as their content.
**Tactic:** for any repeatable task, show 2–3 exact examples instead of a paragraph of prose. For small models this is the dominant lever.

## 6. Output is a sample, not a verdict
Decoding is stochastic. One answer feels authoritative; it's one draw from a distribution.
**Tactic:** on hard/important questions, run the prompt 3 times and pick the best or majority-vote (published as "self-consistency" — reliably beats single attempts). Almost nobody does this.

## 7. The conversation IS the model's entire state; errors compound autoregressively
No hidden memory of your intent exists — only the token sequence. One bad early output conditions everything after it. This is the mechanism behind the slop spiral, and why fresh sessions work (PLAYBOOK.md Part 3–4).
**Tactic:** edit history instead of appending to it. Deleting a failed attempt from context beats adding "no, that's wrong" after it — the failed tokens otherwise keep conditioning every future token.

## 8. Verification is a different, easier task than generation
Critiquing is close to classification; generating is search through a vast space. The same model, in a fresh context, asked to review its own output will catch errors it just made — the task changed, not the model.
**Tactic:** separate critic passes, always in fresh context (PROMPT-PATTERNS.md #9–10). Cross-model review is stronger still: models share fewer blind spots with each other than with themselves.

## 9. The model has no reliable access to its own uncertainty
Confident tone is what training optimizes; it is uncorrelated with correctness.
**Tactic:** never read tone as signal. Force uncertainty into content: "list the assumptions you made and rank them by how sure you are."

## 10. Tokenization makes some trivial things hard
Models see tokens, not characters — hence embarrassing failures at letter-counting, long arithmetic, exact string edits.
**Tactic:** route anything computational to code ("write and run a script that...") instead of asking for the answer directly. With weak models: always.

## 11. Constraints reduce failure surface
Open-ended generation maximizes the degrees of freedom in which errors can occur.
**Tactic:** demand strict output shapes — exact JSON schema, fixed template, "respond with only X." Small models flail open-ended and perform respectably when boxed in.

## 12. Small models fail at composition, not at pieces
A small model can't do a 10-step task in one prompt but can do each step.
**Tactic:** decompose into a pipeline of narrow calls with schema-constrained handoffs (rule 11) and verification between stages (rule 8). This is how you get near-frontier results from weak models — the closest thing to an actual cheat code.

---

**The honest caveat:** none of this is secret and none of it is mine — it's the published mechanics of the architecture. The durable edge is not knowing these twelve things; it's being in the small minority that applies them on every task. Knowledge arbitrages away; discipline compounds.
