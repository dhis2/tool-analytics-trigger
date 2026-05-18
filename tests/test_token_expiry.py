import os
import sys
import logging

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from dhis2_analytics_trigger import check_token_expiry, DHISConfig, AlertingConfig
from telegram_alerts import format_token_expiry_warning

CFG = DHISConfig(base_url="http://localhost:8080/dhis", token="tok", verify_ssl=False)
ALERTING = AlertingConfig(telegram={"bot_token": "123:ABC", "chat_id": "-100"})
ALERTING_NO_TG = AlertingConfig()


def _epoch_ms(dt: datetime) -> int:
    """Convert a datetime to epoch milliseconds (as DHIS2 returns)."""
    return int(dt.timestamp() * 1000)


def _make_response(status_code, json_body):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    return resp


def _session_with_tokens(expire_epochs):
    """Build a mock session returning /api/me and /api/apiToken responses.

    expire_epochs: list of epoch-ms ints or None (perpetual).
    """
    tokens = []
    for i, exp in enumerate(expire_epochs):
        tok = {"id": f"tok{i}", "code": f"code{i}"}
        if exp is not None:
            tok["expire"] = exp
        tokens.append(tok)

    me_resp = _make_response(200, {"id": "userABC"})
    token_resp = _make_response(200, {"apiToken": tokens})

    session = MagicMock()
    session.get.side_effect = [me_resp, token_resp]
    return session


class TestCheckTokenExpiry:
    def test_warns_on_token_expiring_soon(self, caplog):
        """A token expiring in 3 days should produce a WARNING log."""
        expire_soon = _epoch_ms(datetime.now(timezone.utc) + timedelta(days=3))
        session = _session_with_tokens([expire_soon])

        with caplog.at_level(logging.WARNING):
            check_token_expiry(session, CFG, ALERTING_NO_TG)

        assert any("expires" in rec.message and "tok0" in rec.message for rec in caplog.records)

    def test_no_warning_for_distant_expiry(self, caplog):
        """A token expiring in 30 days should NOT trigger a warning."""
        expire_far = _epoch_ms(datetime.now(timezone.utc) + timedelta(days=30))
        session = _session_with_tokens([expire_far])

        with caplog.at_level(logging.DEBUG):
            check_token_expiry(session, CFG, ALERTING_NO_TG)

        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert not warning_records

    def test_skips_perpetual_tokens(self, caplog):
        """Tokens with no expire field should be silently skipped."""
        session = _session_with_tokens([None])

        with caplog.at_level(logging.DEBUG):
            check_token_expiry(session, CFG, ALERTING_NO_TG)

        assert any("no tokens expiring" in rec.message for rec in caplog.records)

    @patch("dhis2_analytics_trigger.send_telegram_alert")
    def test_sends_telegram_alert_when_configured(self, mock_tg):
        """Expiring token + Telegram config → send_telegram_alert called."""
        expire_soon = _epoch_ms(datetime.now(timezone.utc) + timedelta(days=2))
        session = _session_with_tokens([expire_soon])

        check_token_expiry(session, CFG, ALERTING)

        mock_tg.assert_called_once()
        args = mock_tg.call_args[0]
        assert args[0] == "123:ABC"
        assert args[1] == "-100"
        assert "expiring soon" in args[2].lower()

    def test_api_me_failure_is_non_blocking(self, caplog):
        """If /api/me returns 403, check should silently skip."""
        session = MagicMock()
        session.get.return_value = _make_response(403, {})

        with caplog.at_level(logging.DEBUG):
            check_token_expiry(session, CFG, ALERTING_NO_TG)

        assert any("skipped" in rec.message.lower() for rec in caplog.records)

    def test_network_error_is_non_blocking(self, caplog):
        """Network exceptions should be caught and logged at debug."""
        session = MagicMock()
        session.get.side_effect = ConnectionError("boom")

        with caplog.at_level(logging.DEBUG):
            check_token_expiry(session, CFG, ALERTING_NO_TG)

        assert any("skipped" in rec.message.lower() for rec in caplog.records)

    def test_mixed_tokens(self, caplog):
        """Only expiring-soon tokens produce warnings; others are silent."""
        soon = _epoch_ms(datetime.now(timezone.utc) + timedelta(days=1))
        far = _epoch_ms(datetime.now(timezone.utc) + timedelta(days=60))
        session = _session_with_tokens([soon, far, None])

        with caplog.at_level(logging.WARNING):
            check_token_expiry(session, CFG, ALERTING_NO_TG)

        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_records) == 1
        assert "tok0" in warning_records[0].message

    def test_already_expired_token_warns(self, caplog):
        """A token that already expired should still produce a warning (0 days)."""
        expired = _epoch_ms(datetime.now(timezone.utc) - timedelta(days=1))
        session = _session_with_tokens([expired])

        with caplog.at_level(logging.WARNING):
            check_token_expiry(session, CFG, ALERTING_NO_TG)

        assert any("0 days remaining" in rec.message for rec in caplog.records)


class TestFormatTokenExpiryWarning:
    def test_basic_format(self):
        tokens = [
            {"id": "abc123", "expire": "2025-06-01", "days_remaining": 5},
        ]
        result = format_token_expiry_warning(expiring_tokens=tokens)
        assert "expiring soon" in result.lower()
        assert "abc123" in result
        assert "5 days" in result

    def test_includes_endpoint(self):
        tokens = [
            {"id": "x", "expire": "2025-06-01", "days_remaining": 3},
        ]
        result = format_token_expiry_warning(expiring_tokens=tokens, endpoint="https://play.dhis2.org")
        assert "play.dhis2.org" in result

    def test_singular_day(self):
        tokens = [
            {"id": "x", "expire": "2025-06-01", "days_remaining": 1},
        ]
        result = format_token_expiry_warning(expiring_tokens=tokens)
        assert "1 day)" in result
