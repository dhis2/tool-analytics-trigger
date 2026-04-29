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
