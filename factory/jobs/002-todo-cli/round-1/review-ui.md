VERDICT: PASS

## Summary
CLI output matches the spec exactly (Added/Done/list formats, `No todos.`, `error:` to stderr, argparse usage for exit 2). Naming is consistent and README documents usage and format clearly.

## Notes
- Output is built before printing so errors never leak partial stdout; good.
- Minor: a multi-line todo text would break the one-line-per-item list format; not in spec, non-blocking.
