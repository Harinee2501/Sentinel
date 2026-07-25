"""
Adaptor 1: Python Middleware.
"""

from __future__ import annotations

import contextvars
import functools
from collections.abc import Callable

from agent_sentinel.core.engine import SentinelBlockedError, SentinelEngine
from agent_sentinel.core.types import Action, Source

# Lets the calling agent loop set "who is making this call, in what session,
# with what task context" without every guarded function needing extra params.
current_agent_id = contextvars.ContextVar("current_agent_id", default="default-agent")
current_session_id = contextvars.ContextVar(
    "current_session_id", default="default-session"
)
current_context = contextvars.ContextVar("current_context", default={})


class Sentinel:
    def __init__(self, config: str = "config/default_policy.yaml"):
        self.engine = SentinelEngine(config_path=config)

    def guard(self, tool_name: str):
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                action = Action(
                    tool=tool_name,
                    args=kwargs if kwargs else {"args": args},
                    agent_id=current_agent_id.get(),
                    session_id=current_session_id.get(),
                    source=Source.PYTHON_MIDDLEWARE,
                    context=current_context.get(),
                )

                def execute_fn(_action: Action):
                    return func(*args, **kwargs)

                try:
                    return self.engine.guarded_execute(action, execute_fn)
                except SentinelBlockedError as e:
                    print(f"🛑 BLOCKED: {tool_name} — {e.verdict.reason}")
                    raise

            return wrapper

        return decorator
