# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python CLI utility that triggers DHIS2 analytics runs via the REST API, polls for completion, and sends alerts (Telegram and/or generic webhook). Primary use case is **continuous analytics** (`lastYears=0`) on high-volume tracker-only systems where full analytics runs are too slow — process only recently changed data on a 2-hour schedule, with a full rebuild once a week.

## Running the script

```bash
# Activate venv first
source .venv/bin/activate

# Dry run (no actual requests)
python dhis2_analytics_trigger.py --mode continuous --config dish.conf --dry-run

# Continuous analytics (recently changed data only, tracker-only systems)
python dhis2_analytics_trigger.py --mode continuous --config dish.conf

# Full analytics run
python dhis2_analytics_trigger.py --mode full --config dish.conf

# Fire-and-forget (no polling)
python dhis2_analytics_trigger.py --mode continuous --config dish.conf --no-watch

# Tune polling
python dhis2_analytics_trigger.py --mode full --config dish.conf --poll-interval 30 --max-wait 43200
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Architecture

**Entry point:** `main()` in `dhis2_analytics_trigger.py` parses CLI args, loads config, then calls either `post_analytics()` (fire-and-forget) or `trigger_and_watch()` (POST + poll + alert).

**Config dataclasses** (`load_config()`):
- `AppConfig` → `DHISConfig` + `AlertingConfig`
- `DHISConfig`: `base_url`, `token`, `verify_ssl`, `timeout_seconds`; derives `analytics_endpoint` as `{base_url}/api/resourceTables/analytics`
- `AlertingConfig`: `webhook_url`, `telegram` (dict with `bot_token`/`chat_id`), `only_on_failure`

**Analytics modes** are defined entirely in the config file under a `modes` key. Each mode is a free-form dict of DHIS2 analytics query params. Any string is accepted as `--mode`; the script validates the mode exists in the loaded config and exits with a clear error listing available modes if not. JSON booleans are coerced to lowercase strings. Params not listed in a mode are omitted from the POST — DHIS2 applies its own defaults (`false` / no `lastYears` limit). The `config.json.sample` documents three common modes (`continuous`, `incremental`, `full`) as a starting point.

**Task polling** (`poll_task_logs()`): polls the `relativeNotifierEndpoint` returned in the trigger response. Deduplicates events by `uid`. Starts a grace window (`grace_seconds_after_complete`, default 10s) once a `completed:true` event is seen, then classifies outcome:
- **Success**: any `completed:true` INFO event whose message contains `"analytics tables updated"` (case-insensitive)
- **Failure**: latest `completed` event is ERROR/FATAL, or fallback to any ERROR/FATAL event anywhere

**Alerting**: both webhook and Telegram respect `only_on_failure`. Telegram formatting uses HTML (not Markdown) to avoid escaping issues.

**Auth**: `ApiToken` header if `token` is set; falls back to `HTTPBasicAuth` using `DHIS2_USERNAME`/`DHIS2_PASSWORD` env vars.

**`telegram_alerts.py`**: standalone helper imported by the main script. Contains `send_telegram_alert()`, `format_success_summary()`, and `format_failure_summary()`. Handles Telegram 429 rate-limit with a single retry.

**`user-enc.py`**: unrelated standalone script for signing HMAC proofs against the DHIS2 `user-enc` token resolution endpoint. Not part of the analytics trigger flow.

## Config file

`config.json.sample` is the committed reference. Local config (e.g. `dish.conf`) is gitignored and holds real credentials. Config supports a `d2:token` alias for `token` in the `dhis` block.