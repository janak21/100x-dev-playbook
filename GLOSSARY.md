# Glossary — personal, permanent, append-only

<!--
Your compounding vocabulary asset (PLAYBOOK.md: vocabulary is the highest-leverage,
fastest-to-acquire skill of the four). Every term the AI teaches you (Rulebook rule 16,
Explanation Extraction prompt #5d) gets one line here. Review it weekly; pick one term
per week to study deeply. Seeded with ten to set the format.
-->

| Term | One-line meaning | Why it matters to me |
|---|---|---|
| Idempotent | Safe to run twice — same result as running once | Double-clicks and retries stop being bugs |
| Race condition | Two things modify shared state; outcome depends on timing | Where "works on my machine" bugs live |
| Trust boundary | Any line data crosses from outside your control to inside | Everything crossing it gets validated (Rulebook 7) |
| N+1 query | Fetching a list, then querying once per item instead of once for all | The classic "why is this page slow" |
| Debounce | Wait until input stops before acting | Search boxes that don't fire per keystroke |
| Optimistic update | Show success in the UI immediately, reconcile with server after | Why good apps feel instant |
| Migration | Versioned, scripted change to database structure | How you change data shape without losing data |
| Pagination | Fetch results in pages, not all at once | Apps that survive 10,000 rows |
| Server-side validation | Checking input on the server even if the UI already checked | The UI check is decoration; attackers skip it |
| Eval | A scored test suite for AI-feature quality | The difference between an AI product and an AI demo |
