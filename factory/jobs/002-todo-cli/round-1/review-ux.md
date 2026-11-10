VERDICT: PASS

## Summary
The CLI matches the spec from a user's view. I ran it by hand with a temp HOME. Output formats, exit codes, usage errors and the help text are all clear, and error messages name the file or item.

## Notes
- `done 0` or a negative N says "no todo #0 (have 2)". That is accurate, though a hint such as "valid: 1..2" would be friendlier. It is optional.
- `add "   "` is rejected with a clear message. Joining words with single spaces is documented in the README.
- The README covers usage, the storage location, the output format and the exit codes.
