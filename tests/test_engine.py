from unittest.mock import patch

from agent_sentinel.core.engine import SentinelBlockedError, SentinelEngine
from agent_sentinel.core.types import Action, Source, Verdict, VerdictType


def make_action(**overrides):
    defaults = dict(
        tool="write_file",
        args={"path": "sandbox/out.txt"},
        agent_id="agent-1",
        session_id="session-1",
        source=Source.PYTHON_MIDDLEWARE,
        context={"original_task": "Write output file."},
    )
    defaults.update(overrides)
    return Action(**defaults)


def test_short_circuits_on_policy_block():
    engine = SentinelEngine(config_path="config/default_policy.yaml")
    action = make_action(args={"path": "/etc/passwd"})  # violates scope

    with patch.object(engine.judge, "evaluate") as mock_judge:
        verdict = engine.evaluate(action)
        mock_judge.assert_not_called()  # judge should never be reached

    assert verdict.verdict == VerdictType.BLOCK
    assert verdict.layer == "policy_engine"


def test_short_circuits_on_judge_block():
    engine = SentinelEngine(config_path="config/default_policy.yaml")
    action = make_action()  # passes policy engine

    fake_judge_verdict = Verdict(
        action_id=action.action_id,
        verdict=VerdictType.BLOCK,
        reason="hijacked",
        layer="judge",
    )
    with patch.object(engine.judge, "evaluate", return_value=fake_judge_verdict):
        with patch.object(engine.drift_tracker, "check") as mock_drift:
            verdict = engine.evaluate(action)
            mock_drift.assert_not_called()

    assert verdict.verdict == VerdictType.BLOCK
    assert verdict.layer == "judge"


def test_full_pass_executes_action():
    engine = SentinelEngine(config_path="config/default_policy.yaml")
    action = make_action()

    allow_judge = Verdict(
        action_id=action.action_id,
        verdict=VerdictType.ALLOW,
        reason="ok",
        layer="judge",
    )
    allow_drift = Verdict(
        action_id=action.action_id,
        verdict=VerdictType.ALLOW,
        reason="ok",
        layer="drift_tracker",
    )

    executed = {"called": False}

    def execute_fn(a):
        executed["called"] = True
        return "success"

    with patch.object(engine.judge, "evaluate", return_value=allow_judge):
        with patch.object(engine.drift_tracker, "check", return_value=allow_drift):
            result = engine.guarded_execute(action, execute_fn)

    assert executed["called"] is True
    assert result == "success"


def test_blocked_action_raises():
    engine = SentinelEngine(config_path="config/default_policy.yaml")
    action = make_action(args={"path": "/etc/passwd"})

    def execute_fn(a):
        raise AssertionError("Should never be called")

    try:
        engine.guarded_execute(action, execute_fn)
        assert False, "Expected SentinelBlockedError"
    except SentinelBlockedError:
        pass
