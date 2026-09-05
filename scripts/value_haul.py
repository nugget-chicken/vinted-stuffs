"""Value-haul helpers: prefilter, gate, scoring payload (no I/O)."""

from __future__ import annotations

GYM_TOKENS = (
    "sport", "training", "gym", "running", "workout", "fitness",
    "nike", "adidas", "lululemon", "under armour", "underarmour",
    "puma", "reebok", "craft", "decathlon", "h&m", "hm move", "hm sport",
    "ten thousand", "compression", "dry-fit", "dri-fit", "tech tee",
)


def value_haul_config(config: dict) -> dict:
    defaults = {
        "min_items": 3,
        "min_items_steal": 2,
        "steal_max_delivered_per_item_ron": 20,
        "strong_max_delivered_per_item_ron": 30,
        "excellent_max_delivered_per_item_ron": 25,
        "closet_crawl_limit": 36,
        "min_deal_score": 8,
        "keep_value_bands": ["steal", "hunt"],
        "max_candidates_to_score": 12,
        "max_value_hauls_per_run": 3,
    }
    merged = dict(defaults)
    merged.update(config.get("value_haul") or {})
    return merged


def _listing_amount(item: dict):
    raw = (item.get("price") or {}).get("amount")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def size_matches(item: dict, target_sizes: list[str]) -> bool:
    if not target_sizes:
        return True
    raw = f"{item.get('size_title') or ''} {item.get('title') or ''}".upper()
    targets = [t.upper() for t in target_sizes]
    for t in targets:
        if t in raw.replace(" ", ""):
            return True
        # token-ish: " M ", "M/", "/M", "M-L"
        for sep in (" ", "/", "-", ","):
            if f"{sep}{t}{sep}" in f" {raw.replace('-', '/')} ":
                return True
            if raw.startswith(t + sep) or raw.endswith(sep + t):
                return True
    # ambiguous M/L style already covered by membership of either letter
    compact = raw.replace(" ", "")
    if "/" in compact or "-" in compact:
        parts = compact.replace("-", "/").split("/")
        if any(p.strip() in targets for p in parts):
            return True
    return False


def looks_like_gymwear(item: dict, watch: dict) -> bool:
    blob = f"{item.get('title') or ''} {item.get('brand_title') or ''}".lower()
    if any(tok in blob for tok in GYM_TOKENS):
        return True
    notes = (watch.get("notes") or "").lower()
    for word in notes.replace(",", " ").split():
        if len(word) >= 4 and word in blob:
            return True
    target = (watch.get("target_type") or "").lower()
    if "gym" in target or "training" in target or "sport" in target:
        if any(w in blob for w in ("tee", "t-shirt", "short", "legging", "hoodie", "tank", "top", "póló", "tricou")):
            return True
    return False


def rough_delivered_per_item(items: list, checkout_extra: float) -> float | None:
    if not items:
        return None
    total = 0.0
    for it in items:
        amt = _listing_amount(it)
        if amt is None:
            return None
        total += amt
    return (total + float(checkout_extra)) / len(items)


def passes_value_haul_gate(n: int, rough_per_item: float | None, vh: dict) -> bool:
    min_items = int(vh.get("min_items", 3))
    min_steal = int(vh.get("min_items_steal", 2))
    steal_cap = float(vh.get("steal_max_delivered_per_item_ron", 20))
    if n >= min_items:
        return True
    if n >= min_steal and rough_per_item is not None and rough_per_item <= steal_cap:
        return True
    return False


def prefilter_candidates(items: list, watch: dict, config: dict) -> list:
    vh = value_haul_config(config)
    sizes = watch.get("target_sizes") or []
    scored = []
    for it in items:
        if _listing_amount(it) is None:
            continue
        if not size_matches(it, sizes):
            continue
        if not looks_like_gymwear(it, watch):
            continue
        title = (it.get("title") or "").lower()
        brand = (it.get("brand_title") or "").lower()
        fit = sum(1 for tok in GYM_TOKENS if tok in f"{title} {brand}")
        price = _listing_amount(it) or 9999
        scored.append((fit, -price, it))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    cap = int(vh.get("max_candidates_to_score", 12))
    return [t[2] for t in scored[:cap]]
