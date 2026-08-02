vinted deal bot that kinda works

Watches Vinted for phones and consoles, has Gemini judge whether each listing is actually a good deal (and whether the seller looks sketchy), and pushes a notification when something clears the bar. Runs on a schedule via GitHub Actions, no server needed.

how it works
GitHub Actions kicks the script off every 5 minutes.
For each search in scripts/config.json, it hits ScrapeBadger's Vinted search API and gets back listings under the price cap.
Anything not already seen (tracked in data/seen_listings.json) gets a quick seller-profile lookup — how old the account is, feedback count, how many other items they've sold.
All of that gets handed to Claude in one batch: score the deal quality 1-10, and flag scam risk based mostly on the seller history (a listing from a brand-new account with zero feedback is the biggest red flag).
Anything that scores high enough and isn't flagged as risky gets pushed to your phone via ntfy. Everything gets marked as seen either way so it's not re-scored next run.

The price cap in the config (price_to) is just a filter on what gets pulled from Vinted in the first place — it's not the deal bar. Claude decides whether $280 is actually good for that specific phone, not just whether it's under $300.

files
.github/workflows/vinted-bot.yml   the cron job
scripts/vinted_bot.py              the bot
scripts/config.json                what to search for
scripts/requirements.txt           python deps
data/seen_listings.json            dedup state
setup

You need three repo secrets (Settings → Secrets and variables → Actions):

SCRAPEBADGER_API_KEY — from your ScrapeBadger dashboard
GEMINI_API_KEY — from their api website (free version)
NTFY_TOPIC — make one up, keep it long/random since anyone who knows the name can subscribe to your alerts. Subscribe to it yourself in the ntfy app so you actually get the pushes.

Also: Settings → Actions → General → Workflow permissions needs to be set to "Read and write" so the workflow can commit the updated dedup file back.

Once secrets are set, push and trigger a manual run from the Actions tab to check everything's wired up before letting the cron take over.

editing what it searches for

Edit scripts/config.json. Each entry is one saved search:

json
{ "name": "ps5-under-300", "query": "ps5", "market": "us", "price_to": 300, "min_deal_score": 7 }
query — required, whatever you'd type into Vinted's search bar
market — vinted country code, us for the US site
price_to — upper price filter
min_deal_score — how good Claude has to rate it (1-10) before you get alerted. Raise it if you're getting flooded, lower it if you're not hearing anything.

Add as many watches as you want, each one costs a little extra in ScrapeBadger credits per run.

known rough edges
The seller-profile lookup (member-since date, feedback count) is based on an endpoint whose exact response format wasn't fully documented anywhere I could find — it's wrapped so a bad guess on field names won't crash the run, it'll just fall back to treating that seller's history as unknown. If it ever behaves oddly, check the Action log for a DEBUG first seller profile response line.
ScrapeBadger charges per call — searches are cheap, profile lookups cost more, so the first run (when everything looks "new") costs more than steady state.
Scam detection is only as good as what the API exposes. It can't read the actual listing description for red-flag phrases like "pay me outside the app," since the search endpoint doesn't return descriptions.
