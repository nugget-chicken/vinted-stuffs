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


## Step 1: Set up push notifications (ntfy)

1. Install the **ntfy** app on your phone (search "ntfy" on the App Store
   or Google Play — it's free, no account needed)
2. Open the app and subscribe to a topic name — think of this like a
   private-ish channel name, e.g. `xxx-vinted-deals-x7k2`. Make it random
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
