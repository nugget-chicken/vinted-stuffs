# Bundle opportunity dashboard (wardrobe-building first)

Date: 2026-09-05  
Status: approved for planning  
Repo: `vinted-stuffs`  
Supersedes (partially): `2026-09-05-value-haul-hunt-design.md` non-goals that excluded maternity and near-miss persistence.

## Problem

The live dashboard shows ~17 crème solo keeps while `seen_keys` holds ~8000 processed listings. That is expected under the current solo path (`min_deal_score` 9, “most listings should fail”), but it does **not** match how the buyer actually shops:

> If one seller has several usable H&M Sport / Mama pieces in size, make a bundle offer.

Value hauls exist in code, but:

1. Closet crawl was broken (`catalog/items?seller_id=` ignored) until the wardrobe API fix — so multi-item closets rarely evaluated correctly.
2. Only LLM-approved `value_haul` rows persist; fee-gated closets that the model skips never appear.
3. Maternity wardrobe seeds (`bundle_hunt`) never become solo finds and were out of scope for value hauls in v1.
4. Caps (`max_value_hauls_per_run`, crawl seller caps) keep volume tiny even when candidates exist.

## Goal

Retarget hunt **persistence and dashboard** toward **same-seller multi-item opportunities** for **gym and maternity** wardrobe building. Solo crème keeps remain; they are no longer the only rows that “count.”

Success looks like option **C**: a wider opportunity list on the dashboard; only the strongest also ntfy-alert.

## Non-goals

- Relaxing premium solo keep rules for Craft / Lululemon / knitwear / sneakers (those stay crème).
- Cross-run haul merge (“yesterday’s 2 + today’s 2”).
- Auto-sending Vinted bundle offers.
- Redesigning the Finds table into a general “all scored listings” dump.
- Changing checkout fee tables in this change (reuse existing `checkout_fees`).

## Domain

| Term | Meaning |
|---|---|
| **Value haul** | Gate + LLM steal/hunt keep. `kind: "value_haul"`. Alerts + dashboard. |
| **Near haul** | Gate passes on prefiltered closet candidates (size + category fit + fee math). LLM weak/skip, failed parse, or intentionally not scored. `kind: "near_haul"`. **Dashboard only** (no ntfy). |
| **Bundle hunt** | Watch with `bundle_hunt: true`. Seeds closet inspection; never solo `is_keep`. |
| **Keep-bundle** | Existing ≥1 keep + extras. Unchanged. |

## Approaches considered

1. **Widen value-haul path + persist near hauls** (chosen) — reuses closet/gate; Bundles tab becomes the wardrobe surface.
2. Lower solo keep bar for maternity/gym — floods Finds with weak singles; still one-listing thinking.
3. Separate opportunities store/UI — cleaner split, slower to ship.

## Architecture

```
bundle_hunt seeds (gym + maternity)     hunt-fit gym/maternity Path B
        │                                         │
        ▼                                         ▼
   closet crawl (wardrobe API)  ◄─────────────────┘
        │
        ▼
   prefilter (size + gym/maternity tokens + max price)
        │
        ▼
   fee gate (existing passes_value_haul_gate)
        │
        ├─► LLM score_value_haul
        │         │
        │         ├─ alert rules pass → persist value_haul (+ ntfy)
        │         └─ else → persist near_haul (dashboard)
        │
        └─► (optional score skip when LLM budget exhausted)
                  → persist near_haul
```

**Invariant:** once a seller’s closet clears the **fee gate** with ≥2 prefilter candidates for a haul watch, the run **must** write either `value_haul` or `near_haul` (unless fingerprint already in `best_bundles` / alerted keys for the same useful-id set).

## Persistence

### Record shape

Extend `data/best_bundles.json` entries:

- `kind`: `"value_haul" | "near_haul" | "keep_bundle"`
- `seller`, `seller_id` always set when known
- `items[]` each carry `seller` / `seller_id` when known
- `effective_price_per_useful_item` / rough delivered estimate
- `reason`: LLM reason, or for near hauls a fixed short string such as `"Fee-gated closet match (not LLM-confirmed)"`
- `value_band`: for near hauls use `"opportunity"` (dashboard badge); do not require steal/hunt
- `deal_score`: near hauls may use `null` or a rough placeholder; UI must not treat them as 9/10 keeps

### Dedup

- Fingerprint remains `seller_id:sorted_item_ids` (useful/prefilter ids).
- If a stronger `value_haul` arrives for an overlapping fingerprint, replace or supersede the `near_haul` row (prefer value_haul).
- Cap list growth: keep newest N opportunity rows (config `max_opportunity_bundles`, default 80) while preserving recent keep_bundles.

### Caps (config under `value_haul`)

| Key | Purpose | Suggested default |
|---|---|---|
| `max_value_hauls_per_run` | LLM-confirmed + alert | 10 |
| `max_near_hauls_per_run` | Dashboard-only gate passes | 25 |
| `max_closet_sellers` | Crawl budget | 40 (keep) |
| `max_seeds_per_watch` | Seeds marked seen without crawl explosion | 25 (keep) |

Scoring budget: attempt LLM for gated sellers up to `max_value_hauls_per_run`; remaining gated sellers in the same run still emit `near_haul` without LLM when under `max_near_hauls_per_run`.

## Maternity + gym path eligibility

- `is_value_haul_path_watch`: gym **or** maternity (already partially true) — ensure maternity **bundle seeds** always enter seed → closet → gate.
- Prefilter already has maternity tokens + seed-brand acceptance; keep that.
- Prompt for maternity hauls: wardrobe building / nursing utility, not “premium Seraphine only.”
- Solo maternity premium watches (Seraphine, etc.) unchanged for Finds.

## Dashboard

- Bundles tab: badges for `value haul` / `near haul` / `keep bundle`.
- Default sort: newest opportunity first; filter chips optional (all / hauls / near / keep).
- Empty state copy updated to describe near hauls.
- Seller username links required (existing backfill stays).
- Finds tab: no change required for this feature (still crème solos).

## Alerts

- **ntfy only for `value_haul`** (and existing keep / keep_bundle).
- Near hauls never alert (avoid spam while filling the board).

## Error handling

- Closet failure: skip seller (unchanged).
- LLM failure after gate: **persist `near_haul`**, do not drop the opportunity.
- Missing login: still persist with `seller_id`; dashboard shows id until backfill.

## Testing

1. Gate pass + LLM skip band → `near_haul` record kind.
2. Gate pass + LLM steal → `value_haul`; supersedes prior near_haul same fingerprint.
3. Maternity seed watch produces haul-path eligibility.
4. Dashboard snapshot / render treats `near_haul` badge (unit or snapshot fixture).
5. Existing value-haul alert tests unchanged for steal path.

## Success criteria (verification)

On live `https://vinted-stuffs.vercel.app` after a real hunt (or focused local publish):

1. Bundles tab shows **multiple** `near_haul` and/or `value_haul` rows for gym and/or maternity, each with seller username when known.
2. At least one maternity-path opportunity (Mama/Next/ASOS seed lineage or maternity prefilter) appears if the hunt found a gated closet.
3. Solo Finds crème behavior unchanged for premium watches.
4. Closet crawl uses wardrobe API (no cross-seller junk under one id).

## Implementation touchpoints

- `scripts/value_haul.py` — `near_haul` record helper, alert vs persist split
- `scripts/vinted_bot.py` — after gate: always persist; LLM optional; maternity seeds
- `scripts/config.json` — caps
- `dashboard/app.js` (+ CSS if needed) — badges / copy
- `lib/snapshot.js` / `scripts/serve_dashboard.py` — kind passthrough
- `scripts/test_value_haul.py` — near-haul cases
- Optional: amend CONTEXT.md domain terms

## Out of scope follow-ups

- Opportunity rows on Finds tab
- Auto-ranking “best offer price” suggestions
- Pushing wardrobe fix upstream to `googlarz/vinted-mcp-cli` (Actions already on `rolki-png` fork)
