import pytest

from agent_sentinel.core.policy_engine import PolicyEngine
from agent_sentinel.core.types import Action, Source, VerdictType


@pytest.fixture
def engine():
    return PolicyEngine(config_path="config/default_policy.yaml")


def make_action(tool, args, agent_id="agent-1"):
    return Action(
        tool=tool,
        args=args,
        agent_id=agent_id,
        session_id="session-1",
        source=Source.PYTHON_MIDDLEWARE,
    )


def test_allowed_write_within_sandbox(engine):
    action = make_action("write_file", {"path": "sandbox/notes.txt"})
    verdict = engine.check(action)
    assert verdict.verdict == VerdictType.ALLOW


def test_blocked_write_outside_sandbox(engine):
    action = make_action("write_file", {"path": "/etc/passwd"})
    verdict = engine.check(action)
    assert verdict.verdict == VerdictType.BLOCK
    assert "scope" in verdict.reason.lower()


def test_blocked_shell_command(engine):
    action = make_action("run_shell_cmd", {"cmd": "rm -rf /"})
    verdict = engine.check(action)
    assert verdict.verdict == VerdictType.BLOCK


def test_rate_limit_exceeded(engine):
    # send_email allows 5/minute — fire 6 in a row
    for _ in range(5):
        verdict = engine.check(
            make_action("send_email", {"to": "a@b.com", "body": "hi"})
        )
        assert verdict.verdict == VerdictType.ALLOW
    verdict = engine.check(make_action("send_email", {"to": "a@b.com", "body": "hi"}))
    assert verdict.verdict == VerdictType.BLOCK
    assert "rate limit" in verdict.reason.lower()


def test_unknown_tool_falls_back_to_default(engine):
    action = make_action("delete_database", {})
    verdict = engine.check(action)
    assert verdict.verdict == engine.config.default_verdict  # block


def test_blocked_path_traversal(engine):
    action = make_action("write_file", {"path": "sandbox/../../etc/passwd"})
    verdict = engine.check(action)
    assert verdict.verdict == VerdictType.BLOCK
