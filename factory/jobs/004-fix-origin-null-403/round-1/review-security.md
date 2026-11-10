VERDICT: PASS

## Summary
The only runtime change is `Referrer-Policy: no-referrer` -> `same-origin` in `src/app/web.py:50`. That keeps the real `Origin` on the page's own form POSTs and still sends no `Referer` to other origins. `_check_origin` (`src/app/web.py:220-226`) is unchanged and still refuses `Origin: null`, foreign origins, wrong ports and repeated Origin headers. No new attack surface.

## Notes   (optional, non-blocking)
- `same-origin` sends the full URL as `Referer` only on same-origin requests. Cross-origin requests get no Referer, so nothing leaks to third parties, and the page has no external subresources anyway (CSP `default-src 'none'`). The rendered HTML adds no per-element `referrerpolicy` or `<meta name="referrer">` override, and `test_page_has_no_referrer_override` checks this.
- `requirements-browser.txt` has `playwright` unpinned, and `make test-browser` runs `playwright install chromium`, which downloads browser binaries. Both are opt-in and test-only, and neither is part of `make test` or the runtime. Pinning a version would make it reproducible and limit supply-chain drift, but nothing blocks.
- `tests/test_browser.py` binds the server through `make_server(port=0, ...)`, which uses the existing loopback-only bind. Nothing listens on external interfaces.
- POSTs with no `Origin` header are still accepted. This was already the case before this job and the spec keeps it on purpose (old or non-browser clients). Current browsers send `Origin` on form POSTs, and the Host check still blocks DNS rebinding. Mentioned only for completeness.
