# Sprint 3 — Public Webapp

**Goal:** Take the MVP CLI and lift it into a hosted webapp at (TBD
domain). Users sign in, upload their Reddit export, configure buckets,
watch `process` run, review/edit flags in the browser, and trigger
`remove` — all without touching a terminal.

See [overview.md](overview.md), [sprint-1.md](sprint-1.md), and
[sprint-2.md](sprint-2.md) for prior context. The data contract (the
output `.zip`, `flagged_comments.csv`, `buckets.json`, etc.) carries
over unchanged — the webapp is a new frontend over the same pipeline.

---

## In Scope

### Hosting + accounts

- User accounts (email + password at minimum; OAuth via Reddit is a
  natural fit and probably the right call since we'll need their
  Reddit OAuth anyway for `remove`).
- Per-user storage for uploaded exports, run outputs, and review state.
- Decide hosting target (VPS? managed PaaS?) and pick a deployment
  story.

### Upload + process

- Browser upload of the Reddit `.zip` export.
- Bucket configuration UI (add/remove/edit bucket strings, save
  presets).
- LLM provider selection: a hosted default (whatever frontier provider
  we go with) plus BYO-API-key for users who want it.
- `process` runs server-side as a background job; user sees progress
  and can navigate away and come back.

### Review UI (productionized)

- Builds on the Sprint 2 renderer — same Reddit-themed infinite scroll,
  same flag/unflag semantics — but now backed by the user's stored run
  output instead of a local CSV.
- Edits persist server-side.
- Filter / search within a run (by bucket, by score, by subreddit).

### Remove

- Triggered from the UI against the user's stored, post-review flag
  state.
- Reddit OAuth handled by the webapp (no CLI dance).
- Same dry-run and overwrite-vs-delete semantics as the CLI.
- Surface progress + any rate-limit backoff in the UI.

### Everything else worth dragging in

- Subreddit whitelist exposed as a UI filter rather than a flag.
- Resumable processing (if not already done in Sprint 2) becomes
  table-stakes here.
- Basic observability: per-user run history, errored-comment review.

---

## Out of Scope

- Multi-account / org / team features.
- A polished mobile app (the webapp should be responsive, but native
  apps are not in scope).
- Anything billing-related unless we decide to charge.

---

## Definition of Done

- A user can sign up, upload their export, configure buckets, run
  `process`, review/edit flags, and run `remove` — all from the
  browser.
- The CLI still works against the same data contract for power users
  who prefer it.
- Reddit OAuth is wired up cleanly for `remove`.
- At least one real end-to-end run by a non-developer test user
  succeeds without intervention.

---

## Open Questions for This Sprint

- Hosting + deployment target.
- Cost model for the hosted LLM: do we eat the inference cost (and how
  do we cap it), or require BYO-API-key for any non-trivial run?
- Data retention: how long do we keep uploaded exports and run outputs?
  Default to short retention + user-initiated deletion.
- Do we keep the local `tidder review` renderer alive as a maintained
  artifact, or sunset it once the webapp is live?
