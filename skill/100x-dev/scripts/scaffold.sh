#!/usr/bin/env bash
# Deterministic project setup for the 100x-dev loop.
# Usage:  bash scripts/scaffold.sh [target-dir]
# Creates AGENTS.md (from the bundled rulebook), CLAUDE.md pointer, SPEC.md,
# SESSION-STATE.md, a .gitignore, and an initial git commit — without spending
# model tokens re-deriving boilerplate every project.
# Only for projects meant to live. One-off scripts skip this entirely.
set -euo pipefail

TARGET="${1:-.}"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$TARGET"
cd "$TARGET"

copy_if_absent() {  # src dst
  if [ -e "$2" ]; then echo "  skip   $2 (exists)"; else cp "$1" "$2"; echo "  create $2"; fi
}

echo "Scaffolding 100x-dev project in: $(pwd)"

copy_if_absent "$SKILL_DIR/assets/AGENTS-rulebook.md" AGENTS.md
copy_if_absent "$SKILL_DIR/assets/SPEC-template.md" SPEC.md
copy_if_absent "$SKILL_DIR/assets/SESSION-STATE-template.md" SESSION-STATE.md

if [ ! -e CLAUDE.md ]; then
  printf 'See AGENTS.md — single source of truth for this project.\n' > CLAUDE.md
  echo "  create CLAUDE.md (pointer, not a copy)"
else
  echo "  skip   CLAUDE.md (exists)"
fi

if [ ! -e .gitignore ]; then
  printf '.env\n.env.*\n__pycache__/\nnode_modules/\n*.log\n.DS_Store\n' > .gitignore
  echo "  create .gitignore"
fi

if [ ! -d .git ]; then
  git init -q -b main 2>/dev/null || { git init -q; git checkout -q -b main 2>/dev/null || true; }
  git add -A
  if git commit -qm "Scaffold: rulebook, spec, session state" 2>/tmp/scaffold_git_err; then
    echo "  create git repo + initial commit"
  else
    # Fail loudly rather than reporting a commit that did not happen.
    echo "  WARN   git repo created but the initial commit FAILED:" >&2
    sed 's/^/         /' /tmp/scaffold_git_err >&2
    echo "         Fix with: git config user.name 'You'; git config user.email 'you@example.com'" >&2
    echo "         Then:     git add -A && git commit -m 'Scaffold'" >&2
  fi
else
  echo "  skip   git init (repo exists)"
fi

cat <<'NEXT'

Next, in order:
  1. Fill AGENTS.md "Project Context" and SPEC.md (interview the user if it can't be filled).
  2. Commit. Then Phase 1: propose a plan, invite interrogation, write no code yet.
NEXT
