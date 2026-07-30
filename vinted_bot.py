"""
Vinted Deal & Scam Watcher
---------------------------
Checks a Vinted search for new listings, works out which ones look like
good deals (and which look sketchy), and sends you a push notification
via ntfy.sh for anything worth looking at.

You can run this on your own computer with:
    python vinted_bot.py

...but the whole point is to let GitHub Actions run it automatically on
a schedule, so you don't have to. See the README for setup steps.
"""

import json
import statistics
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# 1. SETTINGS — this is the only section you should need to edit
# ---------------------------------------------------------------------------

VINTED_DOMAIN = "www.vinted.co.uk"     # swap for your country's Vinted site
SEARCH_TEXT = "nike air force 1"       # what you're hunting for
PRICE_TO = ""                          # e.g. "40" to cap price, "" = no cap
PER_PAGE = 40                          # how many listings to check each run
CURRENCY_SYMBOL = "£"                  # just used in the notification text

# How far below the going price counts as a "good deal".
# 0.30 means 30% cheaper than similar listings.
DEAL_DISCOUNT_THRESHOLD = 0.30

# A listing needs at least this many red flags to get treated as sketchy
SCAM_FLAG_THRESHOLD = 2

# Your ntfy.sh topic name — make it random/unguessable, anyone who knows
# it can see your alerts (it's a public service, not a private inbox).
NTFY_TOPIC = "leo-vinted-deals-x7k2"

SEEN_IDS_FILE = Path(__file__).parent / "seen_ids.json"

# ---------------------------------------------------------------------------
# 2. FETCH LISTINGS FROM VINTED
# ---------------------------------------------------------------------------

def get_listings():
    """Ask Vinted's own search API for the current listings — the same
    request your browser makes when you search on the website."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    })

    # Vinted's API expects cookies from a normal page visit first, so we
    # grab those before calling the API itself.
    session.get(f"https://{VINTED_DOMAIN}/")

    params = {
        "search_text": SEARCH_TEXT,
        "order": "newest_first",
        "per_page": PER_PAGE,
    }
    if PRICE_TO:
        params["price_to"] = PRICE_TO

    response = session.get(
        f"https://{VINTED_DOMAIN}/api/v2/catalog/items",
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("items", [])


def item_price(item):
    """Pull a plain number out of Vinted's price field, whatever shape
    it happens to be in."""
    price = item.get("price")
    if isinstance(price, dict):
        return float(price.get("amount", 0) or 0)
    try:
        return float(price)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# 3. "GOOD DEAL" CHECK
# ---------------------------------------------------------------------------

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

def scam_flags(item, all_prices):
    flags = []

    seller = item.get("user") or {}
    if seller.get("feedback_count", 0) == 0:
        flags.append("seller has no reviews")

    price = item_price(item)
    if all_prices:
        median_price = statistics.median(all_prices)
        if median_price > 0 and price < median_price * 0.4:
            flags.append("price is far below similar listings")

    if not item.get("photo"):
        flags.append("no photo on the listing")

    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
    off_platform_hints = ["whatsapp", "telegram", "paypal friends", "venmo", "zelle"]
    if any(hint in text for hint in off_platform_hints):
        flags.append("mentions paying outside Vinted")

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
# 6. KEEPING TRACK OF WHAT WE'VE ALREADY SEEN
# ---------------------------------------------------------------------------

def load_seen_ids():
    if SEEN_IDS_FILE.exists():
        return set(json.loads(SEEN_IDS_FILE.read_text() or "[]"))
    return set()


def save_seen_ids(ids):
    SEEN_IDS_FILE.write_text(json.dumps(sorted(ids)))


# ---------------------------------------------------------------------------
# 7. PUTTING IT ALL TOGETHER
# ---------------------------------------------------------------------------

def main():
    listings = get_listings()
    if not listings:
        print(
            "No listings came back. Double-check SEARCH_TEXT / "
            "VINTED_DOMAIN in the settings, or Vinted may be temporarily "
            "blocking this request — try again in a bit."
        )
        return

    seen_ids = load_seen_ids()
    all_prices = [item_price(item) for item in listings]
    new_alerts = 0

    for item in listings:
        item_id = str(item.get("id"))
        if not item_id or item_id in seen_ids:
            continue
        seen_ids.add(item_id)

        deal = is_good_deal(item, all_prices)
        flags = scam_flags(item, all_prices)
        looks_sketchy = len(flags) >= SCAM_FLAG_THRESHOLD

        if deal and not looks_sketchy:
            title = item.get("title", "Vinted listing")
            price = item_price(item)
            item_url = f"https://{VINTED_DOMAIN}/items/{item_id}"
            send_notification(
                title=f"Good deal: {title}",
                message=f"{CURRENCY_SYMBOL}{price:.2f} — {title}",
                url=item_url,
            )
            new_alerts += 1

    save_seen_ids(seen_ids)
    print(f"Checked {len(listings)} listings, sent {new_alerts} alert(s).")


if __name__ == "__main__":
    main()
