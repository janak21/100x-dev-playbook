# Roadmap — 6 months, 10–20 hrs/week

Path: web apps as the base skill, AI-native features on top (your "generalist" pick). Structured as projects, not courses — judgment comes from shipping and reviewing, not from watching tutorials. Every project runs The Loop (PLAYBOOK.md Part 2) in full; the projects are the curriculum, the Loop is the teacher.

**Stack decision, made for you:** TypeScript + Next.js + Postgres (via Supabase or similar) + deployed on Vercel. Reasons: largest AI training corpus (models are strongest here), one language across frontend/backend, employable, and every AI-product pattern layers onto it. Don't relitigate this for 6 months; stack-shopping is procrastination with extra steps.

**Weekly rhythm (at ~15 hrs):** ~10 hrs building via The Loop · ~2 hrs reading code the AI wrote (Explanation Extraction on old work) · ~2 hrs studying one concept from your GLOSSARY.md deeply · ~1 hr using excellent products attentively (taste training — articulate *why* they feel good).

---

## Month 1 — The Loop on rails
**Project: a personal tool you'll actually use** (expense tracker, workout log, bookmark manager — pick pain you have). Deliberately unoriginal: novelty budget goes to process, not product.

Do: full spec → plan interrogation → small steps with git commits → every gate of the review checklist → deploy publicly. Yes, deploy month 1 — a URL changes your relationship to quality.

Skills forced: git basics, what frontend/backend/database each do, deploy pipeline, reading errors without panic.

**Exit test:** the tool is live, you use it weekly, and you can explain every file in the repo (sit with the AI: "walk me through the repo; quiz me"). If you can't explain it, month 1 isn't done — this test is the whole point.

## Month 2 — The unhappy 20%
**Project: same tool, hardened + one more small app to re-run the Loop faster.** Add: real auth, hostile-input handling everywhere, empty/loading/error states for every screen, mobile usability.

This month exists because the last 20% is what separates you from every demo-builder (PLAYBOOK.md Part 5). It's grinding. That's the moat forming.

Skills forced: auth concepts (sessions, tokens), validation, the security floor (Rulebook 7–10), reading the review checklist without needing it.

**Exit test:** hand the app to a friend with zero instructions and watch them use it. Every confusion or breakage they hit = a gate you skipped. Under three findings = pass.

## Month 3 — Data and other people's computers
**Project: something with a real external API + meaningful data** (e.g., a dashboard pulling from an API you care about — stocks, fitness, content stats — with history stored and charted).

Skills forced: API integration and its failure modes (timeouts, rate limits, bad responses), data modeling (the skill that quietly determines whether apps stay maintainable), background jobs, caching basics.

**Exit test:** unplug scenarios — API down, API slow, API returns garbage — and your app degrades politely in all three. Plus: you can sketch your data model on paper and defend it.

## Month 4 — AI-native building
**Project: an AI-powered feature or product** (RAG over documents you own, an agent that does a real multi-step task, a smart layer on a month-1–3 project). Now the domain you're most curious about, on top of foundations that can hold it.

Skills forced: calling model APIs, prompt design *as software* (versioned, tested), RAG/embeddings basics, evals (how do you know the AI feature works? — the question that separates AI products from AI demos), token cost awareness, streaming UX.

**Exit test:** an eval script that measures your AI feature's quality on 20+ cases, and you know your cost per user-action to the cent.

## Month 5 — Ship to strangers
**Project: the differentiated one.** Apply PLAYBOOK Part 5: a problem where YOU have domain insight from your job/life that an average builder doesn't. Small scope, real users (5–20 strangers or colleagues), feedback loop.

Skills forced: problem selection, onboarding design, analytics, acting on feedback without whiplash, saying no (spec section 6 becomes your best friend).

**Exit test:** at least 5 people you don't know have used it more than once. Retention, however tiny, is the first real signal you've built product and not demo.

## Month 6 — Judgment consolidation
No new project. Instead: the Simplification Pass (PROMPT-PATTERNS #12) on everything you've built · rewrite your worst module from its corrected plan · red-team all deployed apps with a second model · write (publicly if you can) the 10 things you now know that month-1-you didn't. Writing it is the test that you know it.

**Exit test — the 100x checkpoint.** You should now be able to: take a vague idea to a spec in an hour; interrogate an AI's plan and catch a real flaw in it; predict 2 of the 3 places a feature will break before building it; and look at AI output and *feel* wrong before you can articulate it (that feeling is taste — articulating it comes next).

---

## After month 6
Two compounding paths, not exclusive: go deeper on AI-native engineering (agents, pipelines, evals — scarcer skills, less commoditized) while shipping increasingly ambitious products; and raise delegation altitude — bigger steps per prompt, interrogation at architecture level — as models improve under you. The Loop doesn't change; your position in it rises.

## Failure modes for THIS roadmap (know them now)
- **Tutorial drift:** consuming content instead of shipping. Cap: if a week has zero commits, the week failed regardless of what you watched.
- **Novelty addiction:** abandoning at 70% for a shinier idea. The last 30% is where all the learning is; finishing is the skill.
- **Gate-skipping under time pressure:** "just this once" on the review checklist. The checklist under pressure is the only checklist that matters.
- **Stack-shopping relapse:** re-opening the tools/framework decision. New tools get evaluated in month 7, not mid-project.
- **Burnout via 20+ hr weeks:** you chose 10–20 for a reason. Six sustained months beats two heroic ones; the compounding needs duration, not intensity.
