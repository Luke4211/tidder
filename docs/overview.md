# Tidder — Project Overview

A tool for cleaning up a user's Reddit comment history by using an LLM to classify
each comment against a user-defined set of "content type buckets," surfacing the
risky ones for review, and then deleting or overwriting them via the Reddit API.

The MVP is a CLI. A web-based frontend and public webapp deployment are planned
follow-ons; the CLI commands are designed so the review/remove steps can later be
swapped for, or fronted by, a webapp without changing the underlying data flow.

---

## Goals

- Let a user feed in their full Reddit data export and a list of "things I don't
  want to be associated with anymore" (the buckets).
- Use a locally-hosted LLM (Ollama, initially) to score each comment against
  every bucket -- eventually we will offer the option to use Frontier LLM's
  that the user would provide an API key for.
- Produce a sorted, reviewable artifact (CSV) of comments that are likely
  matches, with a per-comment `flagged_for_del` toggle.
- Provide a path from that artifact to actually overwriting/deleting the
  flagged comments through Reddit's API.

## Non-Goals (for MVP)

- A polished web UI. A minimal local web renderer is a stretch goal; the public
  webapp is explicitly post-MVP.
- Support for non-Ollama LLM providers. The CLI surface should leave room for
  this (e.g. an `--llm-provider` flag), but only Ollama is wired up at MVP.
- Multi-account / shared-tenant concerns.
- Subreddit whitelist -- pass process a whitelist of subreddits and only process
  comments from within those subs.

---

## Inputs

### Reddit data export

Users upload the `.zip` archive Reddit emails them after requesting their data.
The tool unpacks it internally and locates the relevant files (e.g.
`comments.csv`, and `comment_headers.csv` when present) rather than asking the
user to extract anything by hand.

### Bucket definitions

A list of natural-language strings describing categories of content the user
wants flagged. Examples:

```
[
  "personally identifying information",
  "anything you wouldn't want read in front of a jury",
  "overtly political rhetoric"
]
```

Buckets are referenced internally by index (`0`, `1`, …, `n`). The
index → description mapping is persisted alongside the output CSV (see
[Outputs](#outputs)).

### LLM configuration

- `--llm-host` (default: `http://localhost:11434`) — where to reach Ollama.
- `--llm-model` — required; the Ollama model name to use.
- (Future) `--llm-provider`, `--api-key` for external providers.

### Confidence threshold

- `--confidence-threshold` (default: `0.75`) — a comment is included in the
  output if **any** bucket score meets or exceeds this value.

---

## Commands

### `process`

Classifies every comment in the archive and writes the review artifact.

```
tidder process \
  --archive path/to/reddit_export.zip \
  --buckets "PII" "political rhetoric" \
  --llm-model llama3.1 \
  [--llm-host http://localhost:11434] \
  [--confidence-threshold 0.75] \
  [--output-dir ./out]
```

**Flow:**

1. Unpack the archive; locate `comments.csv` (and headers file if present).
2. Iterate over comments, in batches (batch size TBD — see
   [Open Questions](#open-questions)).
3. For each comment, send a prompt to the configured LLM containing:
   - the bucket list and what each bucket means,
   - the comment text,
   - instructions to return a JSON object mapping each bucket to a
     confidence score in `[0.00, 1.00]`, where `0.00 = definitely not in
     this bucket`, `0.50 = unsure`, `1.00 = definitely in this bucket`.
4. If `max(scores) >= confidence_threshold`, append a row to the output.
5. After all comments are processed, sort the output rows by
   `MAX(confidence_mapping) DESC`.
6. Write the output CSV and the bucket-index metadata file, and print the
   paths plus a short "next steps" message pointing at `review` and
   `remove`.

### `review` (MVP scope TBD)

Lets the user audit and toggle `flagged_for_del` per comment.

The webapp version renders the output CSV as an infinite-scroll, Reddit-themed
page where each comment has a flag/unflag control that mutates the source CSV
in place.

For the CLI MVP, options under consideration:

- Skip a real `review` command entirely and tell the user to edit the CSV
  by hand.
- Ship the minimal local web renderer described above as `tidder review`,
  which serves the page on `localhost`. This keeps the rendering logic in
  one place and lets it be reused by the eventual webapp.

This needs to be decided before we start building — see
[Open Questions](#open-questions).

### `remove`

Acts on the (possibly user-edited) output CSV, performing the actual cleanup
via Reddit's API.

```
tidder remove \
  --input ./out/flagged_comments.csv \
  [--mode overwrite|delete]   # default: overwrite
```

- `overwrite` (default): replaces the comment body with placeholder text.
  Safe to run repeatedly; intended for progressive overwriting on a schedule
  before a final deletion pass.
- `delete`: actually deletes the comments.

Only rows with `flagged_for_del = true` are touched. Rows where the user
unflagged the comment during review are skipped.

---

## Outputs

### Flagged-comments CSV

One row per comment that exceeded the confidence threshold, sorted by
`MAX(confidence_mapping) DESC`.

| Column                | Description                                                                 |
|-----------------------|-----------------------------------------------------------------------------|
| `id`                  | Reddit comment ID (from the export).                                        |
| `url`                 | Permalink to the comment.                                                   |
| `confidence_mapping`  | Stringified mapping of bucket index → confidence score, e.g. `0:0.92,1:0.10,2:0.04`. |
| `comment_text`        | Raw comment body.                                                           |
| `comment_date`        | Timestamp from the export.                                                  |
| `upvotes`             | Score/karma if available (optional, nice-to-have).                          |
| `flagged_for_del`     | Boolean. Defaults to `true`.                                                |

### Bucket-index metadata

Written next to the CSV, mapping the numeric bucket indices used in
`confidence_mapping` back to the original user-provided strings. Format TBD —
JSON is the obvious default; a sidecar CSV would also work.

```json
{
  "0": "personally identifying information",
  "1": "anything that could be construed as evidence of illicit behavior (e.g. drug use)",
  "2": "overtly political rhetoric"
}
```

---

## LLM Prompt Contract

The classifier prompt should be deterministic in shape so we can parse the
response reliably:

- Input: bucket list (with descriptions) + a single comment.
- Output: strict JSON object, keys = bucket indices (as strings), values =
  floats in `[0.0, 1.0]`. No prose, no markdown.
- Failure handling: if parsing fails or scores are out of range, the comment
  is logged and skipped (not silently dropped — see
  [Open Questions](#open-questions)).

---

## Resolved Decisions

- **Batching.** One LLM prompt per comment for the MVP — local LLMs are too
  unreliable to trust with multi-comment batches. Regardless of batch size,
  every prompt uses a **fresh context window** (no carry-over between
  comments). Batching is something to experiment with later, not now.
- **`review` command in MVP.** Yes — ship the local web renderer as
  `tidder review`. It is the **lowest priority** item in the MVP, though:
  build `process` and `remove` first, get them solid, then layer the
  renderer on top.
- **Failure / retry policy.** Retry the LLM call up to a configurable
  threshold on unparseable / out-of-range responses. Comments that still
  fail after exhausting retries are written to a tertiary output file,
  `errored_comments.csv`, so the user can hand-review or re-run them
  later. Never silently drop.
- **Resumability.** Yes, `process` should checkpoint progress so it can
  resume after interruption. Like the web renderer, this is **lowest
  priority** for MVP — implement after the core flow works end-to-end.
- **Rate limiting for `remove`.** Required. Include a Reddit-API-aware
  backoff strategy plus a `--dry-run` mode that reports what *would* be
  touched without making any API calls.

---

## Output Bundling

All artifacts from a `process` run are bundled into a single `.zip` archive
in `--output-dir`, so the user has one file to keep, move, or hand to
`review` / `remove`. Archive contents:

- `flagged_comments.csv` — the main review artifact.
- `errored_comments.csv` — comments that exhausted LLM retries (omitted if
  empty).
- `buckets.json` — the bucket-index → description mapping.
- `run_metadata.json` — model name, host, threshold, retry threshold,
  timestamp, source archive name, etc. (useful for resumability and for
  debugging unexpected output.)

The user can extract the archive manually to poke at individual files; the
`review` and `remove` commands accept the `.zip` directly and handle
extraction internally.

---

## Roadmap

1. **MVP CLI core** — `process` + `remove` (with `--dry-run` and rate
   limiting), output bundled as `.zip`, per-comment prompting with retries
   and `errored_comments.csv`.
2. **MVP CLI stretch** — `tidder review` local web renderer, and
   `process` resumability via checkpointing. Lowest priority items in the
   MVP; ship after the core is solid.
3. **External LLM providers** — pluggable backend, API key support.
   Multi-comment batching experiments live here too, since frontier models
   are more likely to handle it reliably.
4. **Webapp** — reuses the same data contract; `process` runs server-side,
   `review` becomes the polished frontend, `remove` is triggered from the UI.
