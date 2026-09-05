#!/usr/bin/env python3
"""
Vinted deal-bot.
 
For each configured "watch" (a saved search), this:
  1. searches Vinted via the vinted-mcp-cli (no ScrapeBadger)
  2. drops any listing we've already processed (dedup state in data/seen_listings.json)
  3. scores new listings (Vercel AI Gateway, then Gemini fallback) for deal + scam risk
  4. pushes a ntfy alert for anything that clears the watch's threshold
  5. commits the updated dedup state back (handled by the GitHub Actions workflow)
 
Config lives in scripts/config.json — see that file for the schema.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
 
import requests

try:
    from google import genai
    from google.genai import types
except ImportError:  # Gemini is optional when Vercel AI Gateway is configured
    genai = None
    types = None
 
STATE_PATH = Path("data/seen_listings.json")
CONFIG_PATH = Path("scripts/config.json")
REPO_ROOT = Path(__file__).resolve().parents[1]
VERCEL_GATEWAY_BASE = "https://ai-gateway.vercel.sh/v1"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-3.6-flash"
# Cheap default; override with AI_GATEWAY_MODEL (e.g. openai/gpt-4.1-mini)
AI_GATEWAY_MODEL = os.environ.get("AI_GATEWAY_MODEL") or "google/gemini-2.5-flash"
 
 
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
 
 
# ---------- vinted-mcp-cli ----------

def _vinted_argv() -> list:
    """Resolve the vinted CLI: VINTED_BIN, sibling checkout, then npx."""
    explicit = os.environ.get("VINTED_BIN")
    if explicit:
        if explicit.endswith(".js"):
            return [os.environ.get("VINTED_NODE", "node"), explicit]
        return [explicit]
    sibling = REPO_ROOT.parent / "vinted-mcp-cli" / "dist" / "cli.js"
    if sibling.exists():
        return [os.environ.get("VINTED_NODE", "node"), str(sibling)]
    return ["npx", "--yes", "@googlarz/vinted-client"]


def _vinted_json(args: list, timeout: int = 60) -> dict | list:
    cmd = _vinted_argv() + args
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"vinted CLI failed ({proc.returncode}): {err[:500]}")
    raw = proc.stdout.strip()
    if not raw:
        raise RuntimeError("vinted CLI returned empty stdout")
    return json.loads(raw)


def _country(watch: dict) -> str:
    return watch.get("country") or watch.get("market") or "ro"


def _normalize_item(raw: dict) -> dict:
    """Map CLI item shape onto the bot's internal ScrapeBadger-era fields."""
    price = raw.get("price")
    if isinstance(price, dict):
        amount = price.get("amount", "?")
        currency = price.get("currency_code") or price.get("currency") or ""
    else:
        amount = price if price is not None else "?"
        currency = raw.get("currency") or ""
    seller = raw.get("seller") or raw.get("user") or {}
    return {
        "id": raw.get("id"),
        "title": raw.get("title", ""),
        "price": {"amount": amount, "currency_code": currency},
        "brand_title": raw.get("brand") or raw.get("brand_title"),
        "size_title": raw.get("size") or raw.get("size_title"),
        "status": raw.get("condition") or raw.get("status"),
        "favourite_count": raw.get("favouriteCount") or raw.get("favourite_count") or 0,
        "url": raw.get("url"),
        "user": {
            "id": seller.get("id") if isinstance(seller, dict) else None,
            "login": (seller.get("username") or seller.get("login")) if isinstance(seller, dict) else None,
        },
    }


def search_vinted(watch: dict) -> list:
    country = _country(watch)
    args = [
        "search",
        watch["query"],
        "-c",
        country,
        "--sort",
        watch.get("order", "newest_first"),
        "-l",
        str(watch.get("per_page", 24)),
    ]
    if "price_from" in watch:
        args += ["--price-min", str(watch["price_from"])]
    if "price_to" in watch:
        args += ["--price-max", str(watch["price_to"])]
    if watch.get("brand_ids"):
        args += ["--brand-ids", ",".join(str(i) for i in watch["brand_ids"])]
    if watch.get("category_id"):
        args += ["--category-id", str(watch["category_id"])]
    if watch.get("size_ids"):
        args += ["--size-ids", ",".join(str(i) for i in watch["size_ids"])]
    if watch.get("condition"):
        cond = watch["condition"]
        args += ["--condition", ",".join(cond) if isinstance(cond, list) else str(cond)]
    data = _vinted_json(args)
    items = data.get("items", data if isinstance(data, list) else [])
    return [_normalize_item(it) for it in items if it.get("id") is not None]


_profile_debug_printed = False
_profile_consecutive_failures = 0
_profile_endpoint_disabled = False


def get_seller_profile(user_id, country: str) -> dict:
    """Best-effort seller profile for scam-risk. {} on failure; disable after repeats."""
    global _profile_debug_printed, _profile_consecutive_failures, _profile_endpoint_disabled
    if not user_id or _profile_endpoint_disabled:
        return {}
    try:
        data = _vinted_json(["seller", str(user_id), "-c", country], timeout=30)
        if not isinstance(data, dict):
            return {}
        _profile_consecutive_failures = 0
        profile = {
            "member_since": data.get("member_since")
            or data.get("created_at")
            or (data.get("raw") or {}).get("created_at"),
            "feedback_count": data.get("feedbackCount") or data.get("feedback_count"),
            "feedback_reputation": data.get("feedbackReputation") or data.get("feedback_reputation"),
            "item_count": data.get("itemCount") or data.get("item_count"),
        }
        if not _profile_debug_printed:
            print("DEBUG first seller profile:", json.dumps(profile, ensure_ascii=False), file=sys.stderr)
            _profile_debug_printed = True
        return profile
    except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        _profile_consecutive_failures += 1
        if not _profile_debug_printed:
            print(f"Seller profile lookup failed (skipping enrichment): {e}", file=sys.stderr)
            _profile_debug_printed = True
        if _profile_consecutive_failures >= 3:
            _profile_endpoint_disabled = True
            print("Seller profile lookups failing — disabling for the rest of this run.", file=sys.stderr)
        return {}
 
 
# ---------- scoring ----------
#
# Unattended cron scoring is a cheap JSON completion. Do not use the Cursor
# Agent SDK here — that burns coding-agent quota for a task that needs
# structured output, not tools. Interactive hunts stay in Cursor via /vinted.
#
# Provider order (first that has a key wins, then the next on failure):
#   1. Vercel AI Gateway  (AI_GATEWAY_API_KEY) — OpenAI-compatible, any model
#   2. Gemini             (GEMINI_API_KEY)     — leftover fallback
# ChatGPT Plus has no API. An OpenAI API key can be sent *through* the gateway
# as BYOK; a chatgpt.com subscription cannot.
 
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


def _listing_payload(items: list) -> list:
    return [
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
    ]


def _scoring_prompt(watch: dict, items: list) -> str:
    return SCORING_PROMPT.format(
        query=watch["query"],
        price_to=watch.get("price_to", "any"),
        currency=((items[0].get("price") or {}).get("currency_code", "USD") if items else "USD"),
        listings_json=json.dumps(_listing_payload(items), ensure_ascii=False),
    )


def _parse_scores(raw: str, source: str) -> list:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        print(f"Could not parse {source} response:\n{raw}", file=sys.stderr)
        return []
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("listings", "scores", "items"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
    print(f"{source} returned JSON that is not a score array:\n{raw}", file=sys.stderr)
    return []


def score_with_gateway(api_key: str, watch: dict, items: list) -> list:
    prompt = (
        _scoring_prompt(watch, items)
        + '\nWrap the array as {"listings": [ ... ]} so the response is a JSON object.'
    )
    resp = requests.post(
        f"{VERCEL_GATEWAY_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": AI_GATEWAY_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = (((resp.json().get("choices") or [{}])[0].get("message") or {}).get("content") or "")
    return _parse_scores(content, "AI Gateway")


def score_with_gemini(client, watch: dict, items: list) -> list:
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=_scoring_prompt(watch, items),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    return _parse_scores(response.text or "", "Gemini")


def score_listings(watch: dict, items: list, gateway_key: str, gemini_client) -> list:
    errors = []
    if gateway_key:
        try:
            scores = score_with_gateway(gateway_key, watch, items)
            if scores:
                print(f"Scored {len(scores)} listing(s) via Vercel AI Gateway ({AI_GATEWAY_MODEL})", file=sys.stderr)
                return scores
            errors.append("AI Gateway returned no parseable scores")
        except requests.RequestException as e:
            errors.append(f"AI Gateway failed: {e}")
            print(errors[-1], file=sys.stderr)
    if gemini_client is not None:
        try:
            scores = score_with_gemini(gemini_client, watch, items)
            if scores:
                print(f"Scored {len(scores)} listing(s) via Gemini ({GEMINI_MODEL})", file=sys.stderr)
                return scores
            errors.append("Gemini returned no parseable scores")
        except Exception as e:
            errors.append(f"Gemini failed: {e}")
            print(errors[-1], file=sys.stderr)
    print("All scorers failed: " + "; ".join(errors or ["no scorer configured"]), file=sys.stderr)
    return []
 
 
# ---------- ntfy ----------
 
def _header_safe(text: str) -> str:
    """HTTP headers are Latin-1 only. Listing titles often contain en dashes,
    em dashes, or curly quotes that aren't — swap common ones for ASCII
    equivalents, then drop anything else that still won't fit rather than
    crashing the request."""
    replacements = {
        "\u2013": "-", "\u2014": "-",  # en dash, em dash
        "\u2018": "'", "\u2019": "'",  # curly single quotes
        "\u201c": '"', "\u201d": '"',  # curly double quotes
        "\u2026": "...",  # ellipsis
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", errors="ignore").decode("latin-1")
 
 
def send_ntfy(topic: str, item: dict, score: dict) -> None:
    price = (item.get("price") or {}).get("amount", "?")
    currency = (item.get("price") or {}).get("currency_code", "")
    title = _header_safe(f"{score['deal_score']}/10 deal: {item.get('title', '')[:60]}")
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
        headers["Click"] = _header_safe(url)
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
    gateway_key = os.environ.get("AI_GATEWAY_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    ntfy_topic = os.environ.get("NTFY_TOPIC", "")
    test_mode = os.environ.get("SKIP_SCORING", "").strip().lower() in ("1", "true", "yes")
 
    required = [("NTFY_TOPIC", ntfy_topic)]
    if not test_mode and not gateway_key and not gemini_key:
        print(
            "Missing a scorer: set AI_GATEWAY_API_KEY (preferred) or GEMINI_API_KEY.",
            file=sys.stderr,
        )
        sys.exit(1)
    missing = [n for n, v in required if not v]
    if missing:
        print(f"Missing required secrets: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
 
    if test_mode:
        print("TEST MODE: skipping LLM scoring, fake-scoring every new listing as a pass", file=sys.stderr)
 
    config = load_config()
    state = load_state()
    seen = set(state["seen_ids"])
    gemini_client = None
    if not test_mode and gemini_key:
        if genai is None:
            print("GEMINI_API_KEY is set but google-genai is not installed; Gateway-only.", file=sys.stderr)
        else:
            gemini_client = genai.Client(api_key=gemini_key)
 
    alerts_sent = 0
    for i, watch in enumerate(config["watches"]):
        if i > 0:
            time.sleep(1.5)  # small pacing gap between watches to avoid bursting the rate limit
        try:
            items = search_vinted(watch)
        except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
            print(f"Search failed for watch '{watch['name']}': {e}", file=sys.stderr)
            continue
 
        new_items = [it for it in items if str(it["id"]) not in seen]
        new_items = new_items[: config.get("max_new_items_per_run", 20)]
        if not new_items:
            continue
 
        for item in new_items:
            user = item.get("user")
            user_id = user.get("id") if isinstance(user, dict) else None
            item["_profile"] = get_seller_profile(user_id, _country(watch))
 
        if test_mode:
            scores = [
                {"id": item.get("id"), "deal_score": 10, "scam_risk": "low", "reason": "TEST MODE - scoring skipped"}
                for item in new_items
            ]
        else:
            scores = score_listings(watch, new_items, gateway_key, gemini_client)
        scores_by_id = {str(s["id"]): s for s in scores if s.get("id") is not None}
 
        for item in new_items:
            seen.add(str(item["id"]))
            score = scores_by_id.get(str(item["id"]))
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
 
