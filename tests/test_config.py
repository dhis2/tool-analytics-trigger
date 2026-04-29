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


def test_modes_defaults_when_no_modes_in_config(tmp_path):
    cfg = load_config(_write_config(tmp_path, BASE_CONFIG))
    assert cfg.modes["continuous"] == CONTINUOUS_PARAMS
    assert cfg.modes["incremental"] == INCREMENTAL_PARAMS
    assert cfg.modes["full"] == FULL_PARAMS


def test_modes_override_merges_over_defaults(tmp_path):
    data = {**BASE_CONFIG, "modes": {"continuous": {"lastYears": "2"}}}
    cfg = load_config(_write_config(tmp_path, data))
    assert cfg.modes["continuous"]["lastYears"] == "2"
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
    assert cfg.modes["incremental"] == INCREMENTAL_PARAMS
    assert cfg.modes["full"] == FULL_PARAMS
