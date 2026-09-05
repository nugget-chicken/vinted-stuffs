# Gym shorts broad discovery

Date: 2026-09-05  
Status: approved design  
Repo: `vinted-stuffs` (config in `scripts/config.json`; bot unchanged)

## Problem

Gym hunting today is mostly a **premium brand watchlist** (Lululemon, Ten Thousand, Rhone, …) plus a single `h&m sport` bundle seed.

That misses ordinary M/L gym shorts (Nike, Adidas, Under Armour, Hummel, Virtus, Endurance, Domyos, etc.) that never appear in a brand query. `notes` only steer the LLM after a listing is already fetched — they do not widen Vinted search.

A one-shot “look at every recent M/L gym short” is also blocked on normal runs by the global `max_new_items_per_watch: 15` cap (unless `FULL_SWEEP=1`).

## Goal

1. **Broad shorts discovery** — watches that search for gym/training shorts by product language, not brand, with men’s M/L size filter.
2. **Multi-brand gym bundle seeds** — cheap hits become closet-crawl seeds so 20–50 RON pieces can form value hauls with tees/pants from the same seller.
3. **One-time full broad sweep** — temporary sweep-only config + `FULL_SWEEP=1`, then resume the full config. Premium brand watches stay for mis-categorised rare pieces.

Focus: **men’s gym shorts** for discovery; tees/pants only via bundle/closet when the seller also has useful M/L gymwear.

## Non-goals (v1)

- Python changes (per-watch caps, cheap prefilter before LLM, scoped `FULL_SWEEP` flag)
- `category_id` filters (Vinted category initializer API currently 404s)
- HU / PL markets
- Changing sneaker, knitwear, or maternity watches
- Raising the global `max_new_items_per_watch` for everyday runs

## Architecture

Three channels, all config-driven; existing bot / value-haul code paths:

| Channel | Config shape | Runtime behaviour |
|---|---|---|
| Broad shorts | Normal watches, shorts-focused queries | Search → score → keep if steal/hunt |
| Premium gym brands | Existing brand watches; notes prefer shorts | Unchanged search; clearer scoring hints |
| Bundle seeds | `bundle_hunt: true` | Seeds only → closet crawl → value haul / keep-bundle |

```text
[sweep config + FULL_SWEEP=1]  --once-->  score all broad shorts + gym seeds
                |
                v
[full config.json]  --ongoing-->  15 new/watch + premium + seeds
```

## Config changes

### Shared filters

- Country: `ro`
- Men’s clothing sizes M/L: `size_ids: [208, 209]` (size group 14 “Mărimi bărbați”)
- Also keep `target_sizes: ["M", "L"]` for LLM / value-haul text matching
- No `category_id` in v1

### Broad shorts watches (new, not `bundle_hunt`)

| name | query | per_page | price_to | hunt_price |
|---|---|---|---|---|
| Broad gym shorts M-L | `short sport` | 50 | 120 | 70 |
| Broad training shorts M-L | `pantaloni scurti sport` | 50 | 120 | 70 |
| Broad gym short EN M-L | `gym shorts` | 50 | 120 | 70 |
| Broad dri-fit shorts M-L | `dri fit short` | 50 | 120 | 70 |

- `target_type`: men's gym or training shorts
- `notes`: Prefer technical training / gym shorts in good condition. Skip kickboxing/football kits, casual cargo, and non-gym fashion shorts unless an exceptional steal. Brand-agnostic: Nike, Adidas, UA, Decathlon/Domyos, Hummel, Craft, etc. all valid.

### Bundle seeds (replace single “Gym bundle seeds M-L”)

Each with `bundle_hunt: true`, `per_page: 50`, `price_to: 80`, `hunt_price: 50`, `target_sizes` M/L, `size_ids` [208, 209] where useful:

| name | query |
|---|---|
| Gym seed H&M Sport M-L | `h&m sport` |
| Gym seed Nike Dri-Fit M-L | `nike dri fit` |
| Gym seed Adidas training M-L | `adidas training` |
| Gym seed Under Armour M-L | `under armour` |
| Gym seed Domyos M-L | `domyos` |
| Gym seed Hummel M-L | `hummel` |
| Gym seed Craft M-L | `craft` |
| Gym seed short sport M-L | `short sport` |

- `target_type`: men's gym clothing suitable for building a multi-item bundle
- `notes`: Seeds only — never solo-alert. Prefer sellers with several useful M/L gym pieces (shorts, tees, training pants). Individual 20–50 RON items are weak alone; same-seller multi-piece + one shipping is the goal.

### Premium gym watches (existing Lululemon … 2XU)

- Keep queries, prices, `per_page`
- Update `target_type` / `notes` to prefer shorts first, then tees/pants; still reject casual non-gym pieces

### Sweep-only config

New file: `scripts/config.gym-shorts-sweep.json`

- Same top-level scoring / value_haul / checkout settings as `config.json` (copy relevant keys)
- `watches`: only the 4 broad shorts watches **and** the 8 gym bundle seeds (seeds so the sweep also indexes cheap closet triggers)
- No sneakers, knitwear, maternity, or premium brand watches

One-time run:

```bash
VINTED_CONFIG=scripts/config.gym-shorts-sweep.json FULL_SWEEP=1 uv run python scripts/vinted_bot.py
```

Then resume normal `config.json` runs. Dedup uses per-hunt `seen_keys`, so later runs only score unseen listings for those hunt names.

## Limits and trade-offs

- Task 4 one-time `FULL_SWEEP` remains deferred until after the correct men’s size IDs land and any concurrent backfill job finishes.

- Everyday runs still cap at 15 new items per watch (global). Full coverage is the **sweep**, not every cron tick.
- Sweep scores every unseen listing from paginated search (`full_sweep_max` default 400 per watch in bot). Expect higher LLM cost once.
- Overlap: `short sport` appears as both broad and seed — intentional: broad can keep a steal; seed path never solo-keeps and drives closet crawl.
- Without Python prefilter, sweep may spend tokens on kickboxing kits / wrong gender; notes + size_ids reduce but do not eliminate noise.

## Success criteria

- After sweep: scored index / alerts include brand-agnostic M/L gym shorts (not only premium brands).
- Bundle seeds produce closet value-haul candidates when a seller has multiple cheap gym pieces.
- Premium brand short steals still surface from existing brand watches.
- Normal runs after sweep do not re-score the same broad hunt keys.

## Implementation notes

- Config-only; no `vinted_bot.py` / `value_haul.py` changes for v1.
- Prefer editing watches in place: remove the old single “Gym bundle seeds M-L” entry when adding the eight seeds.
- Do not commit secrets; config remains non-secret search definitions.
