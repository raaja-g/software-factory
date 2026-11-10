---
name: factory
description: Run the software factory — take a feature through spec → build → 4 parallel reviews → approval → merge. Use for "/factory <feature>", "/factory next", "/factory approve <job-id>", "/factory rework <job-id> <note>".
argument-hint: <feature> | next | approve <job-id> | rework <job-id> <note>
---

# Software Factory — Orchestrator

You (the session running this skill) are the **orchestrator**. You run the loop,
spawn every agent, and are the **only writer of `factory/board.json`**.
Agents get their context from files, never from this conversation, and each
writes only its own file.

Arguments: `$ARGUMENTS`

## The loop

```
feature → spec-writer → builder ⇄ [security | ux | ui | code] (max 2 rounds) → approver
                                                                     APPROVE → merge to main
                                                                     ESCALATE → needs-human
```

| Step     | Agent (subagent_type) | Model  | Writes                                   |
|----------|-----------------------|--------|------------------------------------------|
| spec     | `spec-writer`         | opus   | `factory/jobs/<id>/spec.md`              |
| build    | `builder`             | opus   | `factory/jobs/<id>/build.md` + commits   |
| review   | `reviewer-security`   | opus   | `factory/jobs/<id>/round-<n>/review-security.md` |
| review   | `reviewer-ux`         | sonnet | `.../round-<n>/review-ux.md`             |
| review   | `reviewer-ui`         | sonnet | `.../round-<n>/review-ui.md`             |
| review   | `reviewer-code`       | sonnet | `.../round-<n>/review-code.md`           |
| approve  | `approver`            | opus   | `factory/jobs/<id>/decision.md`          |

`MAX_ROUNDS = 2`

## Preflight (every run)

- If the repo has no commits yet (`git rev-parse --verify main` fails), make the
  initial commit on `main`: `git add -A && git commit -m "factory: initial scaffold"`.
- Agents run in the background; after spawning one, wait for its completion
  notification before moving on. Never guess an agent's result.

## Parse the command

- `next` → open `factory/backlog.md`, take the first `- [ ]` item, mark it `- [~]`
  (in progress), then run it as a new job. If none, say the backlog is empty and stop.
- `approve <job-id>` → go to **Human approve**.
- `rework <job-id> <note>` → go to **Rework**.
- anything else → the whole argument string is the feature description; run a **new job**.

## Board updates

Read `factory/board.json`, change only the job you're working on, write it back.
Update it at **every** transition below (the dashboard polls it). Job shape:

```json
{
  "id": "003-rate-limiting",
  "title": "Add rate limiting to the API",
  "branch": "factory/003-rate-limiting",
  "stage": "spec | build | review | approve | needs-human | merged",
  "round": 1,
  "reviews": { "security": "pending", "ux": "pending", "ui": "pending", "code": "pending" },
  "history": [ { "round": 1, "reviews": { "security": "CHANGES", "ux": "PASS", "ui": "PASS", "code": "PASS" } } ],
  "decision": null,
  "files": ["spec.md", "build.md", "round-1/review-security.md"],
  "updated": "2026-01-01T12:00:00Z"
}
```

`files` lists every markdown file in the job folder (relative paths) — refresh it
each time a file appears. `history` holds completed rounds; `reviews` is the current round.
Review values: `pending | PASS | CHANGES`. Set `updated` to the current UTC time
(`date -u +%Y-%m-%dT%H:%M:%SZ`).

## New job

1. **Id.** Next 3-digit number after the highest existing id in `factory/jobs/`
   (start at `001`), plus a short kebab slug of the feature: `004-csv-export`.
2. Create `factory/jobs/<id>/` and write `factory/jobs/<id>/feature.md` containing
   the raw feature request. Add the job to the board with `stage: "spec"`, `round: 0`.
3. **Spec.** Spawn `spec-writer` and wait for it:
   > Job folder: factory/jobs/<id>/. Read feature.md and write spec.md.
   When it returns, confirm `spec.md` exists.
4. **Build.** Make sure the working tree is clean (changes under `factory/` are fine —
   the builder never touches that folder) and you are on `main`, then
   set `stage: "build"`, `round: 1`. Spawn `builder` **with name `builder-<id>`**
   (if the Agent tool has no name field, remember the agent ID it returns — that is
   what you SendMessage later):
   > Job <id>. Job folder: factory/jobs/<id>/. Branch: factory/<id>.
   > Read spec.md, create the branch from main, implement, test against the
   > acceptance criteria, commit, and write build.md. Leave the repo on the branch.
5. Go to **Review round**.

## Review round (round n)

1. Set `stage: "review"`, `round: n`, all four reviews `pending`. Create
   `factory/jobs/<id>/round-<n>/`.
2. Spawn **all four reviewers in a single message** (parallel). Each prompt:
   > Job <id>. Job folder: factory/jobs/<id>/. Branch: factory/<id>. Round <n>.
   > Read spec.md and build.md, review `git diff main...factory/<id>`, and write
   > factory/jobs/<id>/round-<n>/review-<kind>.md.
3. As each one returns, read the first line of its file and update that chip on
   the board (`PASS` / `CHANGES`).
4. **WAIT FOR ALL.** The round is done only when all four files exist in
   `round-<n>/`. If a reviewer finished without writing its file, re-spawn that
   reviewer. **Never resume the builder mid-round.**
5. Push the round into `history`.
   - All four `PASS` → go to **Approve**.
   - Any `CHANGES` and `n < MAX_ROUNDS` → set `stage: "build"`, `round: n+1`, and
     **resume the same builder** with `SendMessage` to `builder-<id>`:
     > Round <n> reviews are in factory/jobs/<id>/round-<n>/. Address every
     > CHANGES item, re-test, commit on factory/<id>, and append a
     > "## Round <n+1>" section to build.md.
     (If the builder can no longer be resumed, spawn a fresh `builder` named
     `builder-<id>` with the same instructions plus "read build.md first".)
     Then run **Review round** n+1.
   - Any `CHANGES` and `n == MAX_ROUNDS` → go to **Approve** anyway; the approver
     will see the outstanding CHANGES and should ESCALATE.

## Approve

1. Set `stage: "approve"`. Spawn `approver`:
   > Job <id>. Job folder: factory/jobs/<id>/. Branch: factory/<id>.
   > Read everything in the job folder and the diff, and write decision.md.
2. Read the first line of `decision.md`, record it in `decision`.
   - `APPROVE` → **Merge**.
   - `ESCALATE` → set `stage: "needs-human"`. Tell the user why (one or two lines
     from decision.md) and that they can run `/factory approve <id>` or
     `/factory rework <id> <note>`.

## Merge

1. `git checkout main && git merge --no-ff factory/<id> -m "factory: merge <id>"`.
2. If the merge conflicts: `git merge --abort`, set `stage: "needs-human"` with
   `decision: "ESCALATE"`, and tell the user.
3. On success set `stage: "merged"`. If the job came from the backlog, change its
   line to `- [x]`. Commit the factory/ bookkeeping on main
   (`git add factory && git commit -m "factory: <id> merged"`).

## Human approve (`/factory approve <job-id>`)

Only for a job in `needs-human`. Append `\n\nHUMAN OVERRIDE: approved by user on <date>`
to `decision.md`, set `decision: "APPROVE (human)"`, then **Merge**.

## Rework (`/factory rework <job-id> <note>`)

1. Write the note to `factory/jobs/<id>/rework-<k>.md` (k = 1, 2, …).
2. `git checkout factory/<id>`. Set `stage: "build"`, `round: <last round + 1>`.
3. Resume `builder-<id>` via SendMessage (or spawn a fresh `builder` named
   `builder-<id>` if it can't be resumed) pointing it at the rework file and
   build.md. Then run **Review round** for the new round, followed by **Approve**.
   The MAX_ROUNDS cap counts from the rework (one extra review round allowed after it).

## Rules

- Agents write only their own file. You write only `board.json`, `feature.md`,
  `rework-*.md`, backlog checkmarks, and git merges.
- Keep the user posted with one short line per transition
  (e.g. `003 · round 1 · security CHANGES, ux PASS, ui PASS, code PASS → builder`).
- Dashboard: `cd factory && python3 -m http.server 8765` then open
  http://localhost:8765/dashboard.html.
