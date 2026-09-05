# Bundle opportunity dashboard — Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox syntax.

**Goal:** Persist fee-gated same-seller gym/maternity closets as `near_haul` (dashboard) or `value_haul` (alert), so the live Bundles tab fills with wardrobe opportunities.

**Architecture:** After closet prefilter + fee gate, always write a bundle row. LLM steal/hunt → `value_haul` + ntfy; otherwise → `near_haul`. Dashboard badges distinguish kinds.

**Tech Stack:** Python bot (`value_haul.py`, `vinted_bot.py`), JSON data files, static dashboard JS/CSS.

## Global Constraints

- Do not relax premium solo keep rules.
- Near hauls never ntfy.
- Closet crawl uses wardrobe API (already fixed in CLI fork).

---

### Task 1: near_haul helpers + merge

- [ ] Tests for `near_haul_record` and `merge_bundle_rows` (supersede near→value)
- [ ] Implement in `scripts/value_haul.py`
- [ ] Config defaults: `max_near_hauls_per_run`, `max_opportunity_bundles`

### Task 2: bot loop

- [ ] After gate: LLM up to `max_value_hauls_per_run`; always persist value or near
- [ ] Remaining gated sellers → near without LLM up to `max_near_hauls_per_run`
- [ ] `save_bundles` via merge; last_run counts `near_hauls`

### Task 3: dashboard

- [ ] Badges + empty copy for near haul
- [ ] CSS `.pill.near`

### Task 4: verify live

- [ ] Focused gym+maternity seed hunt; push `best_bundles.json`
- [ ] Confirm live API has multiple opportunity rows with sellers
