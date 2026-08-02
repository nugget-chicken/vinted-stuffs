#!/usr/bin/env python3
"""
Vinted deal-bot.
 
For each configured "watch" (a saved search), this:
  1. calls ScrapeBadger's Vinted search endpoint
  2. drops any listing we've already processed (dedup state in data/seen_listings.json)
  3. sends the new listings to Gemini in one batch to score deal quality + scam risk
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
from google import genai
from google.genai import types
 
STATE_PATH = Path("data/seen_listings.json")
CONFIG_PATH = Path("scripts/config.json")
SCRAPEBADGER_BASE = "https://scrapebadger.com/v1"
GEMINI_MODEL = "gemini-3.6-flash"  # check aistudio.google.com for the current recommended flash model name
 
 
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
        "market": watch.get("market", "us"),
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
 
 
_profile_debug_printed = False
 
 
def get_seller_profile(api_key: str, user_id, market: str) -> dict:
    """Best-effort seller profile lookup for scam-risk signal (member-since,
    feedback count). Returns {} on any failure rather than raising, since
    losing this enrichment shouldn't take down the whole run."""
    global _profile_debug_printed
    if not user_id:
        return {}
    try:
        resp = requests.get(
            f"{SCRAPEBADGER_BASE}/vinted/user",
            headers={"x-api-key": api_key},
            params={"user_id": user_id, "market": market},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if not _profile_debug_printed:
            print("DEBUG first seller profile response:", file=sys.stderr)
            print(json.dumps(data, indent=2, ensure_ascii=False), file=sys.stderr)
            _profile_debug_printed = True
        return data
    except requests.RequestException as e:
        if not _profile_debug_printed:
            print(f"Seller profile lookup failed (skipping enrichment): {e}", file=sys.stderr)
            _profile_debug_printed = True
        return {}
 
 
# ---------- Gemini scoring ----------
 
SCORING_PROMPT = """You are screening second-hand Vinted listings for a buyer \
looking for good deals. For each listing below, score it and return ONLY a \
JSON array (no prose, no markdown fences) with one object per listing:
 
  {{"id": <item id>, "deal_score": <1-10>, "scam_risk": "low"|"medium"|"high", "reason": "<one short sentence>"}}
 
deal_score: how good a price this is for the brand/item/condition (10 = excellent deal, 1 = overpriced).
scam_risk: weigh these signals in order of importance:
  1. Seller account age/history (member_since, feedback_count, item_count) — a \
brand-new account (no feedback, joined very recently, few or no other listings) \
selling an expensive electronics item is the single strongest scam signal here.
  2. Whether the price is implausibly low for the item/brand/condition (too-good-to-be-true).
  3. Low favourite count relative to how good the deal claims to be.
If seller profile data wasn't available for a listing, say so isn't a reason to \
assume "low" risk — treat missing seller history the same as a new account \
(elevated risk), not as a neutral unknown.
 
Buyer is searching for "{query}", budget up to {price_to} {currency}.
 
Listings:
{listings_json}
"""
 
 
def score_with_gemini(client: "genai.Client", watch: dict, items: list) -> list:
    listings_json = json.dumps(
        [
            {
                "id": it.get("id"),
                "title": it.get("title", ""),
                "price": (it.get("price") or {}).get("amount", "?"),
                "currency": (it.get("price") or {}).get("currency_code", ""),
                "brand": it.get("brand_title"),
                "size": it.get("size_title"),
                "condition": it.get("status"),
                "favourite_count": it.get("favourite_count"),
                "seller": it.get("user", {}).get("login") if isinstance(it.get("user"), dict) else None,
                "seller_member_since": (it.get("_profile") or {}).get("member_since")
                    or (it.get("_profile") or {}).get("created_at"),
                "seller_feedback_count": (it.get("_profile") or {}).get("feedback_count")
                    or (it.get("_profile") or {}).get("feedback_reputation"),
                "seller_item_count": (it.get("_profile") or {}).get("item_count"),
            }
            for it in items
        ],
        ensure_ascii=False,
    )
    prompt = SCORING_PROMPT.format(
        query=watch["query"],
        price_to=watch.get("price_to", "any"),
        currency=((items[0].get("price") or {}).get("currency_code", "USD") if items else "USD"),
        listings_json=listings_json,
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    raw = (response.text or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"Could not parse Gemini response:\n{raw}", file=sys.stderr)
        return []
 
 
# ---------- ntfy ----------
 
def send_ntfy(topic: str, item: dict, score: dict) -> None:
    price = (item.get("price") or {}).get("amount", "?")
    currency = (item.get("price") or {}).get("currency_code", "")
    title = f"{score['deal_score']}/10 deal: {item.get('title', '')[:60]}"
    body = (
        f"{price} {currency} - {item.get('brand_title') or 'no brand'} "
        f"- scam risk: {score['scam_risk']}\n{score['reason']}"
    )
    headers = {
        "Title": title,
        "Priority": "high" if score["deal_score"] >= 9 else "default",
    }
    url = item.get("url")
    if url:
        headers["Click"] = url
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.URLError as e:
        print(f"ntfy send failed: {e}", file=sys.stderr)
 
 
# ---------- main ----------
 
def main() -> None:
    scrapebadger_key = os.environ.get("SCRAPEBADGER_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    ntfy_topic = os.environ.get("NTFY_TOPIC", "")
    missing = [
        n for n, v in [
            ("SCRAPEBADGER_API_KEY", scrapebadger_key),
            ("GEMINI_API_KEY", gemini_key),
            ("NTFY_TOPIC", ntfy_topic),
        ] if not v
    ]
    if missing:
        print(f"Missing required secrets: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
 
    config = load_config()
    state = load_state()
    seen = set(state["seen_ids"])
    client = genai.Client(api_key=gemini_key)
 
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
 
        for item in new_items:
            user = item.get("user")
            user_id = user.get("id") if isinstance(user, dict) else None
            item["_profile"] = get_seller_profile(scrapebadger_key, user_id, watch.get("market", "us"))
 
        scores = score_with_gemini(client, watch, new_items)
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
 
