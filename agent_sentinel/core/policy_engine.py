"""
Policy Engine — fast, deterministic rule checks.

This is the first line of defense: no LLM call needed. Checks scope,
blocked domains/commands, and rate limits before anything reaches the
(more expensive) LLM judge.
"""

from __future__ import annotations

import time

import yaml
import os

from agent_sentinel.core.types import (
    Action,
    PolicyConfig,
    PolicyRule,
    Verdict,
    VerdictType,
)


class PolicyEngine:
    def __init__(self, config_path: str):
        self.config: PolicyConfig = self._load_config(config_path)
        # key: f"{agent_id}:{tool}" -> list of timestamps (seconds) of recent calls
        self._rate_limit_window: dict[str, list[float]] = {}

    def _load_config(self, config_path: str) -> PolicyConfig:
        with open(config_path) as f:
            raw = yaml.safe_load(f)
        return PolicyConfig.model_validate(raw)

    def _find_rule(self, tool: str) -> PolicyRule | None:
        for rule in self.config.rules:
            if rule.tool == tool:
                return rule
        return None

    def check(self, action: Action) -> Verdict:
        rule = self._find_rule(action.tool)

        # No rule at all for this tool -> fall back to the configured default.
        if rule is None:
            return Verdict(
                action_id=action.action_id,
                verdict=self.config.default_verdict,
                reason=f"No policy rule defined for tool '{action.tool}'; "
                f"falling back to default verdict.",
                layer="policy_engine",
            )

        # 1. Scope check (applies to args like "path" or "url")
        if rule.allowed_scopes:
            if not self._check_scope(action, rule):
                return Verdict(
                    action_id=action.action_id,
                    verdict=VerdictType.BLOCK,
                    reason=f"Action target is outside allowed scopes {rule.allowed_scopes}.",
                    layer="policy_engine",
                )

        # 2. Blocked domain check (for tools like send_email, call_api)
        if rule.blocked_domains:
            target = str(action.args.get("to") or action.args.get("url") or "")
            for domain in rule.blocked_domains:
                if domain in target:
                    return Verdict(
                        action_id=action.action_id,
                        verdict=VerdictType.BLOCK,
                        reason=f"Target '{target}' matches blocked domain '{domain}'.",
                        layer="policy_engine",
                    )

        # 3. Blocked command substring check (for run_shell_cmd)
        if rule.blocked_commands:
            cmd = str(action.args.get("cmd", ""))
            for blocked in rule.blocked_commands:
                if blocked in cmd:
                    return Verdict(
                        action_id=action.action_id,
                        verdict=VerdictType.BLOCK,
                        reason=f"Command contains blocked pattern '{blocked}'.",
                        layer="policy_engine",
                    )

        # 4. Rate limit check
        if rule.rate_limit_per_minute is not None:
            if not self._check_rate_limit(action, rule):
                return Verdict(
                    action_id=action.action_id,
                    verdict=VerdictType.BLOCK,
                    reason=f"Rate limit exceeded ({rule.rate_limit_per_minute}/min) for tool '{action.tool}'.",
                    layer="policy_engine",
                )

        # All checks passed
        return Verdict(
            action_id=action.action_id,
            verdict=VerdictType.ALLOW,
            reason="Passed all policy engine checks.",
            layer="policy_engine",
        )

    def _check_scope(self, action: Action, rule: PolicyRule) -> bool:
        target = str(action.args.get("path") or action.args.get("url") or "")
        if not target:
            return False

        # For file paths, resolve any ../ traversal before checking scope
        if "path" in action.args:
            normalized = os.path.normpath(target)
            # normpath can still start with ../ if it escapes — check for that explicitly
            if normalized.startswith(".."):
                return False
            return any(normalized.startswith(scope) for scope in rule.allowed_scopes)

        # URLs don't have this traversal issue, keep original logic
        return any(target.startswith(scope) for scope in rule.allowed_scopes)

    def _check_rate_limit(self, action: Action, rule: PolicyRule) -> bool:
        key = f"{action.agent_id}:{action.tool}"
        now = time.time()
        window_start = now - 60  # 1-minute sliding window

        timestamps = self._rate_limit_window.get(key, [])
        # Drop anything older than 60 seconds
        timestamps = [t for t in timestamps if t > window_start]

        if len(timestamps) >= rule.rate_limit_per_minute:
            self._rate_limit_window[key] = timestamps  # save pruned list even on block
            return False

        timestamps.append(now)
        self._rate_limit_window[key] = timestamps
        return True
