VERDICT: PASS

## Summary
The one-line header change fixes the user-visible bug (browser Add/Done forms no longer get 403 from Origin: null). `_check_origin` is unchanged, so foreign and null origins are still refused. Tests, README and the optional browser test meet every AC from a user's view.

## Notes
- Makefile `help`: the new `make test-browser - ...` line breaks the column alignment of the other entries. Cosmetic only.
- README documents `make test-browser` and the reason for `same-origin`, so the behaviour is discoverable.
- The browser test skips cleanly when Playwright or a browser is missing. Once Playwright is in `.venv`, it also runs under `make test` (noted in build.md). That is acceptable.
- No UI, markup or error-message changes, so there are no accessibility concerns.
