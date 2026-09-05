# Gym Shorts Broad Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add brand-agnostic M/L gym-shorts discovery and multi-brand gym bundle seeds to config, plus a one-shot FULL_SWEEP config so the first pass covers the broad market.

**Architecture:** Config-only. Everyday `scripts/config.json` gains four broad shorts watches and eight `bundle_hunt` seeds; premium gym notes prefer shorts. A separate `scripts/config.gym-shorts-sweep.json` holds only those gym watches for `VINTED_CONFIG=… FULL_SWEEP=1`. No Python changes.

**Tech Stack:** JSON config for `vinted_bot.py`; existing `FULL_SWEEP` / `VINTED_CONFIG` env vars; men's size IDs 1739 (M) / 1740 (L).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-05-gym-shorts-broad-discovery-design.md`
- Do not modify `scripts/vinted_bot.py` or `scripts/value_haul.py`
- Do not change sneaker, knitwear, or maternity watches
- Do not raise global `max_new_items_per_watch` above 15 for everyday runs
- No `category_id` in v1
- Country remains `ro`
- Size filter: `size_ids: [1739, 1740]` and `target_sizes: ["M", "L"]`

---

## File structure

| File | Responsibility |
|---|---|
| `scripts/config.json` | Full hunt list: broad shorts + gym seeds + updated premium gym notes |
| `scripts/config.gym-shorts-sweep.json` | Sweep-only: broad shorts + gym seeds + shared top-level scoring keys |
| `docs/superpowers/specs/2026-09-05-gym-shorts-broad-discovery-design.md` | Already approved; do not rewrite unless a bug is found |

---

### Task 1: Broad shorts + gym seeds in main config

**Files:**
- Modify: `scripts/config.json`

**Interfaces:**
- Consumes: existing top-level keys (`min_deal_score`, `value_haul`, `checkout_fees`, …) unchanged
- Produces: 4 broad shorts watches (no `bundle_hunt`); 8 gym `bundle_hunt` seeds replacing `"Gym bundle seeds M-L"`

- [ ] **Step 1: Remove the old single gym seed**

Delete the watch object whose `"name"` is `"Gym bundle seeds M-L"` (currently the first entry in `"watches"`).

- [ ] **Step 2: Insert the four broad shorts watches at the start of `"watches"`**

Use this exact block (JSON objects, same indentation style as neighboring watches):

```json
    {
      "name": "Broad gym shorts M-L",
      "query": "short sport",
      "country": "ro",
      "order": "newest_first",
      "per_page": 50,
      "price_to": 120,
      "hunt_price": 70,
      "size_ids": [1739, 1740],
      "target_type": "men's gym or training shorts",
      "target_sizes": ["M", "L"],
      "notes": "Prefer technical training / gym shorts in good condition. Skip kickboxing/football kits, casual cargo, and non-gym fashion shorts unless an exceptional steal. Brand-agnostic: Nike, Adidas, UA, Decathlon/Domyos, Hummel, Craft, etc. all valid."
    },
    {
      "name": "Broad training shorts M-L",
      "query": "pantaloni scurti sport",
      "country": "ro",
      "order": "newest_first",
      "per_page": 50,
      "price_to": 120,
      "hunt_price": 70,
      "size_ids": [1739, 1740],
      "target_type": "men's gym or training shorts",
      "target_sizes": ["M", "L"],
      "notes": "Prefer technical training / gym shorts in good condition. Skip kickboxing/football kits, casual cargo, and non-gym fashion shorts unless an exceptional steal. Brand-agnostic: Nike, Adidas, UA, Decathlon/Domyos, Hummel, Craft, etc. all valid."
    },
    {
      "name": "Broad gym short EN M-L",
      "query": "gym shorts",
      "country": "ro",
      "order": "newest_first",
      "per_page": 50,
      "price_to": 120,
      "hunt_price": 70,
      "size_ids": [1739, 1740],
      "target_type": "men's gym or training shorts",
      "target_sizes": ["M", "L"],
      "notes": "Prefer technical training / gym shorts in good condition. Skip kickboxing/football kits, casual cargo, and non-gym fashion shorts unless an exceptional steal. Brand-agnostic: Nike, Adidas, UA, Decathlon/Domyos, Hummel, Craft, etc. all valid."
    },
    {
      "name": "Broad dri-fit shorts M-L",
      "query": "dri fit short",
      "country": "ro",
      "order": "newest_first",
      "per_page": 50,
      "price_to": 120,
      "hunt_price": 70,
      "size_ids": [1739, 1740],
      "target_type": "men's gym or training shorts",
      "target_sizes": ["M", "L"],
      "notes": "Prefer technical training / gym shorts in good condition. Skip kickboxing/football kits, casual cargo, and non-gym fashion shorts unless an exceptional steal. Brand-agnostic: Nike, Adidas, UA, Decathlon/Domyos, Hummel, Craft, etc. all valid."
    },
```

- [ ] **Step 3: Insert the eight gym bundle seeds immediately after the broad watches**

```json
    {
      "name": "Gym seed H&M Sport M-L",
      "query": "h&m sport",
      "country": "ro",
      "order": "newest_first",
      "per_page": 50,
      "price_to": 80,
      "hunt_price": 50,
      "bundle_hunt": true,
      "size_ids": [1739, 1740],
      "target_type": "men's gym clothing suitable for building a multi-item bundle",
      "target_sizes": ["M", "L"],
      "notes": "Seeds only — never solo-alert. Prefer sellers with several useful M/L gym pieces (shorts, tees, training pants). Individual 20–50 RON items are weak alone; same-seller multi-piece + one shipping is the goal. bundle_hunt seed."
    },
    {
      "name": "Gym seed Nike Dri-Fit M-L",
      "query": "nike dri fit",
      "country": "ro",
      "order": "newest_first",
      "per_page": 50,
      "price_to": 80,
      "hunt_price": 50,
      "bundle_hunt": true,
      "size_ids": [1739, 1740],
      "target_type": "men's gym clothing suitable for building a multi-item bundle",
      "target_sizes": ["M", "L"],
      "notes": "Seeds only — never solo-alert. Prefer sellers with several useful M/L gym pieces (shorts, tees, training pants). Individual 20–50 RON items are weak alone; same-seller multi-piece + one shipping is the goal. bundle_hunt seed."
    },
    {
      "name": "Gym seed Adidas training M-L",
      "query": "adidas training",
      "country": "ro",
      "order": "newest_first",
      "per_page": 50,
      "price_to": 80,
      "hunt_price": 50,
      "bundle_hunt": true,
      "size_ids": [1739, 1740],
      "target_type": "men's gym clothing suitable for building a multi-item bundle",
      "target_sizes": ["M", "L"],
      "notes": "Seeds only — never solo-alert. Prefer sellers with several useful M/L gym pieces (shorts, tees, training pants). Individual 20–50 RON items are weak alone; same-seller multi-piece + one shipping is the goal. bundle_hunt seed."
    },
    {
      "name": "Gym seed Under Armour M-L",
      "query": "under armour",
      "country": "ro",
      "order": "newest_first",
      "per_page": 50,
      "price_to": 80,
      "hunt_price": 50,
      "bundle_hunt": true,
      "size_ids": [1739, 1740],
      "target_type": "men's gym clothing suitable for building a multi-item bundle",
      "target_sizes": ["M", "L"],
      "notes": "Seeds only — never solo-alert. Prefer sellers with several useful M/L gym pieces (shorts, tees, training pants). Individual 20–50 RON items are weak alone; same-seller multi-piece + one shipping is the goal. bundle_hunt seed."
    },
    {
      "name": "Gym seed Domyos M-L",
      "query": "domyos",
      "country": "ro",
      "order": "newest_first",
      "per_page": 50,
      "price_to": 80,
      "hunt_price": 50,
      "bundle_hunt": true,
      "size_ids": [1739, 1740],
      "target_type": "men's gym clothing suitable for building a multi-item bundle",
      "target_sizes": ["M", "L"],
      "notes": "Seeds only — never solo-alert. Prefer sellers with several useful M/L gym pieces (shorts, tees, training pants). Individual 20–50 RON items are weak alone; same-seller multi-piece + one shipping is the goal. bundle_hunt seed."
    },
    {
      "name": "Gym seed Hummel M-L",
      "query": "hummel",
      "country": "ro",
      "order": "newest_first",
      "per_page": 50,
      "price_to": 80,
      "hunt_price": 50,
      "bundle_hunt": true,
      "size_ids": [1739, 1740],
      "target_type": "men's gym clothing suitable for building a multi-item bundle",
      "target_sizes": ["M", "L"],
      "notes": "Seeds only — never solo-alert. Prefer sellers with several useful M/L gym pieces (shorts, tees, training pants). Individual 20–50 RON items are weak alone; same-seller multi-piece + one shipping is the goal. bundle_hunt seed."
    },
    {
      "name": "Gym seed Craft M-L",
      "query": "craft",
      "country": "ro",
      "order": "newest_first",
      "per_page": 50,
      "price_to": 80,
      "hunt_price": 50,
      "bundle_hunt": true,
      "size_ids": [1739, 1740],
      "target_type": "men's gym clothing suitable for building a multi-item bundle",
      "target_sizes": ["M", "L"],
      "notes": "Seeds only — never solo-alert. Prefer sellers with several useful M/L gym pieces (shorts, tees, training pants). Individual 20–50 RON items are weak alone; same-seller multi-piece + one shipping is the goal. bundle_hunt seed."
    },
    {
      "name": "Gym seed short sport M-L",
      "query": "short sport",
      "country": "ro",
      "order": "newest_first",
      "per_page": 50,
      "price_to": 80,
      "hunt_price": 50,
      "bundle_hunt": true,
      "size_ids": [1739, 1740],
      "target_type": "men's gym clothing suitable for building a multi-item bundle",
      "target_sizes": ["M", "L"],
      "notes": "Seeds only — never solo-alert. Prefer sellers with several useful M/L gym pieces (shorts, tees, training pants). Individual 20–50 RON items are weak alone; same-seller multi-piece + one shipping is the goal. bundle_hunt seed."
    },
```

- [ ] **Step 4: Validate JSON parses**

Run:

```bash
cd /home/rolki/projects/vinted-stuffs && python3 -c "
import json
from pathlib import Path
cfg = json.loads(Path('scripts/config.json').read_text())
names = [w['name'] for w in cfg['watches']]
assert 'Gym bundle seeds M-L' not in names
broad = [n for n in names if n.startswith('Broad ')]
seeds = [n for n in names if n.startswith('Gym seed ')]
assert len(broad) == 4, broad
assert len(seeds) == 8, seeds
for w in cfg['watches']:
    if w['name'] in broad or w['name'] in seeds:
        assert w.get('size_ids') == [1739, 1740], w['name']
        assert w.get('target_sizes') == ['M', 'L'], w['name']
        assert w.get('country') == 'ro', w['name']
    if w['name'] in seeds:
        assert w.get('bundle_hunt') is True, w['name']
    if w['name'] in broad:
        assert not w.get('bundle_hunt'), w['name']
print('ok', len(cfg['watches']), 'watches')
"
```

Expected: `ok <N> watches` with no AssertionError.

- [ ] **Step 5: Commit** (only if the user asked to commit)

```bash
git add scripts/config.json
git commit -m "$(cat <<'EOF'
Add broad gym-shorts watches and multi-brand gym bundle seeds.

EOF
)"
```

---

### Task 2: Prefer shorts in premium gym watch notes

**Files:**
- Modify: `scripts/config.json` (premium gym watches only)

**Interfaces:**
- Consumes: watches named Lululemon … 2XU (and Saysky / Falke ESS if present in the gym block)
- Produces: same queries/prices; updated `target_type` and `notes` preferring shorts

- [ ] **Step 1: Update each premium gym watch’s `target_type` and `notes`**

For every watch in this name set:

- `Lululemon gym M-L`
- `Ten Thousand gym M-L`
- `Rhone gym M-L`
- `Vuori gym M-L`
- `Tracksmith gym M-L`
- `Saysky running M-L`
- `Falke ESS M-L`
- `Craft ADV M-L`
- `Odlo technical M-L`
- `GOREWEAR M-L`
- `2XU M-L`

Set `target_type` to include shorts first, e.g.:

```text
men's gym or training clothing (shorts preferred, then tees/pants)
```

Prefix or rewrite `notes` so the first sentence is:

```text
Prioritise shorts when present; then technical tees and training pants.
```

Keep brand-specific model hints that already exist (Pace Breaker, Interval, Kore, etc.) after that sentence. Do not change `query`, `price_to`, `hunt_price`, or `per_page`.

- [ ] **Step 2: Re-validate JSON**

```bash
cd /home/rolki/projects/vinted-stuffs && python3 -c "import json; json.load(open('scripts/config.json')); print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit** (only if the user asked to commit)

```bash
git add scripts/config.json
git commit -m "$(cat <<'EOF'
Prefer shorts in premium gym hunt scoring notes.

EOF
)"
```

---

### Task 3: Sweep-only config file

**Files:**
- Create: `scripts/config.gym-shorts-sweep.json`

**Interfaces:**
- Consumes: top-level keys from `scripts/config.json`; the 4 broad + 8 seed watches from Task 1
- Produces: loadable config for `VINTED_CONFIG=scripts/config.gym-shorts-sweep.json FULL_SWEEP=1`

- [ ] **Step 1: Create the sweep config**

Copy from `scripts/config.json`:

- All top-level keys except `"watches"` (`min_deal_score`, `require_hunt_fit`, `keep_value_bands`, `max_keeps_per_run`, `max_bundles_per_run`, `max_new_items_per_watch`, `solo_floor_clothing_ron`, `bundle_extra_min_score`, `closet_crawl_limit`, `closet_crawl_max_sellers`, `checkout_extra_ron`, `checkout_fees`, `value_haul`)
- `"watches"`: only the 4 `Broad *` and 8 `Gym seed *` objects (exact same objects as in main config)

Do not include sneakers, knitwear, maternity, or premium brand watches.

Practical approach:

```bash
cd /home/rolki/projects/vinted-stuffs && python3 <<'PY'
import json
from pathlib import Path
src = json.loads(Path("scripts/config.json").read_text())
keep = []
for w in src["watches"]:
    n = w["name"]
    if n.startswith("Broad ") or n.startswith("Gym seed "):
        keep.append(w)
assert len(keep) == 12, [w["name"] for w in keep]
out = {k: v for k, v in src.items() if k != "watches"}
out["watches"] = keep
Path("scripts/config.gym-shorts-sweep.json").write_text(
    json.dumps(out, indent=2, ensure_ascii=False) + "\n"
)
print("wrote", len(keep), "watches")
PY
```

- [ ] **Step 2: Validate sweep config**

```bash
cd /home/rolki/projects/vinted-stuffs && python3 -c "
import json
from pathlib import Path
sweep = json.loads(Path('scripts/config.gym-shorts-sweep.json').read_text())
names = [w['name'] for w in sweep['watches']]
assert len(names) == 12
assert all(n.startswith('Broad ') or n.startswith('Gym seed ') for n in names)
assert sweep.get('max_new_items_per_watch') == 15
print('sweep ok', names)
"
```

Expected: `sweep ok` followed by the 12 names.

- [ ] **Step 3: Commit** (only if the user asked to commit)

```bash
git add scripts/config.gym-shorts-sweep.json
git commit -m "$(cat <<'EOF'
Add gym-shorts FULL_SWEEP config for one-time broad coverage.

EOF
)"
```

---

### Task 4: One-time FULL_SWEEP run (manual / ops)

**Files:**
- None (runtime only)
- Reads: `scripts/config.gym-shorts-sweep.json`
- Writes: `data/seen_listings.json`, scored store / alerts as usual

**Interfaces:**
- Consumes: env `VINTED_CONFIG`, `FULL_SWEEP=1`, plus existing API keys the bot already needs
- Produces: scored broad shorts + indexed gym seeds; `seen_keys` for those hunt names

- [ ] **Step 1: Confirm credentials**

Ensure the same secrets used for a normal bot run are available (`AI_GATEWAY` / Gemini / Vinted bootstrap as already configured). Do not invent new env vars.

- [ ] **Step 2: Run the sweep**

```bash
cd /home/rolki/projects/vinted-stuffs && \
  VINTED_CONFIG=scripts/config.gym-shorts-sweep.json FULL_SWEEP=1 \
  uv run python scripts/vinted_bot.py
```

Expected stderr includes `FULL_SWEEP: paginate every hunt…` and per-hunt lines for each Broad / Gym seed watch. Expect higher LLM cost and longer runtime (up to ~400 items per watch uncapped by the 15 limit).

- [ ] **Step 3: Sanity-check results**

After the run, confirm at least one of:

- New rows / alerts for brand-agnostic shorts (Nike/Adidas/UA/Domyos/etc.), or
- Gym seed closet / value-haul activity in logs

Then resume normal cron / manual runs **without** `VINTED_CONFIG` override and **without** `FULL_SWEEP` (default `scripts/config.json`).

- [ ] **Step 4: Do not commit `data/` runtime artifacts** unless the user explicitly wants seen-state committed.

---

## Spec coverage self-check

| Spec requirement | Task |
|---|---|
| 4 broad shorts watches + size_ids | Task 1 |
| 8 gym bundle seeds replacing H&M-only seed | Task 1 |
| Premium gym notes prefer shorts | Task 2 |
| `config.gym-shorts-sweep.json` | Task 3 |
| One-time `FULL_SWEEP` with sweep config | Task 4 |
| No Python / no category_id / no sneaker·knit·maternity edits | Global constraints + Task 1–3 scope |

## Placeholder scan

None intentional. Commit steps are gated on explicit user request (repo commit rule).
