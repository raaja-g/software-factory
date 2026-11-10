VERDICT: PASS

## Summary
The page does what the spec's user needs: it lists todos with CLI numbering, adds todos, marks them done, and re-renders the full page with a role="alert" error on bad input. The CLI messages and README match the spec. I read the code and spec only and did not run the server.

## Notes
- The form is accessible: a visible label for the input, aria-label on each Done button naming its item, lang, viewport, and no JavaScript.
- Error pages (403, 404, 413, 415, 500) include a "Back to the todo list" link and escaped messages.
- Error text is #a40000 and bold, and the "(done)" marker is visible text, so state is not conveyed by colour alone.
- Non-blocking: the 303 body "Done. Returning to the list." is also shown after an add, so the wording is slightly off. Browsers follow the redirect, so users never see it.
