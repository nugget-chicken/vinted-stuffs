# Vinted Deal & Scam Watcher — Setup Guide

This bot checks Vinted for new listings that match your search, works out
which ones are underpriced (good deals) and which look sketchy (possible
scams), and sends a push notification to your phone for the good ones.

It runs for free, in the cloud, using a service called **GitHub Actions** —
you don't need your own computer running 24/7 or a Raspberry Pi. Everything
below is done through your web browser; you won't need to install anything
or touch a command line.

---

## What you'll set up, in order

1. A GitHub account and a repository (a folder in the cloud) to hold the code
2. A push notification app on your phone (ntfy)
3. The bot's settings (what to search for)
4. GitHub Actions turned on, so it runs automatically

---

## Step 1: Create a GitHub account

If you don't already have one: go to [github.com](https://github.com) and
sign up. It's free.

## Step 2: Create a new repository

A "repository" (or "repo") is just a folder for your project that lives on
GitHub.

1. Click the **+** icon in the top-right corner → **New repository**
2. Name it something like `vinted-deal-bot`
3. Set it to **Public** — this matters because public repos get *unlimited*
   free minutes to run the bot, while private repos are capped at 2,000
   minutes/month (still plenty, but public is simpler). The only "private"
   info in this repo is item ID numbers, nothing personal.
4. Click **Create repository**

## Step 3: Upload the bot's files

You should have four files/folders from me:
- `vinted_bot.py`
- `requirements.txt`
- `seen_ids.json`
- `.github/workflows/check.yml`

On your new repo's GitHub page:

1. Click **Add file** → **Upload files**
2. Drag in `vinted_bot.py`, `requirements.txt`, and `seen_ids.json`
3. Click **Commit changes** at the bottom

The `.github/workflows/check.yml` file needs to go in a folder structure,
which the upload box handles automatically if you drag the whole
`.github` folder in — do that the same way as step above (or create it by
hand: **Add file → Create new file**, and type `.github/workflows/check.yml`
as the file name — GitHub will create the folders for you — then paste in
the workflow content and commit).

## Step 4: Set up push notifications (ntfy)

1. Install the **ntfy** app on your phone (search "ntfy" on the App Store
   or Google Play — it's free, no account needed)
2. Open the app and subscribe to a topic name — think of this like a
   private-ish channel name, e.g. `leo-vinted-deals-x7k2`. Make it random
   so strangers can't guess it and see your alerts.
3. Keep that exact topic name — you'll paste it into the bot's settings next

## Step 5: Edit the bot's settings

Back in your GitHub repo:

1. Click on `vinted_bot.py` to open it
2. Click the **pencil icon** (top right) to edit it
3. Near the top, under `# 1. SETTINGS`, change:
   - `SEARCH_TEXT` — what you're searching for, e.g. `"nike air force 1"`
   - `NTFY_TOPIC` — the topic name from Step 4
   - `VINTED_DOMAIN` — your country's Vinted site, e.g. `www.vinted.co.uk`,
     `www.vinted.com`, `www.vinted.fr`
   - `PRICE_TO` — optional max price, e.g. `"40"`, or leave as `""` for no limit
4. Scroll down, click **Commit changes**

## Step 6: Let GitHub Actions push updates back to the repo

The bot needs permission to save its own "already seen" list.

1. In your repo, go to **Settings** (top menu) → **Actions** → **General**
   (left sidebar)
2. Scroll to **Workflow permissions**
3. Select **Read and write permissions**
4. Click **Save**

## Step 7: Test it manually

1. Go to the **Actions** tab at the top of your repo
2. You should see **Vinted Deal Watcher** listed — click it
3. Click **Run workflow** → **Run workflow** (green button)
4. Wait ~30 seconds, then click on the run that appears to watch its
   progress. If it finishes with a green checkmark, it worked
5. If nothing goes wrong but you don't get a notification, that's normal —
   it only notifies you when it finds a good deal, not every run

## Step 8: Sit back

Once Step 7 works, the schedule in `check.yml` takes over automatically —
it'll check every 10 minutes from now on, no further action needed.

---

## Adjusting it later

- **Change what you're searching for**: edit `SEARCH_TEXT` in `vinted_bot.py`
  the same way as Step 5
- **Make it stricter/looser on "good deal"**: change
  `DEAL_DISCOUNT_THRESHOLD` (0.30 = 30% under typical price; raise it for
  fewer, better deals)
- **Check less/more often**: edit the `cron` line in `check.yml` — don't go
  below every 5 minutes, and every 10–15 minutes is a friendlier pace on
  Vinted's servers anyway

## If something's not working

- **"No listings came back"** in the run logs → double check `SEARCH_TEXT`
  and `VINTED_DOMAIN` are spelled right
- **The run fails on the last step (git push)** → you likely skipped Step 6
  (Read and write permissions)
- **Runs seem to skip or run late** → this is normal — GitHub's free
  schedule isn't perfectly precise, especially right at the top of the hour
