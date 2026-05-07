import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dhis2_analytics_trigger import load_config


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


def test_modes_loaded_directly_from_config(tmp_path):
    data = {**BASE_CONFIG, "modes": {
        "continuous": {"skipResourceTables": "true", "lastYears": "0"},
        "full": {"skipOutliers": "true"},
    }}
    cfg = load_config(_write_config(tmp_path, data))
    assert cfg.modes["continuous"] == {"skipResourceTables": "true", "lastYears": "0"}
    assert cfg.modes["full"] == {"skipOutliers": "true"}


def test_no_modes_in_config_gives_empty_dict(tmp_path):
    cfg = load_config(_write_config(tmp_path, BASE_CONFIG))
    assert cfg.modes == {}


def test_modes_json_bool_coerced_to_lowercase_str(tmp_path):
    # JSON booleans (Python True/False) must become "true"/"false", not "True"/"False",
    # because the DHIS2 API requires lowercase.
    data = {**BASE_CONFIG, "modes": {"full": {"skipResourceTables": True, "skipOutliers": False}}}
    cfg = load_config(_write_config(tmp_path, data))
    assert cfg.modes["full"]["skipResourceTables"] == "true"
    assert cfg.modes["full"]["skipOutliers"] == "false"
    assert isinstance(cfg.modes["full"]["skipResourceTables"], str)


def test_custom_mode_name_loaded(tmp_path):
    data = {**BASE_CONFIG, "modes": {"enrollments": {"skipAggregate": "true", "skipEvents": "true"}}}
    cfg = load_config(_write_config(tmp_path, data))
    assert "enrollments" in cfg.modes
    assert cfg.modes["enrollments"]["skipAggregate"] == "true"
    assert cfg.modes["enrollments"]["skipEvents"] == "true"
