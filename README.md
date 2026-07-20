# The 100x Dev Operating System

A model-agnostic system for extracting expert-level output from AI coding tools. Works with Claude Code, Codex, Cursor, Antigravity, plain chat, and whatever ships next — because it operates on the one layer that never changes: **what information the model receives and what verification you demand back.**

## The core thesis

Models are not the bottleneck. You are. Specifically, three things you control:

1. **Direction** — what you ask for and how precisely (spec quality)
2. **Context** — what the model knows about your project and constraints (context engineering)
3. **Verification** — what you check before accepting output (the anti-slop gate)

A 10x developer using AI beats you today not because of secret prompts, but because they have a compressed vocabulary (they say "add optimistic UI updates with rollback on failure" instead of "make it feel faster"), they smell wrong output instantly, and they never accept unverified code. All three are learnable. This system forces you to learn them.

## Files in this system

| File | What it is | When you use it |
|---|---|---|
| `PLAYBOOK.md` | The operating principles and the loop. The "why." | Read fully once. Re-read monthly. |
| `RULEBOOK.md` | The rules file you give to the AI. Copy into every project as `AGENTS.md`. | Every project, day one. |
| `ROADMAP.md` | 6-month skill-building plan at 10–20 hrs/week. | Weekly planning. |
| `templates/SPEC.md` | Fill this out before any non-trivial build. | Start of every feature/project. |
| `templates/PROMPT-PATTERNS.md` | The prompt structures that produce expert output. | Reference while working. |
| `templates/REVIEW-CHECKLIST.md` | The verification gate. Run before accepting any AI output. | End of every work session. |
| `templates/DEBUGGING-PROTOCOL.md` | What to do when AI output is broken and iterations aren't converging. | When stuck. |
| `templates/SESSION-STATE.md` | Running memory doc so long projects don't decay into slop. | Ongoing projects. |
| `GLOSSARY.md` | Your permanent vocabulary file — the fastest-compounding asset. | Append every session, review weekly. |
| `MECHANICS.md` | Twelve transformer-level facts and the tactics they imply. | Read once; reference when prompts underperform. |
| `EVALS.md` | How to measure prompts and AI features across cases, not anecdotes. | Any prompt you reuse or feature you ship. |

## Install as a skill (fastest path)

The whole procedural side of this system is packaged as an [Agent Skills](https://agentskills.io/specification)-compliant skill in `skill/100x-dev/`. From this repo:

```bash
npx skills add <your-github-username>/100x-dev-playbook
```

This auto-installs into every agent it detects (`.claude/skills/`, `.cursor/skills/`, `.codex/skills/`). The skill activates on build/plan/debug/review tasks and deploys the rulebook into each project as `AGENTS.md` automatically. Benchmarked on 3 task types with 6 process assertions each: 100% with-skill vs 67% baseline on a frontier model, and 89% vs 50% on a small model (Haiku) — a small model with this skill outperformed the frontier model without it.

## How to deploy the rulebook manually in any tool

The industry standard for agent instruction files is `AGENTS.md` (Linux Foundation, supported by 28+ tools). Deployment:

- **Claude Code**: copy `RULEBOOK.md` content into the project's `CLAUDE.md` (or `AGENTS.md` — Claude Code reads both)
- **Codex CLI / most agents**: save as `AGENTS.md` in the project root
- **Cursor**: save as `AGENTS.md`, or `.cursor/rules/core.mdc`
- **Plain chat (Claude.ai, ChatGPT)**: paste it as the first message of the conversation, or into custom instructions / a Project's knowledge
- **Future tools**: whatever the file convention is, the content transfers. The rules are written in plain English with zero tool-specific syntax.

## The one rule above all rules

**Never accept code you can't explain.** Not "explain line by line" — explain what it does, why this approach, and what breaks it. If you can't, your next prompt is "explain this change: what it does, why this way, what are the failure modes." This single habit is what converts AI usage into actual skill. Skip it and in 12 months you'll have shipped things but learned nothing, and you'll still be producing slop — just faster.
