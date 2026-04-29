# Design: Configurable Mode Parameters

**Date:** 2026-04-29
**Status:** Approved

## Problem

Analytics mode parameters (`skipResourceTables`, `lastYears`, etc.) are hardcoded in the script. Changing them requires editing Python source code rather than the config file.

## Design

Add an optional `modes` block to the JSON config. Each key is a mode name (`continuous`, `incremental`, `full`); its value is a dict of query params that is **merged over** the hardcoded defaults (config values win, unspecified keys retain their defaults).

### Config shape

```json
{
  "dhis": { ... },
  "alerting": { ... },
  "modes": {
    "continuous": {
      "lastYears": "2"
    }
  }
}
```

### Code changes

1. **Remove `_DEFAULT_MODE_PARAMS` indirection** — reference `CONTINUOUS_PARAMS`, `INCREMENTAL_PARAMS`, and `FULL_PARAMS` directly in the merge loop inside `load_config()`. No new intermediate dict needed.

2. **`AppConfig`** — add `modes: Dict[str, Dict[str, str]]` field. This field has no default; `load_config()` always populates it from the hardcoded defaults (plus any config overrides), so it is never absent at runtime. Use `field(default_factory=dict)` if a dataclass default is required.

3. **`load_config()`** — build `modes` by merging defaults with config overrides. Config values are coerced to `str` so that JSON booleans (`true`/`false`) don't reach `requests` as Python `bool`:
   ```python
   _defaults = {
       "continuous": CONTINUOUS_PARAMS,
       "incremental": INCREMENTAL_PARAMS,
       "full": FULL_PARAMS,
   }
   modes_raw = raw.get("modes", {})
   modes = {}
   for name, defaults in _defaults.items():
       overrides = {
           k: str(v).lower() if isinstance(v, bool) else str(v)
           for k, v in modes_raw.get(name, {}).items()
       }
       modes[name] = {**defaults, **overrides}
   ```

4. **`post_analytics()`** — replace the internal mode→params resolution with a `params: Dict[str, str]` argument. Remove the `assert` and the `if/elif/else` block. Keep `mode: str` for logging only.

5. **Update both call sites** of `post_analytics()`:
   - `trigger_and_watch()` (line ~327): resolve `params = app_cfg.modes[mode]` and pass to `post_analytics()`
   - `main()` no-watch branch (line ~461): resolve `params = cfg.modes[args.mode]` and pass to `post_analytics()`

6. **`config.json.sample`** — add an example `modes` block showing how to override a param.

## Out of scope

- Custom mode names beyond the three standard ones
- Per-run param overrides via CLI flags
