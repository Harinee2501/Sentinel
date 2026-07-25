"""
Unit tests for the Python middleware adaptor (@sentinel.guard decorator).

These mock SentinelEngine.guarded_execute() directly, so no real Policy
Engine / Judge / Drift Tracker logic runs here — that's already covered
by their own dedicated test files. This file only verifies the adaptor's
own responsibility: building a correct Action, calling guarded_execute,
and propagating the result (or the block) correctly.
"""

from unittest.mock import MagicMock, patch

import pytest

from agent_sentinel.adaptors.python_middleware import (
    Sentinel,
    current_agent_id,
    current_context,
    current_session_id,
)
from agent_sentinel.core.engine import SentinelBlockedError
from agent_sentinel.core.types import Verdict, VerdictType


@pytest.fixture
def sentinel():
    with patch("agent_sentinel.adaptors.python_middleware.SentinelEngine"):
        s = Sentinel(config="config/default_policy.yaml")
        yield s


def test_allowed_action_executes_and_returns_result(sentinel):
    current_agent_id.set("test-agent")
    current_session_id.set("test-session")
    current_context.set({"original_task": "Test task."})

    sentinel.engine.guarded_execute = MagicMock(
        side_effect=lambda action, execute_fn: execute_fn(action)
    )

    @sentinel.guard(tool_name="dummy_tool")
    def dummy_tool(x):
        return x * 2

    result = dummy_tool(x=5)

    assert result == 10
    sentinel.engine.guarded_execute.assert_called_once()


def test_blocked_action_raises_and_prints_reason(sentinel, capsys):
    current_agent_id.set("test-agent")
    current_session_id.set("test-session")
    current_context.set({"original_task": "Test task."})

    blocked_verdict = Verdict(
        action_id="fake-id",
        verdict=VerdictType.BLOCK,
        reason="Blocked for testing.",
        layer="policy_engine",
    )
    sentinel.engine.guarded_execute = MagicMock(
        side_effect=SentinelBlockedError(blocked_verdict)
    )

    @sentinel.guard(tool_name="dummy_tool")
    def dummy_tool(x):
        return x * 2

    with pytest.raises(SentinelBlockedError):
        dummy_tool(x=5)

    captured = capsys.readouterr()
    assert "BLOCKED" in captured.out
    assert "Blocked for testing." in captured.out


def test_action_built_with_correct_tool_name(sentinel):
    current_agent_id.set("agent-42")
    current_session_id.set("session-99")
    current_context.set({"original_task": "Some task."})

    captured_action = {}

    def fake_guarded_execute(action, execute_fn):
        captured_action["action"] = action
        return execute_fn(action)

    sentinel.engine.guarded_execute = MagicMock(side_effect=fake_guarded_execute)

    @sentinel.guard(tool_name="send_email")
    def send_email(to, body):
        return "sent"

    send_email(to="a@b.com", body="hi")

    action = captured_action["action"]
    assert action.tool == "send_email"
    assert action.agent_id == "agent-42"
    assert action.session_id == "session-99"
    assert action.context == {"original_task": "Some task."}
