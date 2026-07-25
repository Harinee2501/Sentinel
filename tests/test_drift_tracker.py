from agent_sentinel.core.drift_tracker import DriftTracker
from agent_sentinel.core.types import Action, Source, VerdictType


def make_action(session_id, original_task, current_subgoal):
    return Action(
        tool="write_file",
        args={"path": "/sandbox/out.txt"},
        agent_id="agent-1",
        session_id=session_id,
        source=Source.PYTHON_MIDDLEWARE,
        context={"original_task": original_task, "current_subgoal": current_subgoal},
    )


def test_no_drift_within_threshold():
    tracker = DriftTracker(drift_threshold=0.3)
    action = make_action(
        "session-a",
        "Write a summary of the meeting notes.",
        "Drafting the summary paragraph for the meeting notes.",
    )
    verdict = tracker.check(action)
    assert verdict.verdict == VerdictType.ALLOW


def test_flags_significant_drift():
    tracker = DriftTracker(drift_threshold=0.5)
    action = make_action(
        "session-b",
        "Write a summary of the meeting notes.",
        "Booking a flight to Paris for next week.",
    )
    verdict = tracker.check(action)
    assert verdict.verdict == VerdictType.FLAG


def test_reset_session_clears_history():
    tracker = DriftTracker()
    tracker.check(make_action("session-c", "Task A.", "Task A."))
    assert "session-c" in tracker._session_history
    tracker.reset_session("session-c")
    assert "session-c" not in tracker._session_history
