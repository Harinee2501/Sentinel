from agent_sentinel.core.engine import SentinelEngine
from agent_sentinel.core.types import Action, Source

engine = SentinelEngine(config_path="config/default_policy.yaml")

action = Action(
    tool="send_email",
    args={"to": "manager@company.com", "body": "Budget report attached as requested."},
    agent_id="debug-agent",
    session_id="debug-session",
    source=Source.PYTHON_MIDDLEWARE,
    context={"original_task": "Send the budget report to my manager."},
)

for i in range(5):
    verdict = engine.judge.evaluate(action)
    print(f"Run {i + 1}: {verdict.verdict.value} — {verdict.reason}")
