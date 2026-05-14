# Sprint 1 — MVP Core CLI

**Goal:** A working CLI that takes a Reddit data export + bucket list, scores
every comment with a local Ollama model, and lets the user overwrite or
delete the flagged comments via the Reddit API.

By the end of this sprint, an end-to-end run should be possible without the
web renderer — the user audits flagged comments by hand-editing the CSV (or
just trusting the LLM's flags) before running `remove`.

See [overview.md](overview.md) for the full product description.

---

## Status

The scaffolding is in place: `src/tidder/` package, typer-based CLI, full
flag surface for `process` and `remove`, abstract `LLMProvider` with an
`OllamaProvider` shell, layered config (`pydantic-settings` + TOML + env +
flags), Reddit auth/client shells, output-bundle and CSV-schema modules, and
smoke tests confirming the CLI wires up. Every behavior-bearing function
currently raises `NotImplementedError`.

The rest of this doc enumerates the work to take those stubs to a working
end-to-end MVP. Tasks are grouped roughly by the order they unblock each
other; within a group, items are mostly independent.

---

## Workstream 1 — `process` end-to-end

Goal: `tidder process --archive <zip> --buckets ... --llm-model <m>` produces
a sorted bundle `.zip` against a real Reddit export.

### 1.1 Archive parsing — [src/tidder/archive.py](../src/tidder/archive.py)

- Open the Reddit export `.zip`, locate `comments.csv` (and
  `comment_headers.csv` if present — older exports rely on it for column
  names).
- Yield `Comment` objects (see
  [src/tidder/models.py](../src/tidder/models.py)) with `id`, `url`, `body`,
  `subreddit`, `created`, and `score` populated where available.
- Skip empty / `[deleted]` / `[removed]` bodies — they can't be classified
  meaningfully and would just waste inference.
- Stream the CSV (don't read the whole thing into memory) so multi-year
  exports stay tractable.
- Tests against a tiny synthetic export fixture in `tests/fixtures/`.

### 1.2 Ollama classifier — [src/tidder/llm/ollama.py](../src/tidder/llm/ollama.py)

- Implement `classify()`:
  - Build the system+user prompt: explain the bucket-scoring contract, list
    the buckets with their user-supplied descriptions, embed the comment
    body.
  - Call Ollama's `/api/chat` (or `/api/generate`) with `format: "json"`
    and `stream: false`. Use a fresh request per comment — no context
    carry-over.
  - Parse the response JSON; validate keys are bucket indices `0..n-1` and
    values are floats in `[0.0, 1.0]`. Raise a typed parse/range error on
    any deviation so the retry loop can catch it cleanly.
- Implement `generate_replacement()`: same client, different prompt — generic,
  politically neutral, plausible tone, length roughly proportional to the
  original, never references the original content. Returns a single string.
- Define the prompt strings as module-level constants so they're easy to
  iterate on and version.

### 1.3 Classifier pipeline — [src/tidder/classifier.py](../src/tidder/classifier.py)

- Async worker pool sized by `--concurrency`. `asyncio.Semaphore` plus
  `asyncio.gather` over `iter_comments(...)`, or a queue + N consumer tasks
  — either is fine, pick whichever reads more cleanly.
- Per-comment retry loop: up to `retry_threshold` attempts on parse / range
  failures. Final failure → `Classification(errored=True, error_message=...)`
  with empty `scores`.
- Returns a flat `list[Classification]`. Sorting and threshold-filtering
  happen in the output layer (cleaner separation, easier to test).
- Progress logging so a multi-hour run is observable (count processed /
  errored / current rate).

### 1.4 Output bundle writer — [src/tidder/io/output_bundle.py](../src/tidder/io/output_bundle.py)

- `write_bundle(output_dir, classifications, metadata, confidence_threshold)`:
  - Partition classifications: errored, kept (max score ≥ threshold),
    dropped (max score < threshold, not written anywhere).
  - Sort kept by `max_score` DESC.
  - Write `flagged_comments.csv` using `FLAGGED_COLUMNS` from
    [csv_schema.py](../src/tidder/io/csv_schema.py); `flagged_for_del`
    defaults to `true`.
  - Write `errored_comments.csv` only if non-empty.
  - Write `buckets.json` (index → description) and `run_metadata.json`
    (from `RunMetadata`).
  - Zip them into a single archive named
    `{source_archive_stem}_{timestamp}.zip` inside `output_dir`. Return the
    archive path.
- Also implement `read_bundle()` (needed by `remove`): extract to a temp
  dir, return paths to the CSVs + metadata.

### 1.5 Wire `process._run_async` — [src/tidder/commands/process.py](../src/tidder/commands/process.py)

- Instantiate provider via `llm.get_provider(...)`.
- Build a `RunMetadata`, mark `started_at`.
- Call `run_classification(...)`.
- Mark `finished_at`, call `write_bundle(...)`.
- Print the bundle path + a "next: `tidder remove --input <path>`" hint.
- `try/finally` to ensure `provider.aclose()` runs.

### 1.6 Tests

- Unit: archive parser on a fixture export, classifier on a `FakeProvider`,
  output writer on hand-built classifications, CSV-schema formatters.
- Integration smoke test: full `process` run against a small fixture + fake
  provider; assert the bundle has the expected files and ordering.

---

## Workstream 2 — `remove` end-to-end

Goal: `tidder remove --input <bundle.zip>` (with `--dry-run`, `--mode`, and
`--overwrite-style` honored) overwrites or deletes flagged comments via
Reddit.

### 2.1 Random overwriter — [src/tidder/overwriter.py](../src/tidder/overwriter.py)

- Implement `RandomOverwriter.generate()`. Bundle a small wordlist as a
  package resource (or use `secrets`/`random` over a curated word set). Vary
  length (e.g. 20–80 words) and punctuation so outputs aren't suspiciously
  uniform. Must be unique per call.

### 2.2 Reddit auth — [src/tidder/reddit/auth.py](../src/tidder/reddit/auth.py)

- Implement `load_credentials` / `save_credentials` (mode `0600`, parent dir
  created if missing).
- `interactive_oauth()`: spin up a tiny local HTTP listener on a fixed
  loopback port, open the user's browser to Reddit's auth URL with that
  redirect, capture the `code` on callback, exchange for a refresh token,
  return `StoredCredentials`. App credentials (`client_id` and the
  installed-app secret, if any) come from env vars or `~/.config/tidder/
  config.toml` — document the setup in the README.
- `fetch_access_token(creds)`: POST to Reddit's token endpoint with the
  refresh token; return the short-lived access token. Raise a typed error
  on `invalid_grant` so the caller can re-prompt.

### 2.3 Reddit client — [src/tidder/reddit/client.py](../src/tidder/reddit/client.py)

- Implement `overwrite_comment(id, new_body)` (POST `/api/editusertext`)
  and `delete_comment(id)` (POST `/api/del`). Acquire the limiter on every
  call.
- Handle 429s: respect `Retry-After`, exponential backoff with jitter,
  cap retries.
- Refresh the access token when a 401 comes back mid-run (don't crash a
  long run because the token expired).

### 2.4 Wire `remove._run_async` — [src/tidder/commands/remove.py](../src/tidder/commands/remove.py)

- `read_bundle()` to extract; iterate `flagged_comments.csv`.
- Filter to rows with `flagged_for_del = true`.
- Build the `Overwriter` (only in `--mode overwrite`).
- `--dry-run`: print the plan (`N comments would be overwritten/deleted`).
  When `--overwrite-style llm` is also set, generate ~3 sample replacements
  and print them for tone-check before the user commits to a real run.
- Live run: ensure auth (load creds, or kick off `interactive_oauth`),
  build `RedditClient`, dispatch each row through the limiter. Bounded
  concurrency via `--concurrency`.
- Progress logging + a final summary (touched / skipped / errored).

### 2.5 Tests

- Unit: `Overwriter` factory + each style (random uniqueness, fixed echo,
  llm via `FakeProvider`).
- Unit: client respects the limiter (use a fake transport via `httpx.MockTransport`
  and assert call timing / count).
- Integration: dry-run against a fixture bundle prints the expected plan.

---

## Workstream 3 — Cross-cutting

### 3.1 Logging

- Use `logging` with a single `tidder` root logger. Configure once in
  `cli.py` (or a tiny `logging_setup.py`). Default `INFO` to stderr; `-v`
  flag bumps to `DEBUG`.
- Long-running loops log progress every N items or every M seconds,
  whichever first.

### 3.2 Config-file plumbing

- The loader already exists in [config.py](../src/tidder/config.py).
  Confirm the documented precedence (defaults < TOML < env < flags) works
  end-to-end with at least one test.
- Document the supported keys in the README.

### 3.3 README

- Install instructions, quickstart for both commands, where credentials
  live, how to point at a non-default Ollama host, and an example
  `config.toml`.

### 3.4 Cleanup

- Remove the `requirements.txt` "double `-r requirements.txt`" duplication
  in [init_env.sh](../init_env.sh) (or replace the script with a one-liner
  pointing at `pip install -e .[dev]`).

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
- A user can run `tidder remove --dry-run` and see an accurate plan
  (including LLM-overwrite samples when applicable).
- A user can run `tidder remove` in both `overwrite` (all three styles)
  and `delete` modes against their own account without tripping Reddit's
  rate limits.
- Errored comments are captured in `errored_comments.csv`, not silently
  dropped.
- `pytest` is green: unit coverage of the pure-function core (archive
  parsing, classifier loop with `FakeProvider`, bundle writer, overwriter
  factory, CSV formatters) plus integration smoke tests for both
  subcommands.
- README walks a new user from `pip install -e .` to a finished run.

---

## Resolved Decisions

- **Reddit auth.** Interactive OAuth on first `remove`; persist refresh
  token to `~/.config/tidder/credentials.json` (`0600`); silently refresh
  access tokens on every subsequent run; only re-prompt if the refresh
  token is invalidated.
- **Overwrite text.** Three styles via `--overwrite-style`: `random`
  (default, local random-words, unique per comment), `llm` (LLM-generated,
  generic/neutral/plausible), and `fixed` (user-provided constant string).
- **Concurrency.** Worker pool from the jump, `--concurrency` flag, default
  `4`.
- **CLI / package layout.** Typer + `src/tidder/` layout with subcommands
  under `commands/`, providers under `llm/`, Reddit code under `reddit/`,
  IO under `io/`. Config via `pydantic-settings` with defaults < TOML <
  env < flags precedence.
- **Async model.** `asyncio` end-to-end; `httpx.AsyncClient` for both
  Ollama and Reddit; `aiolimiter` for Reddit rate limiting.

## Open Questions for This Sprint

- Reddit OAuth app registration: do we ship a shared client_id for the CLI
  (installed-app flow, no secret) or require each user to register their
  own? Shared is friendlier; per-user is more transparent and removes us
  as a dependency. Lean shared, document the fallback.
- Random-overwriter wordlist source: bundled curated list, or use
  `/usr/share/dict/words` when present? Bundled is portable; system dict
  is zero-effort. Lean bundled.
