# Config-Driven Analytics Modes

**Date:** 2026-05-07

## Problem

The script has three hardcoded analytics mode param dicts (`CONTINUOUS_PARAMS`, `INCREMENTAL_PARAMS`, `FULL_PARAMS`) and a `choices=["continuous", "incremental", "full"]` constraint on `--mode`. This prevents operators from defining custom modes (e.g. `enrollments`, `resource_tables`) without modifying the script itself.

## Decision

Move all mode param definitions into the config file. The script holds no hardcoded defaults. Any string is accepted as `--mode`; the script looks it up in the config and fails clearly if it is not found.

## Changes

### `dhis2_analytics_trigger.py`

- Delete `CONTINUOUS_PARAMS`, `INCREMENTAL_PARAMS`, `FULL_PARAMS`.
- `load_config()`: replace the loop over `_defaults` with a direct read of `raw["modes"]`. Coerce each value to string (booleans → lowercase). `AppConfig.modes` is already `Dict[str, Dict[str, str]]` — no dataclass change.
- `argparse`: remove `choices=[...]` from `--mode`. After `load_config()`, validate `args.mode in cfg.modes`; if not, print a message listing available modes and exit with code 2. The dry-run path gets the same check.

### `config.json.sample`

Document the three common modes with their full param sets:

```json
"modes": {
  "continuous": {
    "skipResourceTables": "true",
    "skipAggregate": "true",
    "lastYears": "0"
  },
  "incremental": {
    "skipResourceTables": "true",
    "skipOrgUnitOwnership": "true",
    "skipTrackedEntities": "true",
    "skipOutliers": "true",
    "lastYears": "1"
  },
  "full": {
    "skipOutliers": "true"
  }
}
```

Any param omitted from a mode is not sent in the POST request; DHIS2 applies its server-side default (`false`, or no `lastYears` limit). The full set of accepted params is:

| Param | DHIS2 default |
|---|---|
| `skipResourceTables` | false |
| `skipAggregate` | false |
| `skipValidationResult` | false |
| `skipEvents` | false |
| `skipEnrollment` | false |
| `skipTrackedEntities` | false |
| `skipOrgUnitOwnership` | false |
| `skipOutliers` | false |
| `lastYears` | (no limit) |

### `CLAUDE.md`

Update the architecture section: modes are entirely config-driven; the three hardcoded param dicts are removed.

## Behaviour

- **Unknown mode**: `error: mode 'foo' not found in config. Available modes: continuous, full` → exit 2.
- **No modes in config**: same error with an empty available list and a hint to add a `modes` block.
- **Existing deployments**: any deployment that already has a `modes` block in its config file continues to work. Deployments without a `modes` block will fail on the mode lookup — they need to add the block once.

## Out of scope

- Param name validation (e.g. warning on unknown keys) — omitted per YAGNI; admins are the target users.
- Default param values baked into the script — intentionally removed.
