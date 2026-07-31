#!/usr/bin/env python3
"""
Vinted deal-bot.
 
For each configured "watch" (a saved search), this:
  1. calls ScrapeBadger's Vinted search endpoint
  2. drops any listing we've already processed (dedup state in data/seen_listings.json)
  3. sends the new listings to Claude in one batch to score deal quality + scam risk
  4. pushes a ntfy alert for anything that clears the watch's threshold
  5. commits the updated dedup state back (handled by the GitHub Actions workflow)
 
Config lives in scripts/config.json — see that file for the schema.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
 
import requests
from anthropic import Anthropic
 
STATE_PATH = Path("data/seen_listings.json")
CONFIG_PATH = Path("scripts/config.json")
SCRAPEBADGER_BASE = "https://scrapebadger.com/v1"
CLAUDE_MODEL = "claude-haiku-4-5-20251001"  # cheap + fast, good enough for scoring
 
 
# ---------- state ----------
 
def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"seen_ids": [], "run_count": 0, "last_run": None}
 
 
def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["seen_ids"] = state["seen_ids"][-5000:]  # don't let this grow forever
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n")
 
 
def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())
 
 
# ---------- ScrapeBadger ----------
 
def search_vinted(api_key: str, watch: dict) -> list:
    params = {
        "query": watch["query"],
        "market": watch.get("market", "fr"),
        "per_page": watch.get("per_page", 48),
        "order": watch.get("order", "newest_first"),
    }
    for key in ("price_from", "price_to", "brand_ids", "color_ids", "status_ids"):
        if key in watch:
            params[key] = watch[key]
 
    resp = requests.get(
        f"{SCRAPEBADGER_BASE}/vinted/search",
        headers={"x-api-key": api_key},
        params=params,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("items", [])
 
 
# ---------- Claude scoring ----------
 
SCORING_PROMPT = """You are screening second-hand Vinted listings for a buyer \
looking for good deals. For each listing below, score it and return ONLY a \
JSON array (no prose, no markdown fences) with one object per listing:
 
  {{"id": <item id>, "deal_score": <1-10>, "scam_risk": "low"|"medium"|"high", "reason": "<one short sentence>"}}
 
deal_score: how good a price this is for the brand/item/condition (10 = excellent deal, 1 = overpriced).
scam_risk: based only on the signals given below (seller reputation, favourite \
count, price relative to what similar items usually go for, whether the price \
seems implausibly low for the item). You are only seeing a search-result \
summary, not the full listing description or photos, so default to "medium" \
when signals are ambiguous rather than guessing "low".
 
Buyer is searching for "{query}", budget up to {price_to} {currency}.
 
Listings:
{listings_json}
"""
 
 
def score_with_claude(client: Anthropic, watch: dict, items: list) -> list:
    listings_json = json.dumps(
        [
            {
                "id": it["id"],
                "title": it["title"],
                "price": it["price"],
                "currency": it["currency"],
                "brand": it.get("brand_title"),
                "size": it.get("size_title"),
                "favourite_count": it.get("favourite_count"),
                "seller": it.get("user", {}).get("login"),
                "seller_reputation": it.get("user", {}).get("feedback_reputation"),
            }
            for it in items
        ],
        ensure_ascii=False,
    )
    prompt = SCORING_PROMPT.format(
        query=watch["query"],
        price_to=watch.get("price_to", "any"),
        currency=items[0]["currency"] if items else "EUR",
        listings_json=listings_json,
    )
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"Could not parse Claude response:\n{raw}", file=sys.stderr)
        return []
 
 
# ---------- ntfy ----------
 
def send_ntfy(topic: str, item: dict, score: dict) -> None:
    title = f"{score['deal_score']}/10 deal: {item['title'][:60]}"
    body = (
        f"{item['price']} {item['currency']} - {item.get('brand_title') or 'no brand'} "
        f"- scam risk: {score['scam_risk']}\n{score['reason']}"
    )
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers={
            "Title": title,
            "Click": item["url"],
            "Priority": "high" if score["deal_score"] >= 9 else "default",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.URLError as e:
        print(f"ntfy send failed: {e}", file=sys.stderr)
 
 
# ---------- main ----------
 
def main() -> None:
    scrapebadger_key = os.environ.get("SCRAPEBADGER_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    ntfy_topic = os.environ.get("NTFY_TOPIC", "")
    missing = [
        n for n, v in [
            ("SCRAPEBADGER_API_KEY", scrapebadger_key),
            ("ANTHROPIC_API_KEY", anthropic_key),
            ("NTFY_TOPIC", ntfy_topic),
        ] if not v
    ]
    if missing:
        print(f"Missing required secrets: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
 
    config = load_config()
    state = load_state()
    seen = set(state["seen_ids"])
    client = Anthropic(api_key=anthropic_key)
 
    alerts_sent = 0
    for watch in config["watches"]:
        try:
            items = search_vinted(scrapebadger_key, watch)
        except requests.RequestException as e:
            print(f"Search failed for watch '{watch['name']}': {e}", file=sys.stderr)
            continue
 
        new_items = [it for it in items if str(it["id"]) not in seen]
        new_items = new_items[: config.get("max_new_items_per_run", 20)]
        if not new_items:
            continue
 
        scores = score_with_claude(client, watch, new_items)
        scores_by_id = {s["id"]: s for s in scores}
 
        for item in new_items:
            seen.add(str(item["id"]))
            score = scores_by_id.get(item["id"])
            if not score:
                continue
            if (
                score["deal_score"] >= watch.get("min_deal_score", 7)
                and score["scam_risk"] != "high"
            ):
                send_ntfy(ntfy_topic, item, score)
                alerts_sent += 1
 
    state["seen_ids"] = list(seen)
    state["run_count"] += 1
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["last_alerts_sent"] = alerts_sent
    save_state(state)
    print(f"Run complete. {alerts_sent} alert(s) sent.")
 
 
if __name__ == "__main__":
    main()
