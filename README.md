# software-factory

An **AI software factory** that runs inside [Claude Code](https://claude.com/claude-code).
You describe a feature in one sentence; a team of specialised agents writes the
spec, builds it on its own branch, reviews it from four angles in parallel,
loops on the feedback, and either merges it to `main` or hands it back to you.

```
feature ─► spec-writer ─► builder ⇄ [ security | ux | ui | code ]  (max 2 rounds) ─► approver
                                                                               ├─ APPROVE  ─► merge to main
                                                                               └─ ESCALATE ─► needs-human (you decide)
```

The repo also contains the small Python app the factory has built so far:
a project skeleton, a `todo` CLI, and a local todo web page. See
[The app](#the-app) at the end.

---

## Contents

- [Quick start](#quick-start)
- [How the factory works](#how-the-factory-works)
  - [The agents](#the-agents)
  - [A job, step by step](#a-job-step-by-step)
  - [Review rounds and verdicts](#review-rounds-and-verdicts)
  - [Approve or escalate](#approve-or-escalate)
- [Ways to use the factory](#ways-to-use-the-factory)
  - [1. Build a one-off feature](#1-build-a-one-off-feature-factory-feature)
  - [2. Work through a backlog](#2-work-through-a-backlog-factory-next)
  - [3. Fix a bug](#3-fix-a-bug)
  - [4. Approve an escalated job](#4-approve-an-escalated-job-factory-approve-job-id)
  - [5. Send a job back for rework](#5-send-a-job-back-for-rework-factory-rework-job-id-note)
  - [6. Watch it on the dashboard](#6-watch-it-on-the-dashboard)
  - [Writing good feature requests](#writing-good-feature-requests)
- [Where everything lives](#where-everything-lives)
  - [The `factory/` folder](#the-factory-folder)
  - [A job folder](#a-job-folder)
  - [`board.json`](#boardjson)
  - [Git branches](#git-branches)
- [Customising the factory](#customising-the-factory)
- [Troubleshooting](#troubleshooting)
- [Factory history](#factory-history)
- [The app](#the-app)

---

## Quick start

Requirements: [Claude Code](https://claude.com/claude-code), `git`, and
whatever the project's stack needs (currently Python 3.10+ and `make`).

```sh
git clone https://github.com/raaja-g/software-factory.git
cd software-factory
claude                       # start Claude Code in the repo
```

Then, inside Claude Code:

```
/factory next                                  # build the next backlog item
/factory Add a --json flag to "todo list"      # or build any feature you describe
```

Optionally watch progress live in a second terminal:

```sh
cd factory && python3 -m http.server 8765
# open http://localhost:8765/dashboard.html
```

---

## How the factory works

The `/factory` skill (`.claude/skills/factory/SKILL.md`) turns the Claude Code
session you're typing in into the **orchestrator**. It runs the loop, spawns
every agent, moves the job between stages, and is the only thing that writes
`factory/board.json` and merges to `main`.

Agents never see your conversation. Each one gets a short prompt naming the job
folder and reads everything else **from files**. Each agent writes **only its own
file**. Because of this, every step leaves an audit trail on disk, and an agent
can't be swayed by anything except the spec, the code and earlier reviews.

### The agents

All agents are defined in `.claude/agents/`.

| Step    | Agent               | Model  | Reads                                     | Writes                                   |
|---------|---------------------|--------|-------------------------------------------|------------------------------------------|
| spec    | `spec-writer`       | opus   | `feature.md`, `CLAUDE.md`, the repo       | `spec.md`                                |
| build   | `builder`           | opus   | `spec.md`, `CLAUDE.md`, later reviews      | code + commits on `factory/<id>`, `build.md` |
| review  | `reviewer-security` | opus   | `spec.md`, `build.md`, the branch diff    | `round-<n>/review-security.md`           |
| review  | `reviewer-ux`       | sonnet | same                                      | `round-<n>/review-ux.md`                 |
| review  | `reviewer-ui`       | sonnet | same                                      | `round-<n>/review-ui.md`                 |
| review  | `reviewer-code`     | sonnet | same (and runs the tests itself)          | `round-<n>/review-code.md`               |
| approve | `approver`          | opus   | everything in the job folder + the diff   | `decision.md`                            |

What each reviewer looks for:

- **security**: injection (SQL, shell, path traversal), XSS, unsafe
  deserialisation, auth gaps, secrets in code, unsafe defaults, input validation
  at trust boundaries, dependency risks, DoS vectors.
- **ux**: whether the feature does what the user needs, every acceptance
  criterion from the user's side, error messages, empty and edge states, help
  text, accessibility basics, sensible defaults.
- **ui**: layout, spacing, typography, colour, consistency, responsiveness; for
  CLIs and APIs, output formatting and naming.
- **code**: bugs, logic errors, edge cases, races, whether the tests really
  cover the acceptance criteria (it runs them), readability, duplication, repo
  conventions.

Reviewers are **read-only**: they never edit, commit or switch branches, because
all four share the same checkout at once. If a change has nothing in a
reviewer's area (for example, no UI), that reviewer passes it and says so.

### A job, step by step

1. **Job id.** The orchestrator takes the next 3-digit number plus a short slug,
   such as `004-fix-origin-null-403`, creates `factory/jobs/<id>/`, saves your
   request word for word as `feature.md`, and adds the job to the board in
   stage `spec`.
2. **Spec.** `spec-writer` turns the request into `spec.md`, which covers the
   goal, stack and conventions, in and out of scope, design, numbered
   **acceptance criteria** (AC1, AC2, …), and a test plan. If the repo has no
   code yet, it picks a minimal stack and says so.
3. **Build.** On a clean `main`, the `builder` creates branch `factory/<id>`,
   implements the spec, writes tests for every acceptance criterion, runs them
   until they pass, commits, and writes `build.md` recording what changed, how
   to test it, each AC with its evidence, the test output and the commit list.
   If it changes the stack or the test command, it updates the Stack section of
   `CLAUDE.md` on the branch.
4. **Review.** All four reviewers run **in parallel** on
   `git diff main...factory/<id>`, and each writes
   `round-<n>/review-<kind>.md`.
5. **Loop.** If any reviewer says `CHANGES`, the **same builder** is resumed with
   the reviews. It fixes every required item, re-tests, commits, appends a
   `## Round <n+1>` section to `build.md`, and a fresh round of all four reviews
   runs.
6. **Approve.** The `approver` reads the whole job folder and the diff, checks
   for merge conflicts, and writes `decision.md`.
7. **Merge.** On `APPROVE` the orchestrator merges `factory/<id>` into `main`
   with `--no-ff`, ticks the backlog line if the job came from the backlog, and
   commits the `factory/` bookkeeping. On `ESCALATE` the job stops at
   `needs-human` and you decide.

Throughout, the orchestrator posts one short status line per transition:

```
003 · spec done → builder (round 1)
003 · round 1 · security CHANGES, ux PASS, ui PASS, code PASS → builder
003 · round 2 · security PASS, ux PASS, ui PASS, code PASS → approver
```

### Review rounds and verdicts

The first line of every review file is exactly one of:

```
VERDICT: PASS
VERDICT: CHANGES
```

followed by `## Summary`, `## Required changes` (numbered, with `file:line`,
only when CHANGES) and optional non-blocking `## Notes`. Reviewers are told to
use `CHANGES` only for real problems in their own area, never for style nits
or out-of-scope wishes.

Rules for a round:

- A round finishes only when **all four** review files exist. A reviewer that
  stops without writing its file is spawned again.
- The builder is **never** resumed mid-round.
- `MAX_ROUNDS = 2`. If round 2 still has a `CHANGES`, the job goes to the
  approver anyway, and the approver will escalate it to you.

### Approve or escalate

The approver writes `APPROVE` only if **all** of these hold:

- the latest round has all four reviews at `VERDICT: PASS`;
- `build.md` shows every acceptance criterion met, with evidence;
- the diff matches the spec's scope, with nothing surprising or unrelated;
- `git merge-tree --write-tree main factory/<id>` reports no conflicts.

Otherwise it writes `ESCALATE`. It also escalates anything irreversible or
high-risk (data migrations, auth changes, deleting files, new external
services) **even if every review passed**. `decision.md` starts with the
verdict, gives 3–6 bullets of reasoning and, when escalating, a "For the human"
section saying what to look at.

---

## Ways to use the factory

Every command runs inside a Claude Code session started in this repo.

| Command                              | What it does                                                         |
|--------------------------------------|----------------------------------------------------------------------|
| `/factory <feature description>`     | Run a new job for that description                                   |
| `/factory next`                      | Take the first unchecked item from `factory/backlog.md` and run it   |
| `/factory approve <job-id>`          | Approve and merge a job stuck at `needs-human`                       |
| `/factory rework <job-id> <note>`    | Send a job back to the builder with your note, then review it again  |

### 1. Build a one-off feature: `/factory <feature>`

Any argument that isn't `next`, `approve` or `rework` is treated as a feature
description and runs as a new job:

```
/factory Add a "todo clear-done" command that removes completed items and renumbers the rest
```

The job is **not** added to the backlog. It shows on the board and in
`factory/jobs/` like any other.

### 2. Work through a backlog: `/factory next`

Queue work in `factory/backlog.md`, one item per line:

```markdown
- [x] Bootstrap a minimal Python 3 project …        ← merged
- [~] Add a `todo` CLI …                            ← in progress
- [ ] Add a tiny local web page …                   ← next up
```

`/factory next` takes the **first** `- [ ]` line, marks it `- [~]`, runs it as a
new job, and changes it to `- [x]` once merged. With nothing unchecked, it says
the backlog is empty and stops.

Tips:

- Order matters: put foundation work (stack, layout, test command) first, since
  later specs build on what earlier jobs left in `CLAUDE.md` and the code.
- Run `/factory next` again for each item. Every run is one full job.
- Edit the backlog by hand whenever you like; only the checkmarks are managed
  for you.

### 3. Fix a bug

A bug fix is just a feature request. The more of the cause you include, the
better the spec. A real example (job `004`):

```
/factory Fix: browser form POSTs to the todo web page get 403 "cross-origin request refused".
Cause: Referrer-Policy: no-referrer makes browsers send Origin: null on same-origin form POSTs,
which _check_origin rejects. Change Referrer-Policy to same-origin, keep rejecting Origin: null,
and add a test that fails if the referrer policy would make browsers send Origin: null
(ideally a real-browser test of add and done).
```

Asking for a **regression test that fails without the fix** is the most useful
part. The builder is expected to show it failing first (in `004` it set the
header back to `no-referrer` and confirmed the new tests failed).

### 4. Approve an escalated job: `/factory approve <job-id>`

When a job stops at **needs-human**, the orchestrator tells you why (quoting
`decision.md`). Read `factory/jobs/<id>/decision.md` and the diff
(`git diff main...factory/<id>`). If you're happy:

```
/factory approve 005-csv-export
```

This appends `HUMAN OVERRIDE: approved by user on <date>` to `decision.md`,
records the decision as `APPROVE (human)`, and merges. It only works for jobs in
`needs-human`.

### 5. Send a job back for rework: `/factory rework <job-id> <note>`

When an escalated job needs changes, or you simply want something different:

```
/factory rework 005-csv-export Use semicolons as the delimiter and add a header row
```

This saves your note as `factory/jobs/<id>/rework-<k>.md`, checks out the
branch, resumes (or re-creates) that job's builder with the note and
`build.md`, then runs a fresh review round and the approver. After a rework the
round cap allows one more review round.

### 6. Watch it on the dashboard

```sh
cd factory && python3 -m http.server 8765
# open http://localhost:8765/dashboard.html
```

`dashboard.html` ("Factory floor") polls `board.json` every 2 seconds and shows:

- one column per stage: **Spec → Build → Review → Approve → Needs human → Merged**;
- a card per job with its round and four review chips (`sec`, `ux`, `ui`,
  `code`) that turn PASS or CHANGES as each verdict lands;
- a count of jobs that need you;
- a drawer, opened from a card, that renders every markdown file in the job
  folder (spec, build, reviews, decision).

It's read-only and has no dependencies. Leave it open in a browser tab while
the factory runs.

### Writing good feature requests

The request becomes `feature.md`, the only input the spec-writer gets, so:

- **Say what, not how.** Describe the behaviour a user sees and leave the
  design to the spec, unless you have a firm opinion.
- **Mention the interface.** For example, `python -m app.todo add|list|done <n>`,
  "a JSON endpoint", or "a button on each row".
- **State constraints.** Standard library only, must work offline, localhost
  only, file location, and so on.
- **Keep it to one job.** Something buildable in one sitting. Split big ideas
  into several backlog lines.
- **For bugs, give the symptom, the cause if you know it, and the test you want.**
- **Carry over earlier findings.** Reviews and decisions often list
  non-blocking notes for later jobs (for example "the web page must HTML-escape
  output and bind to 127.0.0.1"). The spec-writer only reads `feature.md`, the
  repo and `CLAUDE.md`, not earlier jobs, so add any such requirements to the
  request yourself.

---

## Where everything lives

```
.claude/
  skills/factory/SKILL.md     the orchestrator loop (what /factory runs)
  agents/                     one file per agent: role, tools, model, output format
    spec-writer.md
    builder.md
    reviewer-security.md
    reviewer-ux.md
    reviewer-ui.md
    reviewer-code.md
    approver.md
factory/                      factory bookkeeping, owned by the orchestrator
  backlog.md                  queued work for /factory next
  board.json                  live state of every job (read by the dashboard)
  dashboard.html              the "Factory floor" dashboard
  jobs/<id>/                  one folder per job (see below)
CLAUDE.md                     project instructions; its Stack section tells agents
                              how to run and test the code
```

### The `factory/` folder

`factory/` is bookkeeping. Builders **never** edit it, and their commits never
include it. Only the orchestrator writes `board.json`, `feature.md`,
`rework-*.md`, the backlog checkmarks, and the merge commits. Each agent
writes only its own markdown file in the job folder. After every merge the
orchestrator commits `factory/` on `main` (`factory: <id> merged`), so the full
record of every job is versioned along with the code.

### A job folder

```
factory/jobs/003-todo-web/
  feature.md                  your request, word for word
  spec.md                     goal, scope, design, acceptance criteria, test plan
  build.md                    what changed, AC evidence, test output, commits; one "## Round n" section per round
  round-1/
    review-security.md        VERDICT: CHANGES   ← round 1 asked for a fix
    review-ux.md              VERDICT: PASS
    review-ui.md              VERDICT: PASS
    review-code.md            VERDICT: PASS
  round-2/
    review-security.md        VERDICT: PASS      ← fixed in round 2
    …
  rework-1.md                 (only if you ran /factory rework)
  decision.md                 APPROVE | ESCALATE (+ HUMAN OVERRIDE line if you approved it)
```

### `board.json`

One entry per job, rewritten at every transition:

```json
{
  "id": "003-todo-web",
  "title": "Add a tiny local todo web page",
  "branch": "factory/003-todo-web",
  "stage": "merged",
  "round": 2,
  "reviews": { "security": "PASS", "ux": "PASS", "ui": "PASS", "code": "PASS" },
  "history": [
    { "round": 1, "reviews": { "security": "CHANGES", "ux": "PASS", "ui": "PASS", "code": "PASS" } },
    { "round": 2, "reviews": { "security": "PASS", "ux": "PASS", "ui": "PASS", "code": "PASS" } }
  ],
  "decision": "APPROVE",
  "files": ["build.md", "decision.md", "feature.md", "round-1/review-code.md", "…"],
  "updated": "2026-11-11T08:20:00Z"
}
```

- `stage` is one of `spec`, `build`, `review`, `approve`, `needs-human`, `merged`.
- `reviews` is the current round; review values are `pending`, `PASS` or `CHANGES`.
- `history` holds the finished rounds.
- `decision` is `null`, `APPROVE`, `ESCALATE` or `APPROVE (human)`.
- `files` lists every markdown file in the job folder, which the dashboard drawer uses.

### Git branches

- Feature work happens **only** on `factory/<job-id>` branches, each created
  from `main`.
- `main` only receives `--no-ff` merges (`factory: merge <id>`) plus the
  bookkeeping commit after each merge (`factory: <id> merged`).
- A merge conflict aborts the merge and sends the job to `needs-human` with
  `ESCALATE`.
- Job branches are kept locally after merging, so you can inspect or delete
  them.

---

## Customising the factory

All of the factory's behaviour is plain markdown, so edit it like any other
file.

| To change…                         | Edit                                                                 |
|------------------------------------|----------------------------------------------------------------------|
| The loop, round cap, stages        | `.claude/skills/factory/SKILL.md` (for example `MAX_ROUNDS = 2`)     |
| What an agent does or outputs      | `.claude/agents/<agent>.md` (body)                                   |
| An agent's model or tools          | the `model:` / `tools:` frontmatter in `.claude/agents/<agent>.md`  |
| The approve/escalate bar           | `.claude/agents/approver.md`                                         |
| Stack, run and test commands       | the Stack section of `CLAUDE.md` (agents read it every job)          |
| Queued work                        | `factory/backlog.md`                                                 |

**Adding a reviewer** (for example `reviewer-perf`):

1. Copy `.claude/agents/reviewer-code.md` to `reviewer-perf.md`, then change
   `name`, `description`, the focus list and the output filename
   (`review-perf.md`).
2. In `SKILL.md`, add it to the agent table, the parallel spawn in **Review
   round**, and the `reviews` object in the board shape.
3. In `factory/dashboard.html`, add `{ key: 'perf', short: 'perf' }` to
   `REVIEWERS` so it gets a chip.

**Using the factory in another repo:** copy `.claude/` and `factory/` (with an
empty `jobs/` and your own `backlog.md`), add a `CLAUDE.md` with a Stack
section, and run `/factory next`. If the repo has no commits yet, the
orchestrator makes the initial commit for you.

---

## Troubleshooting

| Symptom                                                    | What's going on / what to do |
|------------------------------------------------------------|------------------------------|
| A job sits in `needs-human`                                | The approver escalated it, or round 2 still had CHANGES. Read `decision.md`, then `/factory approve <id>` or `/factory rework <id> <note>`. |
| A reviewer finished but its file is missing                | The orchestrator spawns it again; the round never closes without all four files. |
| The builder can't be resumed for a later round             | The orchestrator spawns a fresh `builder` and tells it to read `build.md` first. |
| Merge conflict at the end                                  | The merge is aborted and the job goes to `needs-human`. Resolve on the branch or rework it. |
| `make test` fails with `No module named pip`               | `.venv/` was left half-created (for example two reviewers set it up at the same moment). Run `make clean && make test`. |
| You changed code but behaviour didn't change               | A long-running process (such as the web server) is still running old code. Restart it. |
| Dashboard shows nothing                                    | Serve it from inside `factory/` (`cd factory && python3 -m http.server 8765`) so `board.json` is next to it. |

---

## Factory history

What the factory has built in this repo so far (full records in `factory/jobs/`):

| Job                         | Request                                                    | Rounds | Outcome |
|-----------------------------|------------------------------------------------------------|--------|---------|
| `001-bootstrap-python`      | Python 3 project skeleton, pytest, `make test`, README     | 1      | Merged; all four reviews passed first time |
| `002-todo-cli`              | `python -m app.todo add\|list\|done <n>` storing `~/.todo.json` | 1  | Merged; 54 new tests |
| `003-todo-web`              | Local web page to list, add and complete todos             | 2      | Security asked for a socket timeout (a stalled client could block the single-threaded server); fixed in round 2, then merged |
| `004-fix-origin-null-403`   | Browser form POSTs got 403 because of `Referrer-Policy: no-referrer` | 1 | Merged; added a regression test and an optional real-browser test |

---

## The app

A minimal Python 3 project (standard library only at runtime), built entirely
by the factory.

### Requirements

- Python 3.10+ (`python3` on your `PATH`)
- `make`

pytest is a dev-only dependency; `make test` installs it into a project-local
virtualenv for you.

### Layout

```
src/app/                  application package (importable as `app`)
  __init__.py             package metadata (`__version__`)
  __main__.py             entry point for `python -m app`
  todo.py                 todo CLI + reusable storage functions (`python -m app.todo`)
  web.py                  local todo web page (`python -m app.web`)
tests/                    pytest test suite (`test_*.py`)
pyproject.toml            project metadata + pytest config (`pythonpath = ["src"]`)
requirements-dev.txt      dev dependencies (pytest)
requirements-browser.txt  optional browser-test deps (pytest + Playwright)
Makefile                  `help`, `venv`, `test`, `test-browser`, `clean` targets
```

### Running tests

```sh
make test          # default target
```

The first run creates a virtualenv in `.venv/` and installs pytest from
`requirements-dev.txt` into it. Later runs reuse it; it's only reinstalled
when `requirements-dev.txt` changes. The exit code of `make test` is pytest's.

Manual alternative (without `make`):

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest
```

Optional real-browser test. It adds a todo and marks it done in headless
Chromium via Playwright, falling back to an installed Google Chrome:

```sh
make test-browser
```

It installs `requirements-browser.txt` (pytest + Playwright) into `.venv/` and
tries `playwright install chromium`. Under plain `make test` the browser test
is reported as skipped when Playwright isn't installed.

Other targets:

```sh
make help          # list targets
make venv          # just create .venv and install dev deps
make clean         # remove .venv, .pytest_cache and __pycache__ dirs
```

### Running the app

```sh
cd src && python3 -m app
```

Prints `app <version>`, for example `app 0.1.0`.

### Todo CLI

A small todo manager. Run it from `src/`:

```sh
cd src
python3 -m app.todo add buy milk     # Added #1: buy milk
python3 -m app.todo add call bob     # Added #2: call bob
python3 -m app.todo done 2           # Done #2: call bob
python3 -m app.todo list
# 1. [ ] buy milk
# 2. [x] call bob
```

- `add TEXT...`: words are joined with single spaces; empty text is an error.
- `list`: one line per item, `<n>. [ ] <text>` (open) or `<n>. [x] <text>`
  (done); prints `No todos.` when there are none.
- `done N`: marks item `N` done. Completed items stay in the list, so numbers
  never change.

Todos are stored in **`~/.todo.json`** (UTF-8 JSON, file mode `0600`, written
atomically):

```json
{
  "items": [
    {"text": "buy milk", "done": false},
    {"text": "call bob", "done": true}
  ]
}
```

Errors (unknown item number, empty text, a corrupt or malformed storage file)
print `error: <message>` to stderr and exit 1, and a corrupt file is never
overwritten. Usage errors (bad or missing subcommand, non-integer `N`) exit 2.

The storage functions `load_items`, `save_items`, `add_item`, `complete_item`
and `default_path` live in `app.todo`, and each accepts an optional `path`.

### Todo web page

A tiny browser view of the same todo list, with no JavaScript and no
dependencies. Run it from `src/`:

```sh
cd src
python3 -m app.web            # Serving todos at http://127.0.0.1:8000/ (Ctrl+C to stop)
python3 -m app.web --port 9000
python3 -m app.web --port 0   # let the OS pick a free port
```

Then open **http://127.0.0.1:8000/** (or `http://localhost:8000/`). The page
lists all todos with the same numbers as `python3 -m app.todo list`, has a
form to add a todo, and a **Done** button on each open item. Press Ctrl+C to
stop the server.

- It shares **`~/.todo.json`** with the CLI (same storage functions), so the
  CLI and the page always show the same list. Reload the page to see changes
  made from the CLI.
- It binds **only to `127.0.0.1`** (localhost), so other machines can't reach
  it. There is no `--host` option.
- Requests whose `Host` isn't `127.0.0.1:<port>` or `localhost:<port>` are
  rejected, as are POSTs whose `Origin` is foreign or `null`. Form bodies are
  limited to 10 000 bytes, and all text is HTML-escaped.
- Each connection has a 10-second timeout, so a stalled client can't block the
  single-threaded server.
- The page sends `Referrer-Policy: same-origin`, so browsers send the real
  `Origin` on its own form POSTs (`no-referrer` would make them send
  `Origin: null`, which is refused).
- A corrupt `~/.todo.json` shows an error page (HTTP 500) and is never
  overwritten.
- If the port is already in use, it prints `error: <message>` to stderr and
  exits 1. An invalid `--port` exits 2.
- After pulling new code, **restart the server**, since a running server keeps
  serving the old code.
