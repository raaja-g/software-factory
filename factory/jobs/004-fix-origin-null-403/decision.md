APPROVE

## Reasoning
- Round 1 is the latest round, and all four reviews (code, security, ui, ux) say `VERDICT: PASS`. The only notes are non-blocking: the `make help` line is out of alignment and `playwright` is not pinned.
- build.md marks AC1–AC7 as met and gives evidence for each: `make test` gives 137 passed (136 passed and 1 skipped before Playwright was installed), and `make test-browser` gives 1 passed. For AC4 the builder also checked by hand that setting the header back to `no-referrer` makes both the model test and the browser test fail. The code reviewer ran `make test` separately and got 137 passed.
- The diff stays inside the spec's scope. The only runtime change is one header value in `src/app/web.py` (`no-referrer` changed to `same-origin`, with a comment and a docstring note). `_check_origin` is unchanged and still refuses `Origin: null`. The rest is tests, an optional opt-in `requirements-browser.txt`, a `test-browser` Make target, and README/CLAUDE.md docs. No files are deleted, there are no migrations, and auth is not loosened.
- On security, `same-origin` still sends no Referer to other origins, and the CSRF and Host checks are unchanged. Playwright and its browser download are opt-in, test-only, and not part of `make test` or the runtime.
- `git merge-tree --write-tree main factory/004-fix-origin-null-403` finished cleanly (exit 0, tree 65f6b988) with no conflicts.
