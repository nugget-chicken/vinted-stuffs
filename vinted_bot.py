"""
Vinted Deal & Scam Watcher
---------------------------
Checks Vinted for specific console/phone models at set price ceilings
(matching a resale price guide), filters out accessories/games/discs,
flags anything that looks like a scam, and sends a push notification
via ntfy.sh for whatever's left.
 
Run locally with:
    python vinted_bot.py
 
...but the point is to let GitHub Actions run it on a schedule for you.
See the README for setup steps.
"""
 
import json
import re
from pathlib import Path
 
import requests
 
# ---------------------------------------------------------------------------
# 1. SETTINGS
# ---------------------------------------------------------------------------
 
VINTED_DOMAIN = "www.vinted.com"   # US site — change to www.vinted.co.uk etc if needed
CURRENCY_SYMBOL = "$"
PER_PAGE = 40
 
# Phrases that disqualify a listing for ANY console search — accessories,
# games, discs, broken units. Uses phrases like "case for" rather than
# bare "case" so it doesn't reject real listings that just mention a
# bundled controller/case/charger (which is normal and fine).
CONSOLE_ACCESSORY_EXCLUDES = [
    "game", "games", "disc", "disk", "cd",
    "controller only", "just controller", "controller for",
    "case only", "case for", "skin for", "cover for",
    "screen protector", "charger only", "charger for",
    "cable only", "headset only", "empty box", "box only",
    "manual only", "broken", "faulty", "for parts", "spares",
]
 
# Same idea, for phones.
PHONE_EXCLUDES = [
    "case only", "case for", "cover for", "screen protector",
    "charger only", "charger for", "cable only", "adapter only",
    "empty box", "box only", "sim card only",
    "for parts", "spares", "broken", "cracked", "faulty",
]
PHONE_REQUIRES = ["unlocked"]  # at least one of these must appear in the text
 
# Every entry is one specific thing to hunt for. price_to is a HARD
# ceiling — Vinted itself won't return listings above it, so anything
# that comes back and clears the filters below already fits the target
# price from Jack's list.
SEARCH_ITEMS = [
    {"label": "PS4 Slim 1TB", "search_text": "ps4 slim 1tb", "price_to": "55",
     "exclude_keywords": CONSOLE_ACCESSORY_EXCLUDES},
    {"label": "PS4 Slim 500GB", "search_text": "ps4 slim 500gb", "price_to": "40",
     "exclude_keywords": CONSOLE_ACCESSORY_EXCLUDES},
    {"label": "PS4 Pro 1TB", "search_text": "ps4 pro 1tb", "price_to": "65",
     "exclude_keywords": CONSOLE_ACCESSORY_EXCLUDES},
    {"label": "Nintendo Switch", "search_text": "nintendo switch", "price_to": "60",
     "exclude_keywords": CONSOLE_ACCESSORY_EXCLUDES + ["switch 2", "lite"]},
    {"label": "Xbox Series X 1TB", "search_text": "xbox series x 1tb", "price_to": "270",
     "exclude_keywords": CONSOLE_ACCESSORY_EXCLUDES},
    {"label": "Xbox Series S 1TB", "search_text": "xbox series s 1tb", "price_to": "140",
     "exclude_keywords": CONSOLE_ACCESSORY_EXCLUDES},
    {"label": "Xbox Series S 500GB", "search_text": "xbox series s 500gb", "price_to": "120",
     "exclude_keywords": CONSOLE_ACCESSORY_EXCLUDES},
    {"label": "iPhone 13", "search_text": "iphone 13", "price_to": "100",
     "exclude_keywords": PHONE_EXCLUDES, "require_keywords": PHONE_REQUIRES,
     "min_battery_percent": 75},
    {"label": "iPhone 14", "search_text": "iphone 14", "price_to": "175",
     "exclude_keywords": PHONE_EXCLUDES, "require_keywords": PHONE_REQUIRES,
     "min_battery_percent": 75},
    {"label": "iPhone 15", "search_text": "iphone 15", "price_to": "250",
     "exclude_keywords": PHONE_EXCLUDES, "require_keywords": PHONE_REQUIRES,
     "min_battery_percent": 75},
    {"label": "iPhone 16", "search_text": "iphone 16", "price_to": "300",
     "exclude_keywords": PHONE_EXCLUDES, "require_keywords": PHONE_REQUIRES,
     "min_battery_percent": 75},
]
 
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
BATTERY_PATTERN = re.compile(r"batter\w*[^\d]{0,15}(\d{2,3})\s*%")
 
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
    """Everything text-based we can search: title + description if present.
    Note: Vinted's search-results endpoint often only includes the title,
    not the full description — so battery-percent and phrase checks may
    miss things that are only mentioned in the full listing description."""
    return f"{item.get('title', '')} {item.get('description', '')}".lower()
 
 
def item_location_text(item):
    parts = [
        str(item.get("city", "")),
        str(item.get("country_title", "")),
        str((item.get("user") or {}).get("city", "")),
    ]
    return " ".join(parts).lower()
 
 
# ---------------------------------------------------------------------------
# 3. FILTERS — accessory/game exclusion, requirements, battery, price
# ---------------------------------------------------------------------------
 
def matches_target(item, search):
    """True only if this listing is actually the thing we're hunting for —
    not an accessory, game, or disqualified variant."""
    text = item_text(item)
 
    for word in search.get("exclude_keywords", []):
        if word in text:
            return False, f"matched exclude phrase '{word}'"
 
    require_words = search.get("require_keywords")
    if require_words and not any(word in text for word in require_words):
        return False, f"missing required word (one of {require_words})"
 
    min_battery = search.get("min_battery_percent")
    if min_battery:
        match = BATTERY_PATTERN.search(text)
        if match and int(match.group(1)) < min_battery:
            return False, f"battery listed at {match.group(1)}%, below {min_battery}%"
 
    price_to = search.get("price_to")
    if price_to and item_price(item) > float(price_to):
        return False, "priced above target despite search filter"
 
    return True, None
 
 
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
            print(f"[{label}] No listings came back — check search_text/price_to, "
                  f"or Vinted may be temporarily blocking this request.")
            continue
 
        total_checked += len(listings)
 
        for item in listings:
            item_id = str(item.get("id"))
            if not item_id or item_id in seen_ids:
                continue
            seen_ids.add(item_id)
 
            ok, _reason = matches_target(item, search)
            if not ok:
                continue
 
            flags = scam_flags(item)
            if len(flags) >= SCAM_FLAG_THRESHOLD:
                continue
 
            title = item.get("title", "Vinted listing")
            price = item_price(item)
            item_url = f"https://{VINTED_DOMAIN}/items/{item_id}"
 
            note = ""
            if search.get("min_battery_percent") and not BATTERY_PATTERN.search(item_text(item)):
                note = " (battery % not stated — check before buying)"
 
            send_notification(
                title=f"{label}: {title}",
                message=f"{CURRENCY_SYMBOL}{price:.2f} — {title}{note}",
                url=item_url,
            )
            total_alerts += 1
 
    save_seen_ids(seen_ids)
    print(f"Checked {total_checked} listings across {len(SEARCH_ITEMS)} "
          f"searches, sent {total_alerts} alert(s).")
 
 
if __name__ == "__main__":
    main()
