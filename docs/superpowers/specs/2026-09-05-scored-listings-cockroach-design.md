# Scored listings cache in CockroachDB

Date: 2026-09-05  
Status: approved for planning  
Repo: `vinted-stuffs`

## Problem

`data/seen_listings.json` stores only thin dedup keys (`item_id:hunt_name`). After a run, title, price, seller, and score are discarded except for keeps (`best_deals.json`), this-run top 15 (`last_run.json`), and keep/extra rows in `bundle_pool.json`.

When the same seller later uploads a new keep-worthy item, previously scored pieces from that closet are invisible unless we re-crawl and re-score them. That wastes LLM budget and misses same-seller bundles that only become viable once a new listing appears.

## Goal

Persist **every LLM-scored listing** as a reusable score cache so the bot can:

1. Reuse stored scores as-is (no rescore) when a seller becomes interesting again.
2. Availability-check cached item IDs and feed still-listed rows into existing bundle / value-haul assembly.

Success: a seller with prior scored wardrobe items + one new keep this run can form a keep-bundle (or value-haul candidate set) using cached scores without calling the LLM for the old IDs.

## Non-goals (v1)

- Dashboard UI for the score cache.
- Backfilling historical bare `seen_keys` into Cockroach (no recoverable title/score).
- Moving `best_deals`, `best_bundles`, `bundle_pool`, or alert fingerprints into Cockroach.
- Rescoring when hunt rules/prompts change (explicit escape hatch later).
- Storing unscored bundle-hunt seeds in Cockroach (they remain JSON `seen_keys` only).

## Decisions

| Topic | Choice |
|---|---|
| Primary use | Reuse scores as-is; only re-check listing availability |
| What to store | Every LLM-scored listing, including skips and non-fits |
| Storage | Hybrid: thin `seen_keys` stay in git; rich rows in CockroachDB |
| Host | CockroachDB Basic (Postgres wire protocol; free tier ~50M RUs + 10 GiB/org/month — set resource limits) |

## Architecture

```
score_batch (LLM)
    │
    ├─► mark_seen → data/seen_listings.json (git)
    └─► upsert   → Cockroach scored_listings

seller becomes interesting
    │
    ├─► SELECT scored_listings WHERE seller_id = ?
    ├─► check_items_available (existing CLI batch)
    ├─► rebuild {item, score, watch, watch_obj} from cache + fresh payload
    └─► merge_scored → assemble_bundles / value-haul paths (no LLM)
```

### Responsibilities

| Store | Role |
|---|---|
| `data/seen_listings.json` | Dedup + run meta: `seen_keys`, `crawled_trigger_ids`, `alerted_bundle_keys`, counters |
| CockroachDB `scored_listings` | Durable score/item snapshot for reuse |

If `DATABASE_URL` is unset or Cockroach is unreachable: behavior matches today (dedup via git); only the revive-from-cache path is skipped. Hunt runs must not fail solely because of DB errors.

## Data model

Table `scored_listings` — one row per `(item_id, hunt_name)`:

| Column | Type / notes |
|---|---|
| `item_id` | BIGINT — Vinted listing id |
| `hunt_name` | TEXT — watch `name` |
| `title` | TEXT |
| `price` | DECIMAL / NUMERIC nullable |
| `currency` | TEXT |
| `brand` | TEXT nullable |
| `size` | TEXT nullable |
| `condition` | TEXT nullable |
| `url` | TEXT nullable |
| `favourite_count` | INT nullable |
| `seller_id` | BIGINT nullable — required for seller-keyed reuse when known |
| `seller_login` | TEXT nullable |
| `seller_country` | TEXT nullable |
| `deal_score` | INT |
| `value_band` | TEXT |
| `hunt_fit` | BOOL |
| `scam_risk` | TEXT |
| `reason` | TEXT |
| `scored_at` | TIMESTAMPTZ |
| `source` | TEXT — `search` \| `closet_crawl` |

Primary key: `(item_id, hunt_name)`.  
Index: `(seller_id)` for reuse queries.  
Upsert on conflict overwrites the snapshot (later score for the same pair wins).

## Bot integration

### Write path

After a successful score in `score_batch` for an item:

1. Upsert Cockroach row from normalized item + score + hunt + `scored_at` + `source`.
2. `mark_seen` in JSON as today.

Bundle-hunt seeds that are marked seen **without** LLM scoring do **not** get a Cockroach row.

### Read path

When a seller becomes interesting (new hunt-fit / keep / bundle-extra this run, or closet crawl / value-haul seed for that seller):

1. `SELECT` rows for that `seller_id`.
2. Drop IDs already present in this run’s `scored` / merged pool.
3. Availability-check remaining IDs via existing `check_items_available`.
4. For still-listed items: rebuild candidate rows from cache + fresh item payload; resolve `watch_obj` from current config by `hunt_name`.
5. Drop rows whose hunt name is no longer in config.
6. Merge into `merge_scored` → existing `assemble_bundles` / value-haul logic. **Do not** call the LLM for reused rows. Existing `is_keep` / `is_bundle_extra` / haul prefilters decide usefulness; skipped or non-fit cached rows simply do not join carts.

### Secrets / config

- Connection string: prefer `DATABASE_URL`; accept `COCKROACH_DATABASE_URL` as alias. Set in GitHub Actions secrets and local env.
- Optional: set Cockroach Basic monthly resource limits so overrun cannot disable the cluster unexpectedly.
- Schema: `scripts/sql/001_scored_listings.sql`; v1 may also `CREATE TABLE IF NOT EXISTS` on connect for easy first run.
- Python driver: `psycopg` (Postgres wire), added to `scripts/requirements.txt`.

### Errors

- DB down / auth / timeout: log to stderr; skip write and/or read for that run; continue hunt.
- Partial upsert failure: log failed IDs; still `mark_seen` so the bot does not infinite-rescore.
- Missing `seller_id` on write: still store the row (dedup + future hunt reuse by id); seller-keyed revive simply won’t find it until seller is known.

## Testing

- Unit tests against a fake store interface (`upsert`, `load_by_seller`, rebuild round-trip) — no live Cockroach in default CI.
- Optional integration test gated on `DATABASE_URL`.
- One behavioral test: prior cached seller listing + new keep this run → bundle assembly uses cached score without a scorer call.
- Existing keep / bundle / value-haul tests remain green.

## Open follow-ups (post-v1)

- Prompt/rule version column + selective rescore when scoring policy changes.
- Dashboard read of score histogram / near-misses from Cockroach.
- Prune policy if storage approaches free-tier limits (not required for v1 given “keep everything scored”).
