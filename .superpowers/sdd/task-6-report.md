# Task 6 Report: Wire discovery + scoring into the run loop

## Status

**DONE_WITH_CONCERNS.** The run-loop wiring is complete and the required unit
tests pass. The smoke run reached normal completion, but the configured `npx`
Vinted CLI could not resolve an executable, so it could not exercise live
search, closet, or DataDome behavior.

## Commit

- `284d001 Wire value-haul discovery, scoring, and alerts into the bot run.`

## Changes

- Added `score_value_haul`, using AI Gateway first and Gemini fallback, with
  single-object parsing through `value_haul.parse_value_haul_score`.
- Split bundle-hunt and premium watches. Bundle-hunt listings are marked seen
  and collected as seller seeds without solo LLM scoring.
- Added men's-gym Path B detection while excluding maternity, sneaker, knit,
  and cashmere watches.
- Deduplicated value-haul work by seller, preferring bundle-hunt watch metadata
  when a seller is discovered by both paths.
- Built seller-level closet requests: value-haul and Path B sellers use the
  configured 36-item limit; ordinary premium sellers retain the 12-item limit.
- Prefiltered and gated closet candidates, added test-mode value-haul scores,
  scored live hauls through the new scorer, and applied post-reject alert rules.
- Built enriched haul dictionaries from useful items, including `seller`,
  `seller_id`, `country`, checkout extra, listing sum, and checkout total.
- Shared `alerted_bundle_keys` between value hauls and keep-bundles and enforced
  `max_value_hauls_per_run`.
- Persisted value hauls to `best_bundles.json` via `value_haul_record`; value
  hauls are not added to `bundle_pool.json`.
- Added `kind: keep_bundle` to newly persisted keep-bundles.

## Verification

Required tests:

```text
cd scripts && uv run python -m unittest test_value_haul test_keep_rules test_bundle_pool -v
Ran 20 tests in 0.000s
OK
```

Additional checks:

```text
uv run python -m py_compile scripts/vinted_bot.py
git diff --check
```

Both exited successfully.

## Smoke

Command:

```text
SKIP_SCORING=1 NTFY_TOPIC=test uv run python scripts/vinted_bot.py
```

The process exited `0`, printed the bundle-hunt line as
`0 seeds (no solo score)`, and reached `Run complete` without an import or
wiring crash. Search and pool seeding failed before live data retrieval with:

```text
vinted CLI failed (1): npm error could not determine executable to run
```

Smoke-generated state changes were removed before the implementation commit.

## Concerns

- Live seed collection, 36-item closet crawling, and ntfy delivery were not
  exercised because the local Vinted CLI fallback failed to launch.
- The required unit suites cover the pure value-haul helpers and existing keep
  and pool behavior, but there is no dedicated mocked end-to-end run-loop test.

## Important review fixes

- Per-seller closet errors now omit that seller from `get_seller_closets`,
  while successful empty closets remain present as `seller_id: []`.
- Value-haul evaluation now skips sellers missing from the closet result, so
  trigger seeds cannot independently produce an alert after a closet failure.
- Alert fingerprints now retain state-file insertion order, use a set only for
  membership, append both value-haul and keep-bundle keys through one helper,
  and persist the newest 200 ordered entries.
- Added regressions for failed-versus-empty closet results and ordered,
  deduplicated fingerprint retention.

Fix verification:

```text
cd scripts && uv run python -m unittest test_value_haul test_keep_rules test_bundle_pool -v
Ran 22 tests in 0.001s
OK

uv run python -m py_compile scripts/vinted_bot.py scripts/test_bundle_pool.py
git diff --check
```

All commands exited successfully.
