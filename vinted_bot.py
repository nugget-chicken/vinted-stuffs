"""
Vinted Deal & Scam Watcher
---------------------------
Checks Vinted for a broad set of resellable electronics, flags listings
that are meaningfully cheaper than similar current listings, filters out
accessories/games/broken units, flags anything that looks like a scam,
and sends a push notification via ntfy.sh for whatever's left.
 
Run locally with:
    python vinted_bot.py
 
...but the point is to let GitHub Actions run it on a schedule for you.
See the README for setup steps.
"""
 
import json
import re
import statistics
from pathlib import Path
 
import requests
 
# ---------------------------------------------------------------------------
# 1. SETTINGS
# ---------------------------------------------------------------------------
 
VINTED_DOMAIN = "www.vinted.com"   # US site — change to www.vinted.co.uk etc if needed
CURRENCY_SYMBOL = "$"
PER_PAGE = 40
 
# Phrases that disqualify ANY listing — accessories, games, broken units.
# Uses phrases like "case for" rather than bare "case" so it doesn't
# reject real listings that just mention a bundled case/charger.
ELECTRONICS_EXCLUDES = [
    "case only", "case for", "cover for", "screen protector",
    "charger only", "charger for", "cable only", "adapter only",
    "empty box", "box only", "manual only", "sim card only",
    "for parts", "spares", "broken", "cracked", "faulty",
    "game", "games", "disc", "disk",
]
 
# Broad set of resellable electronics categories. No price cap needed —
# "good deal" is judged relative to other current listings for the same
# search (see DEAL_DISCOUNT_THRESHOLD below), not a fixed number.
# Add/remove entries freely; each one is checked independently.
SEARCH_ITEMS = [
    {"label": "iPhone", "search_text": "iphone"},
    {"label": "Samsung Galaxy", "search_text": "samsung galaxy"},
    {"label": "iPad", "search_text": "ipad"},
    {"label": "MacBook", "search_text": "macbook"},
    {"label": "AirPods", "search_text": "airpods"},
    {"label": "PS4", "search_text": "ps4"},
    {"label": "PS5", "search_text": "ps5"},
    {"label": "Xbox Series", "search_text": "xbox series"},
    {"label": "Nintendo Switch", "search_text": "nintendo switch"},
]
 
# How far below the going rate counts as a "good deal" — 0.30 = 30%
# cheaper than the median of other listings that came back for that
# same search, right now. This is a same-moment comparison, not a
# comparison to historical/past-sold prices (Vinted doesn't expose that).
DEAL_DISCOUNT_THRESHOLD = 0.30
 
# A listing needs at least this many red flags to get treated as sketchy
# and skipped. Lower = stricter, but "seller has no reviews" alone is
# common for genuine new sellers too, so 1 will also cut real deals.
SCAM_FLAG_THRESHOLD = 2
 
# Locations you've personally seen tied to sketchy listings (lowercase).
SCAM_LOCATION_KEYWORDS = ["new york"]
 
# Your ntfy.sh topic — random/unguessable, it's a public service.
NTFY_TOPIC = "leo-vinted-deals-x7k2"
 
SEEN_IDS_FILE = Path(__file__).parent / "seen_ids.json"
 
PHONE_NUMBER_PATTERN = re.compile(r"(\+?\d[\d\s\-\(\)]{7,}\d)")
CONTACT_REQUEST_PHRASES = [
    "whatsapp", "telegram", "text me", "text you", "call me",
    "my number", "send your number", "message me on", "contact me at",
    "paypal friends", "venmo", "zelle",
]
 
# ---------------------------------------------------------------------------
# 2. FETCH LISTINGS FROM VINTED
# ---------------------------------------------------------------------------
 
def get_listings(search_text, price_to=""):
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    })
    session.get(f"https://{VINTED_DOMAIN}/")
 
    params = {
        "search_text": search_text,
        "order": "newest_first",
        "per_page": PER_PAGE,
    }
    if price_to:
        params["price_to"] = price_to
 
    response = session.get(
        f"https://{VINTED_DOMAIN}/api/v2/catalog/items",
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    return response.json().get("items", [])
 
 
def item_price(item):
    price = item.get("price")
    if isinstance(price, dict):
        return float(price.get("amount", 0) or 0)
    try:
        return float(price)
    except (TypeError, ValueError):
        return 0.0
 
 
def item_text(item):
    """Title + description if present (search results often only carry
    the title, not the full description)."""
    return f"{item.get('title', '')} {item.get('description', '')}".lower()
 
 
def item_location_text(item):
    parts = [
        str(item.get("city", "")),
        str(item.get("country_title", "")),
        str((item.get("user") or {}).get("city", "")),
    ]
    return " ".join(parts).lower()
 
 
# ---------------------------------------------------------------------------
# 3. FILTERS — accessory/game exclusion, optional price cap
# ---------------------------------------------------------------------------
 
def matches_target(item, search):
    """True only if this listing is a real item, not an accessory/game/
    broken unit."""
    text = item_text(item)
    excludes = search.get("exclude_keywords", ELECTRONICS_EXCLUDES)
 
    for word in excludes:
        if word in text:
            return False, f"matched exclude phrase '{word}'"
 
    price_to = search.get("price_to")
    if price_to and item_price(item) > float(price_to):
        return False, "priced above optional cap"
 
    return True, None
 
 
def is_good_deal(item, all_prices):
    if len(all_prices) < 5:
        return False  # not enough listings yet to know what "normal" is
    median_price = statistics.median(all_prices)
    if median_price == 0:
        return False
    price = item_price(item)
    discount = (median_price - price) / median_price
    return discount >= DEAL_DISCOUNT_THRESHOLD
 
 
# ---------------------------------------------------------------------------
# 4. "POSSIBLE SCAM" CHECK
# ---------------------------------------------------------------------------
 
def scam_flags(item):
    flags = []
 
    seller = item.get("user") or {}
    if seller.get("feedback_count", 0) == 0:
        flags.append("seller has no reviews")
 
    if not item.get("photo"):
        flags.append("no photo on the listing")
 
    text = item_text(item)
    if any(phrase in text for phrase in CONTACT_REQUEST_PHRASES):
        flags.append("asks to text/contact outside Vinted")
    if PHONE_NUMBER_PATTERN.search(text):
        flags.append("phone number in the listing text")
 
    location_text = item_location_text(item)
    if any(place in location_text for place in SCAM_LOCATION_KEYWORDS):
        flags.append("seller location is on your watch list")
 
    return flags
 
 
# ---------------------------------------------------------------------------
# 5. PUSH NOTIFICATION (via ntfy.sh)
# ---------------------------------------------------------------------------
 
def send_notification(title, message, url=None):
    headers = {"Title": title}
    if url:
        headers["Click"] = url
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers=headers,
        timeout=10,
    )
 
 
# ---------------------------------------------------------------------------
# 6. TRACKING WHAT WE'VE ALREADY SEEN
# ---------------------------------------------------------------------------
 
def load_seen_ids():
    if SEEN_IDS_FILE.exists():
        return set(json.loads(SEEN_IDS_FILE.read_text() or "[]"))
    return set()
 
 
def save_seen_ids(ids):
    SEEN_IDS_FILE.write_text(json.dumps(sorted(ids)))
 
 
# ---------------------------------------------------------------------------
# 7. MAIN
# ---------------------------------------------------------------------------
 
def main():
    seen_ids = load_seen_ids()
    total_checked = 0
    total_alerts = 0
 
    for search in SEARCH_ITEMS:
        label = search["label"]
        listings = get_listings(search["search_text"], search.get("price_to", ""))
 
        if not listings:
            print(f"[{label}] No listings came back — check search_text, "
                  f"or Vinted may be temporarily blocking this request.")
            continue
 
        total_checked += len(listings)
        all_prices = [item_price(item) for item in listings]
 
        for item in listings:
            item_id = str(item.get("id"))
            if not item_id or item_id in seen_ids:
                continue
            seen_ids.add(item_id)
 
            ok, _reason = matches_target(item, search)
            if not ok:
                continue
 
            if not is_good_deal(item, all_prices):
                continue
 
            flags = scam_flags(item)
            if len(flags) >= SCAM_FLAG_THRESHOLD:
                continue
 
            title = item.get("title", "Vinted listing")
            price = item_price(item)
            item_url = f"https://{VINTED_DOMAIN}/items/{item_id}"
 
            send_notification(
                title=f"{label} deal: {title}",
                message=f"{CURRENCY_SYMBOL}{price:.2f} — {title}",
                url=item_url,
            )
            total_alerts += 1
 
    save_seen_ids(seen_ids)
    print(f"Checked {total_checked} listings across {len(SEARCH_ITEMS)} "
          f"searches, sent {total_alerts} alert(s).")
 
 
if __name__ == "__main__":
    main()
