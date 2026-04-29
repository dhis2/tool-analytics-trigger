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
