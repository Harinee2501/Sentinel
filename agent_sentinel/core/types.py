"""
Shared data models used across the entire Sentinel engine.

Both adaptors (Python middleware and MCP proxy) convert whatever they
receive into an `Action` object before handing it to the core engine.
This is the single normalization point that lets the policy engine,
judge, and drift tracker be written once and reused everywhere.
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Source(str, Enum):
    """Which adaptor an action came through — used for audit-log filtering."""

    PYTHON_MIDDLEWARE = "python_middleware"
    MCP_PROXY = "mcp_proxy"


class VerdictType(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    FLAG = "flag"  # executes, but logged for human review


class Action(BaseModel):
    """A normalized representation of a single tool call an agent wants to make."""

    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    agent_id: str
    session_id: str
    source: Source
    # Free-form context the judge/drift tracker use, e.g.
    # {"original_task": "...", "history": [...], "round": 3}
    context: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class Verdict(BaseModel):
    """The engine's decision on a given Action, plus why."""

    action_id: str
    verdict: VerdictType
    reason: str
    # Which layer produced this verdict — useful for the dashboard/debugging
    layer: str  # "policy_engine" | "judge" | "drift_tracker"
    latency_ms: float | None = None


class PolicyRule(BaseModel):
    """A single rule loaded from the YAML policy config."""

    tool: str
    allowed_scopes: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=list)
    blocked_commands: list[str] = Field(default_factory=list)
    rate_limit_per_minute: int | None = None


class PolicyConfig(BaseModel):
    """The full parsed policy.yaml."""

    rules: list[PolicyRule] = Field(default_factory=list)
    default_verdict: VerdictType = VerdictType.BLOCK  # fail closed by default
