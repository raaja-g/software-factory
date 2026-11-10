# software-factory

This repo is driven by the **software factory**: run `/factory <feature>` or
`/factory next` in Claude Code. See `.claude/skills/factory/SKILL.md` for the loop
and `.claude/agents/` for each agent.

## Stack
Not chosen yet — the first job (see `factory/backlog.md`) bootstraps it.
Once code exists, keep this section current: language, how to run, and the
**test command** (agents rely on it).

## Conventions
- Feature work happens only on `factory/<job-id>` branches; `main` only receives merges.
- `factory/` is factory bookkeeping, owned by the orchestrator — never edited by builders.
- Dashboard: `cd factory && python3 -m http.server 8765` → http://localhost:8765/dashboard.html
