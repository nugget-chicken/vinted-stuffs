vinted deal bot

Watches Vinted for phones and consoles, has Gemini judge deal quality and scam risk on anything new, and pushes an alert to your phone via ntfy when something's worth looking at. Runs on GitHub Actions, no server needed.

how it works

Every 15 min: search each watch in config.json -> drop anything already seen -> pull each new seller's profile (account age, feedback) -> send it all to Gemini in one batch for a deal score (1-10) and scam risk -> alert on anything past the watch's min_deal_score that isn't high risk -> mark everything as seen either way so nothing gets rescored.

price_to in the config is just a search filter, not the deal bar — Gemini decides if a price is actually good for that item, not just whether it's under the cap.

files
.github/workflows/vinted-bot.yml   the cron job
scripts/vinted_bot.py              the bot
scripts/config.json                what to search for
scripts/requirements.txt           deps
data/seen_listings.json            dedup state, committed back by the workflow
setup

Three repo secrets (Settings -> Secrets and variables -> Actions):

SCRAPEBADGER_API_KEY — from your ScrapeBadger dashboard
GEMINI_API_KEY — from aistudio.google.com, free tier, no billing needed
NTFY_TOPIC — make up a long/random name (anyone who knows it can subscribe to your alerts), then subscribe to it yourself in the ntfy app

Also set Settings -> Actions -> General -> Workflow permissions to "Read and write," or the workflow can't commit the dedup file back.

Push everything, then trigger a manual run from the Actions tab before letting the cron take over.

config.json

One entry per saved search:

json
{ "name": "ps5-under-300", "query": "ps5", "market": "us", "price_from": 20, "price_to": 300, "min_deal_score": 7 }

query is the only required field. min_deal_score is the actual alert threshold (1-10) — raise it if you're getting flooded, lower it if you're hearing nothing.

test mode

Actions tab -> Run workflow -> tick "Test mode." Runs the real search and dedup, skips Gemini, fake-passes every new listing so you can check ntfy delivery without a working Gemini key.

known limits
Scam detection leans on seller account age/feedback, not the listing description — the search API doesn't return descriptions, so it can't catch red-flag phrases like "pay outside the app."
Seller-profile lookups (member-since date, feedback count) hit an under-documented ScrapeBadger endpoint. If it starts failing, the bot just treats that seller as unknown (elevated risk) rather than crashing — check the Action log for DEBUG first seller profile response or Seller profile lookup failed if it seems off.
ScrapeBadger charges per call — searches are cheap, profile lookups cost more. The first run costs the most since everything looks "new."
Requests back off automatically on rate limits (429s), with a small delay between each watch's search either way.
