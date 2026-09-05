vinted deal bot

Watches Vinted for men's M/L running kit on `ro` (Craft, Odlo, 2XU, UA Rush, Nike Dri-FIT ADV, Adizero, Gore). Scores deal quality and scam risk on anything new, and pushes an alert to your phone via ntfy. Runs locally or on GitHub Actions.

Search uses **vinted-mcp-cli** (sibling checkout, or `npx @googlarz/vinted-client`). Scoring uses **Vercel AI Gateway** first (`AI_GATEWAY_API_KEY`), then **Gemini** if that fails. Cursor `/vinted` is the interactive hunter — do not point this cron at the Cursor Agent SDK.

how it works

Every 15 min: search each watch in config.json -> drop anything already seen -> pull each new seller's profile -> score deal (1-10) + scam risk -> alert on anything past `min_deal_score` that isn't high risk -> mark everything as seen either way.

`price_to` is only a search filter. The model decides if the price is actually a deal.

setup

```bash
set -a && source .env && set +a
python scripts/vinted_bot.py
```

Repo secrets on your fork (Actions):

- `AI_GATEWAY_API_KEY` — Vercel AI Gateway key
- `NTFY_TOPIC` — long random name; subscribe in the ntfy app
- `GEMINI_API_KEY` — optional fallback

Optional variable: `AI_GATEWAY_MODEL` (default `google/gemini-2.5-flash`).

Need at least one scorer key unless you run test mode. Set Actions → General → Workflow permissions to **Read and write** so the workflow can commit `data/seen_listings.json`.

config.json

`query` is required. `market` is a Vinted country code (`ro`, `hu`, `pl`, …). Men's clothing is `category_id` 5; men's M/L sizes are `208` and `209`.

test mode

`SKIP_SCORING=1` (or Actions → Run workflow → Test mode) skips the LLM and fake-passes every new listing. Use that only to check ntfy — it will alert everything new.

known limits

- Search results have no description, so "pay outside the app" will not show up.
- Missing seller history is treated as elevated risk.
- GitHub-hosted runners may get blocked by Vinted; a local or self-hosted run is more reliable.
