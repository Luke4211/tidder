# Sprint 1 — MVP Core CLI

**Goal:** A working CLI that takes a Reddit data export + bucket list, scores
every comment with a local Ollama model, and lets the user overwrite or
delete the flagged comments via the Reddit API.

By the end of this sprint, an end-to-end run should be possible without the
web renderer — the user audits flagged comments by hand-editing the CSV (or
just trusting the LLM's flags) before running `remove`.

See [overview.md](overview.md) for the full product description.

---

## In Scope

### `process` command

- Accept `.zip` archive directly; locate and parse `comments.csv` (and
  `comment_headers.csv` if present) internally.
- Flags: `--archive`, `--buckets`, `--llm-model`, `--llm-host`
  (default `http://localhost:11434`), `--confidence-threshold`
  (default `0.75`), `--output-dir`, `--retry-threshold`,
  `--concurrency` (default `4`).
- One LLM prompt per comment, fresh context window per prompt.
- Concurrency via a worker pool of size `--concurrency`. Order-
  independent (each comment is its own prompt); the final sort happens
  after all results are collected. Default of `4` is conservative for
  local Ollama; users with frontier providers will bump this up.
- Strict-JSON output contract; parse + range-check the scores.
- Retry up to `--retry-threshold` times on parse / range failures.
  Comments that still fail go to `errored_comments.csv`.
- Sort the output by `MAX(confidence_mapping) DESC`.
- Bundle results as a single `.zip` in `--output-dir`, containing:
  - `flagged_comments.csv`
  - `errored_comments.csv` (omitted if empty)
  - `buckets.json`
  - `run_metadata.json`
- Print the archive path + a short next-steps message pointing at `remove`.

### `remove` command

- Input: the `.zip` produced by `process` (extract internally).
- Flags: `--input`, `--mode overwrite|delete` (default `overwrite`),
  `--dry-run`, `--overwrite-style random|llm|fixed`
  (default `random`), `--overwrite-text` (only valid with
  `--overwrite-style fixed`), and the LLM flags from `process`
  (`--llm-model`, `--llm-host`, etc.) when `--overwrite-style llm`
  is used.
- Only acts on rows with `flagged_for_del = true`.
- Reddit-API-aware rate limiting + backoff.
- `--dry-run` reports what *would* be touched without making any API
  calls. When combined with `--overwrite-style llm`, also previews a
  sample of generated replacement bodies so the user can sanity-check
  tone before burning inference on the full run.
- `overwrite` replaces the comment body with replacement text per
  `--overwrite-style`; safe to re-run.
- `delete` actually deletes.

#### Overwrite styles

- `random` (default): unique-per-comment random text generated locally
  (random words from a wordlist, varied length). Cheap, but a
  determined data miner could plausibly detect gibberish and skip the
  overwritten version in favor of a cached "good" copy.
- `llm`: generate a unique, plausible-sounding, deliberately generic
  and politically neutral replacement comment via the configured LLM.
  Costs an extra inference call per flagged comment, but is much
  harder to filter out as "obviously overwritten." Worth the cost for
  users serious about evading downstream scraping.
- `fixed`: a single user-provided string applied to every comment.
  Cheapest, least robust — included mostly for parity with existing
  tools.

### Supporting work

- Archive parsing utility (zip → comments iterator).
- Ollama client wrapper (single-comment prompt, JSON-mode response,
  retry loop).
- CSV writers for flagged + errored outputs.
- Reddit API auth + client. Interactive OAuth dance on first `remove`
  invocation; persist the **refresh token** to
  `~/.config/tidder/credentials.json` with `0600` perms. Subsequent
  runs silently exchange the refresh token for a fresh access token
  (Reddit access tokens expire after ~1 hour); only re-prompt the
  user if the refresh token itself is revoked or expired.
- Overwrite-text generators: a local random-words generator for
  `--overwrite-style random`, and an LLM-backed generator for
  `--overwrite-style llm` (reuses the same provider client as
  `process`, with a separate, carefully-tuned prompt: generic,
  politically neutral, plausible tone, no references to the original
  content). Generated bodies should be unique per comment.
- Basic logging so a long `process` run is observable.

---

## Out of Scope (deferred to later sprints)

- Web renderer / `review` command → **Sprint 2**.
- Non-Ollama LLM providers → **Sprint 2**.
- Subreddit whitelist flag → **Sprint 2**.
- Resumable `process` (checkpointing) → **Sprint 2** (stretch).
- Public webapp → **Sprint 3**.

---

## Definition of Done

- A user can run `tidder process` against a real Reddit export and get a
  valid output `.zip`.
- A user can run `tidder remove --dry-run` and see an accurate plan.
- A user can run `tidder remove` (overwrite + delete modes) end-to-end
  against their account without tripping Reddit's rate limits.
- Errored comments are captured, not silently dropped.
- Smoke-tested with at least one real export and one nontrivial bucket
  list.

---

## Resolved Decisions

- **Reddit auth.** Interactive OAuth on first `remove`; persist refresh
  token to `~/.config/tidder/credentials.json` (`0600`); silently
  refresh access tokens on every subsequent run; only re-prompt if the
  refresh token is invalidated.
- **Overwrite text.** Three styles via `--overwrite-style`: `random`
  (default, local random-words, unique per comment), `llm` (LLM-
  generated, generic/neutral/plausible — best evasion vs. downstream
  scrapers, at the cost of one extra inference per flagged comment),
  and `fixed` (user-provided constant string).
- **Concurrency.** Worker pool from the jump, `--concurrency` flag,
  default `4`. Comments are independent so this is a clean win for
  frontier-provider runs, and conservative defaults keep local Ollama
  from getting hammered.

## Open Questions for This Sprint

*(None at the moment — promote new ones here as they come up during
implementation.)*
