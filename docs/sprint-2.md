# Sprint 2 — MVP Polish: Review UI, External LLMs, Filtering

**Goal:** Close out the MVP. Sprint 1 gave us a usable but bare-bones CLI;
this sprint adds the local web renderer for `review`, opens the door to
frontier LLMs via API keys, and lets users narrow `process` to a
whitelist of subreddits.

See [overview.md](overview.md) and [sprint-1.md](sprint-1.md) for prior
context.

---

## In Scope

### `tidder review` — local web renderer

- Loads the `.zip` produced by `process` (or a raw `flagged_comments.csv`).
- Serves a Reddit-themed page on `localhost` (port configurable).
- Infinite-scroll list, sorted by `MAX(confidence_mapping) DESC` (same
  order as the CSV).
- Per-comment flag/unflag toggle that mutates the source CSV in place,
  so subsequent `remove` runs see the user's edits.
- Surface the per-bucket scores and the bucket descriptions
  (`buckets.json`) inline so the user can see *why* a comment was
  flagged.
- Designed so the rendering logic can be reused by the eventual webapp
  in Sprint 3 — keep the UI layer thin and the data layer reusable.

### External LLM provider support

- Generalize the LLM client behind a small provider interface.
- New `process` flags: `--llm-provider` (e.g. `ollama`, `anthropic`,
  `openai`), `--api-key` (or env-var fallback).
- Keep Ollama as the default; existing CLI invocations from Sprint 1
  should continue to work unchanged.
- Per-provider config (base URL, model name conventions, JSON-mode
  flags) lives in the provider implementation, not in `process`.

### Subreddit whitelist

- New optional `process` flag: `--subreddits` (one or more subreddit
  names).
- When provided, only comments whose subreddit matches the list are
  sent to the LLM. Skipped comments don't appear in any output file —
  they're filtered before classification.
- Case-insensitive match; accept with or without the `r/` prefix.

### Stretch: resumable `process`

- Checkpoint progress (per-comment) so an interrupted run can resume
  without re-classifying.
- Checkpoint lives inside the run's output directory; cleared on
  successful completion (or rolled into the final `.zip`).
- Lowest priority in this sprint — only pick up if everything else is
  done.

---

## Out of Scope

- Multi-comment batching experiments → revisit alongside frontier
  providers, but not a sprint commitment.
- Public webapp / hosted version → **Sprint 3**.
- Account / auth system → **Sprint 3**.

---

## Definition of Done

- `tidder review` runs locally, renders the flagged comments, and
  flag/unflag edits persist back to the CSV.
- A `process` run using a frontier provider (with an API key) produces
  the same output schema as an Ollama run.
- `process --subreddits foo bar` only emits comments from those subs.
- All Sprint 1 commands still work with no regressions.

---

## Open Questions for This Sprint

- Web renderer stack: vanilla server-rendered HTML + a sprinkle of JS,
  or a small SPA (Vite + React) that we can carry forward into the
  webapp? Trade-off: SPA is more reusable in Sprint 3 but heavier for
  the MVP.
- API-key storage for external providers: env var only, or also a local
  config file? (Lean env-var-only for the MVP.)
- Should `--subreddits` also accept an inverse form
  (`--exclude-subreddits`)? Not part of the original ask; only pick up
  if it falls out cleanly.
