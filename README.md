# DHIS2 Analytics Trigger

A Python utility to trigger DHIS2 analytics via `POST` and (optionally)
watch progress, log output, and send alerts (generic webhook + Telegram).

The primary use case is **continuous analytics** on high-volume tracker systems
where standard analytics runs are too slow. By using `lastYears=0`, only recently
changed data is processed, allowing frequent short runs instead of one long nightly job.

## What it does
- Triggers analytics runs in three modes:
  - **Continuous**: `lastYears=0`, skips resource tables and aggregate tables — only recently changed tracker data. Use for high-frequency scheduling (e.g. every 2h).
  - **Incremental**: skips resource tables; `lastYears=1`
  - **Full**: includes resource tables; processes all years
- Polls `/api/system/tasks/ANALYTICS_TABLE/<id>` until completion, then classifies the outcome.
- Sends alerts:
  - **Webhook** (any JSON endpoint)
  - **Telegram** (bot token + chat id)
  - Respects `only_on_failure` for both paths.

## Files
- `dhis2_analytics_trigger.py` – main script
- `telegram_alerts.py` – Telegram helper
- `requirements.txt`

## Install
```bash
sudo mkdir -p /opt/tool-analytics-trigger
cd /opt/tool-analytics-trigger
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Configure

Keep your config in `/opt/tool-analytics-trigger/config.json` alongside the script.
Copy `config.json.sample` as a starting point:

```bash
cp config.json.sample /opt/tool-analytics-trigger/config.json
```

Then edit it:

```json
{
  "dhis": {
    "base_url": "https://your-dhis2-instance/",
    "token": "<PASTE_TOKEN>",
    "verify_ssl": true,
    "timeout_seconds": 60
  },
  "alerting": {
    "webhook_url": null,
    "only_on_failure": true,
    "telegram": {
      "bot_token": "123456:ABCDEF...",
      "chat_id": "-1001234567890"
    }
  }
}
```

> For local/dev DHIS2 use e.g. `http://localhost:8080` as `base_url`.

If you want to use the Telegram alerts, create a bot with [BotFather](https://t.me/botfather)
and get your chat ID with [@userinfobot](https://t.me/userinfobot). For group chats, add the
bot to the group and promote it to admin.

## Run
```bash
# Dry run
/opt/tool-analytics-trigger/.venv/bin/python dhis2_analytics_trigger.py --mode continuous --config /opt/tool-analytics-trigger/config.json --dry-run

# Continuous analytics (recently changed data only)
/opt/tool-analytics-trigger/.venv/bin/python dhis2_analytics_trigger.py --mode continuous --config /opt/tool-analytics-trigger/config.json

# Full analytics run
/opt/tool-analytics-trigger/.venv/bin/python dhis2_analytics_trigger.py --mode full --config /opt/tool-analytics-trigger/config.json
```
CLI flags: `--poll-interval`, `--max-wait`, `--no-watch`.

## Cron

Recommended schedule for a high-volume tracker-only system:
- Continuous analytics every 2 hours during business hours (07:00–17:00), Mon–Sat
- Full rebuild once a week (early Sunday morning)

```cron
TZ=Africa/Nairobi
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Continuous: every 2h during business hours (07:00–17:00), Mon–Sat
0 7-18/2 * * 1-6 /usr/bin/flock -n /var/lock/dhis2-analytics.lock /opt/tool-analytics-trigger/.venv/bin/python /opt/tool-analytics-trigger/dhis2_analytics_trigger.py --mode continuous --config /opt/tool-analytics-trigger/config.json >> /var/log/dhis2_trigger.log 2>&1

# Full: weekly on Sunday at 01:00 (allow up to 12h)
0 1 * * 0 /usr/bin/flock -n /var/lock/dhis2-analytics.lock /opt/tool-analytics-trigger/.venv/bin/python /opt/tool-analytics-trigger/dhis2_analytics_trigger.py --mode full --max-wait 43200 --config /opt/tool-analytics-trigger/config.json >> /var/log/dhis2_trigger.log 2>&1
```

## How success/failure is detected
- Success: an `INFO` event with `completed:true` and a message like **"Analytics tables updated: …"**.
- Failure: latest `completed:true` event is `ERROR`/`FATAL`, or any fatal signal with no success marker.
- A short grace window is used after the first `completed:true` to catch trailing events.

## Troubleshooting
- **Auth**: uses `Authorization: ApiToken <token>`. For Basic auth, set `DHIS2_USERNAME` / `DHIS2_PASSWORD` env vars. Note that the use of Basic Authentication is discouraged.
- **SSL**: set `verify_ssl:false` temporarily to diagnose CA issues (fix CA properly for prod).
- **Overlaps**: `flock` prevents concurrent runs.
- **Logs**: `/var/log/dhis2_trigger.log`; set up logrotate if needed.

---
Tweak `lastYears` in the params if your DHIS2 needs a different window.
