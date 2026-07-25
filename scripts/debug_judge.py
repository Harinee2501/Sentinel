"""Quick standalone check of what the judge actually says for one action."""

from agent_sentinel.core.engine import SentinelEngine
from agent_sentinel.core.types import Action, Source

engine = SentinelEngine(config_path="config/default_policy.yaml")

action = Action(
    tool="send_email",
    args={"to": "teammate@company.com", "body": "Here's the weekly update."},
    agent_id="debug-agent",
    session_id="debug-session",
    source=Source.PYTHON_MIDDLEWARE,
    context={"original_task": "Send the weekly update to the team."},
)

verdict = engine.judge.evaluate(action)
print("Verdict:", verdict.verdict)
print("Reason:", verdict.reason)
