# Configurable Mode Parameters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move hardcoded analytics mode query params out of `dhis2_analytics_trigger.py` and into the JSON config file, merging config values over hardcoded defaults.

**Architecture:** Add an optional `modes` block to the JSON config. `load_config()` builds a `modes: Dict[str, Dict[str, str]]` dict on `AppConfig` by merging hardcoded defaults with any per-mode overrides from config. `post_analytics()` receives the resolved params dict directly rather than resolving them internally.

**Tech Stack:** Python 3, pytest, requests

---

## Files

- Modify: `dhis2_analytics_trigger.py` — `AppConfig`, `load_config()`, `post_analytics()`, and two call sites
- Modify: `config.json.sample` — add example `modes` block, **remove live token** (see Task 5)
- Create: `tests/test_config.py` — unit tests for config loading and param merging
- Create: `tests/test_post_analytics.py` — unit tests for `post_analytics()` signature
- Modify: `requirements.txt` — add `pytest`

---

### Task 1: Add pytest to requirements and create test skeleton

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Add pytest to requirements.txt**

The file currently contains:
```
urllib3
requests>=2.25.0
```
Add pytest:
```
urllib3
requests>=2.25.0
pytest>=7.0
```

- [ ] **Step 2: Install the new dependency**

Run:
```bash
source .venv/bin/activate && pip install pytest
```
Expected: pytest installs successfully.

- [ ] **Step 3: Create tests package**

Create `tests/__init__.py` as an empty file.

- [ ] **Step 4: Create test file with skeleton**

Create `tests/test_config.py`:
```python
import json
import os
import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dhis2_analytics_trigger import load_config, CONTINUOUS_PARAMS, INCREMENTAL_PARAMS, FULL_PARAMS


def _write_config(tmp_path, data: dict) -> str:
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data))
    return str(p)


BASE_CONFIG = {
    "dhis": {
        "base_url": "http://localhost:8080/dhis",
        "token": "test-token",
    },
    "alerting": {},
}
```

- [ ] **Step 5: Commit skeleton**

```bash
git add requirements.txt tests/
git commit -m "test: add pytest and test skeleton for config loading"
```

---

### Task 2: Test and implement `AppConfig.modes` + `load_config()` changes

**Files:**
- Modify: `tests/test_config.py`
- Modify: `dhis2_analytics_trigger.py` (line 40, lines 71–74, lines 102–123)

- [ ] **Step 1: Write failing tests**

Append to `tests/test_config.py`:
```python
def test_modes_defaults_when_no_modes_in_config(tmp_path):
    cfg = load_config(_write_config(tmp_path, BASE_CONFIG))
    assert cfg.modes["continuous"] == CONTINUOUS_PARAMS
    assert cfg.modes["incremental"] == INCREMENTAL_PARAMS
    assert cfg.modes["full"] == FULL_PARAMS


def test_modes_override_merges_over_defaults(tmp_path):
    data = {**BASE_CONFIG, "modes": {"continuous": {"lastYears": "2"}}}
    cfg = load_config(_write_config(tmp_path, data))
    assert cfg.modes["continuous"]["lastYears"] == "2"
    # Other keys still present from defaults
    assert cfg.modes["continuous"]["skipResourceTables"] == "true"
    assert cfg.modes["continuous"]["skipAggregate"] == "true"


def test_modes_json_bool_coerced_to_lowercase_str(tmp_path):
    # JSON booleans (Python True/False) must become "true"/"false", not "True"/"False",
    # because the DHIS2 API requires lowercase.
    data = {**BASE_CONFIG, "modes": {"full": {"skipResourceTables": True, "skipOutliers": False}}}
    cfg = load_config(_write_config(tmp_path, data))
    assert cfg.modes["full"]["skipResourceTables"] == "true"
    assert cfg.modes["full"]["skipOutliers"] == "false"
    assert isinstance(cfg.modes["full"]["skipResourceTables"], str)


def test_modes_unspecified_modes_still_have_defaults(tmp_path):
    data = {**BASE_CONFIG, "modes": {"continuous": {"lastYears": "3"}}}
    cfg = load_config(_write_config(tmp_path, data))
    # incremental and full untouched
    assert cfg.modes["incremental"] == INCREMENTAL_PARAMS
    assert cfg.modes["full"] == FULL_PARAMS
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
source .venv/bin/activate && pytest tests/test_config.py -v
```
Expected: All four tests FAIL — `AppConfig` has no `modes` attribute yet.

- [ ] **Step 3: Update the `dataclasses` import on line 40**

`dhis2_analytics_trigger.py` line 40 currently reads:
```python
from dataclasses import dataclass
```
Change it to:
```python
from dataclasses import dataclass, field
```
This is a **separate edit** from the class change in Step 4.

- [ ] **Step 4: Add `modes` field to `AppConfig` (lines 71–74)**

Change lines 71–74 from:
```python
@dataclass
class AppConfig:
    dhis: DHISConfig
    alerting: AlertingConfig
```
To:
```python
@dataclass
class AppConfig:
    dhis: DHISConfig
    alerting: AlertingConfig
    modes: Dict[str, Dict[str, str]] = field(default_factory=dict)
```

- [ ] **Step 5: Update `load_config()` to build `modes` (lines 102–123)**

Replace the `load_config()` function body:
```python
def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    dhis_raw = raw.get("dhis", {})
    alert_raw = raw.get("alerting", {})

    dhis_cfg = DHISConfig(
        base_url=dhis_raw.get("base_url", "http://localhost:8080/dhis"),
        token=dhis_raw.get("token") or dhis_raw.get("d2:token"),
        verify_ssl=bool(dhis_raw.get("verify_ssl", True)),
        timeout_seconds=int(dhis_raw.get("timeout_seconds", 60)),
    )

    alert_cfg = AlertingConfig(
        webhook_url=alert_raw.get("webhook_url"),
        telegram=alert_raw.get("telegram"),
        only_on_failure=bool(alert_raw.get("only_on_failure", True)),
    )

    _defaults = {
        "continuous": CONTINUOUS_PARAMS,
        "incremental": INCREMENTAL_PARAMS,
        "full": FULL_PARAMS,
    }
    modes_raw = raw.get("modes", {})
    modes: Dict[str, Dict[str, str]] = {}
    for name, defaults in _defaults.items():
        overrides = {
            k: str(v).lower() if isinstance(v, bool) else str(v)
            for k, v in modes_raw.get(name, {}).items()
        }
        modes[name] = {**defaults, **overrides}

    return AppConfig(dhis=dhis_cfg, alerting=alert_cfg, modes=modes)
```

Note: `isinstance(v, bool)` check must come before any general `str()` call because `bool` is a subclass of `int` in Python — `str(True)` gives `"True"` (capital T), but DHIS2 expects lowercase `"true"`. Using `.lower()` only on booleans leaves string values untouched.

- [ ] **Step 6: Run tests to confirm they pass**

```bash
source .venv/bin/activate && pytest tests/test_config.py -v
```
Expected: All four tests PASS.

- [ ] **Step 7: Commit**

```bash
git add dhis2_analytics_trigger.py tests/test_config.py
git commit -m "feat: load mode params from config with merge-over-defaults"
```

---

### Task 3: Test and update `post_analytics()` signature

**Files:**
- Create: `tests/test_post_analytics.py`
- Modify: `dhis2_analytics_trigger.py` (lines 152–184)

- [ ] **Step 1: Write failing test**

Create `tests/test_post_analytics.py`:
```python
import os
import sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock
from dhis2_analytics_trigger import post_analytics, DHISConfig

CFG = DHISConfig(base_url="http://localhost:8080/dhis", token="tok", verify_ssl=False)


def test_post_analytics_uses_provided_params():
    custom_params = {"lastYears": "3", "skipResourceTables": "true"}
    mock_session = MagicMock()
    mock_session.post.return_value = MagicMock(status_code=200)

    post_analytics(mock_session, CFG, mode="continuous", params=custom_params)

    _, kwargs = mock_session.post.call_args
    # Verify the exact custom params were forwarded — not the hardcoded CONTINUOUS_PARAMS
    assert kwargs["params"] is custom_params
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
source .venv/bin/activate && pytest tests/test_post_analytics.py -v
```
Expected: FAIL with `TypeError: post_analytics() got an unexpected keyword argument 'params'`.

- [ ] **Step 3: Update `post_analytics()` signature**

In `dhis2_analytics_trigger.py`, replace lines 152–184 (the full `post_analytics` function):
```python
def post_analytics(
    session: requests.Session,
    cfg: DHISConfig,
    mode: str,
    params: Dict[str, str],
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> requests.Response:
    url = cfg.analytics_endpoint
    headers = build_headers(cfg)

    auth = None
    if not cfg.token and username and password:
        auth = requests.auth.HTTPBasicAuth(username, password)

    logging.info("POST %s mode=%s params=%s", url, mode, params)

    resp = session.post(
        url,
        params=params,
        headers=headers,
        timeout=cfg.timeout_seconds,
        verify=cfg.verify_ssl,
        auth=auth,
    )
    return resp
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
source .venv/bin/activate && pytest tests/test_post_analytics.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dhis2_analytics_trigger.py tests/test_post_analytics.py
git commit -m "refactor: post_analytics() accepts resolved params dict directly"
```

---

### Task 4: Update both `post_analytics()` call sites

**Files:**
- Modify: `dhis2_analytics_trigger.py` (lines ~327 and ~461)

- [ ] **Step 1: Update `trigger_and_watch()` call site (~line 327)**

Lines are inside a 4-space indented function body. Change:
```python
    resp = post_analytics(session, app_cfg.dhis, mode, username=username, password=password)
```
To (maintain the same 4-space indentation):
```python
    params = app_cfg.modes[mode]
    resp = post_analytics(session, app_cfg.dhis, mode, params, username=username, password=password)
```

- [ ] **Step 2: Update `main()` no-watch call site (~line 461)**

Lines are inside a doubly-indented `if/try` block (12 spaces). Change:
```python
            resp = post_analytics(session, cfg.dhis, args.mode, username=username, password=password)
```
To (maintain the same 12-space indentation):
```python
            params = cfg.modes[args.mode]
            resp = post_analytics(session, cfg.dhis, args.mode, params, username=username, password=password)
```

- [ ] **Step 3: Run full test suite**

```bash
source .venv/bin/activate && pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 4: Verify config loading manually**

```bash
source .venv/bin/activate && python -c "
from dhis2_analytics_trigger import load_config
import json, sys
cfg = load_config('config.json.sample')
print(json.dumps(cfg.modes, indent=2))
"
```
Expected: prints the three mode dicts with correct keys and lowercase string values.

- [ ] **Step 5: Commit**

```bash
git add dhis2_analytics_trigger.py
git commit -m "refactor: pass resolved mode params through both call sites"
```

---

### Task 5: Update `config.json.sample` and docs

**Files:**
- Modify: `config.json.sample`
- Modify: `CLAUDE.md`

**⚠️ WARNING:** The current `config.json.sample` contains a **live API token** (`d2p_iW6sSUjcXECsPfQ3abxFKDwFYTPp7KRJLi1sSsy2TMNX2t36rU`). This token should be revoked/rotated before or immediately after this commit, since it will remain in git history even after replacement. The step below replaces it with a placeholder — coordinate token rotation with the system administrator.

- [ ] **Step 1: Replace `config.json.sample` content**

Replace the entire file with:
```json
{
  "dhis": {
    "base_url": "https://play.im.dhis2.org/stable-2-42-1",
    "token": "<PASTE_TOKEN>",
    "verify_ssl": true,
    "timeout_seconds": 60
  },
  "alerting": {
    "webhook_url": null,
    "only_on_failure": false,
    "telegram": {
      "bot_token": "123456:ABCDEF...",
      "chat_id": "XXXXXXXXXXXXXXXXXX"
    }
  },
  "modes": {
    "continuous": {
      "lastYears": "0"
    },
    "full": {
      "skipOutliers": "false"
    }
  }
}
```

- [ ] **Step 2: Update `CLAUDE.md` architecture section**

In the `**Three analytics modes**` paragraph, append after the bullet list:

> Mode params can be overridden per-mode in the config under a `modes` key; config values are merged over the hardcoded defaults (config wins, unspecified keys retain defaults, JSON booleans coerced to lowercase strings).

Verify the edit landed:
```bash
grep -n "merged over" CLAUDE.md
```
Expected: one matching line.

- [ ] **Step 3: Commit**

```bash
git add config.json.sample CLAUDE.md
git commit -m "docs: show modes override block in config sample and CLAUDE.md"
```
