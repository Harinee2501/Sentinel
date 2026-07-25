"""
SentinelEngine — the orchestrator both adaptors call into.
"""

from __future__ import annotations

from collections.abc import Callable

from agent_sentinel.core.audit_log import AuditLog
from agent_sentinel.core.drift_tracker import DriftTracker
from agent_sentinel.core.judge import LLMJudge
from agent_sentinel.core.policy_engine import PolicyEngine
from agent_sentinel.core.types import Action, Verdict, VerdictType


class SentinelBlockedError(Exception):
    """Raised by guarded_execute() when an action is blocked."""

    def __init__(self, verdict: Verdict):
        self.verdict = verdict
        super().__init__(f"Action blocked by {verdict.layer}: {verdict.reason}")


class SentinelEngine:
    def __init__(self, config_path: str = "config/default_policy.yaml"):
        self.policy_engine = PolicyEngine(config_path)
        self.judge = LLMJudge()
        self.drift_tracker = DriftTracker()
        self.audit_log = AuditLog()

    def evaluate(self, action: Action) -> Verdict:
        # 1. Policy engine — cheapest check, runs first
        verdict = self.policy_engine.check(action)
        if verdict.verdict != VerdictType.ALLOW:
            self.audit_log.record(action, verdict)
            return verdict

        # 2. LLM judge — only runs if policy passed
        verdict = self.judge.evaluate(action)
        if verdict.verdict != VerdictType.ALLOW:
            self.audit_log.record(action, verdict)
            return verdict

        # 3. Drift tracker — only runs if judge approved
        verdict = self.drift_tracker.check(action)
        # Note: FLAG still lets the action execute, just gets logged for review
        self.audit_log.record(action, verdict)
        return verdict

    def guarded_execute(
        self, action: Action, execute_fn: Callable[[Action], object]
    ) -> object:
        verdict = self.evaluate(action)

        if verdict.verdict == VerdictType.BLOCK:
            raise SentinelBlockedError(verdict)

        # ALLOW or FLAG both execute; FLAG just means "was logged for review"
        return execute_fn(action)
