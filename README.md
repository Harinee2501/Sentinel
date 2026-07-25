# Sentinel

A framework-agnostic **runtime guardrail engine** for agentic AI systems.

Sentinel sits between an AI agent and every real-world action it tries to take
(sending emails, writing files, calling APIs, running shell commands) and
intercepts each action *before* it executes. Every action is checked against
three layers:

1. **Policy Engine** — fast, deterministic rules (allowed scopes, blocked
   domains/commands, rate limits, path-traversal protection).
2. **LLM Judge** — a separate model call (via Groq) that checks whether the
   action still serves the agent's original task, catching prompt-injection
   / hijacking even when the underlying agent itself was fooled.
3. **Drift Tracker** — embeds the agent's stated sub-goals across a session
   and flags gradual goal drift that no single action looks suspicious
   enough to catch on its own.

Every verdict (`allow` / `block` / `flag`) is logged with a human-readable
reason, viewable on a live Streamlit dashboard.

The **same core engine** is reused across two integration modes:

- **Python Middleware** — a `@sentinel.guard` decorator for agents you build
  yourself (LangChain, CrewAI, raw function-calling).
- **MCP Proxy** — a standalone MCP server that sits between an MCP client
  (Claude Desktop, Claude Code, etc.) and the real upstream MCP servers it's
  connected to, enforcing the same policy at the protocol level.

## Why this exists

Companies are rushing to deploy agents with real permissions — reading
files, sending emails, hitting APIs, executing code. Once an LLM is
manipulated (a poisoned document, a hijacked instruction, subtle goal drift
over a long session), everything downstream trusts it blindly. Sentinel
assumes the underlying model *will* sometimes be fooled, and enforces
boundaries anyway — the same defense-in-depth principle used in production
AI safety systems.

## Demo scenarios

| # | Scenario | Layer that catches it | Verified via |
|---|---|---|---|
| 1 | Scope violation (`write_file` outside sandbox) | Policy Engine | Both adaptors |
| 2 | Prompt injection (hidden instruction in retrieved content) | LLM Judge | Both adaptors |
| 3 | Goal drift over multiple rounds | Drift Tracker | Python Middleware |
| 4 | Path traversal (`sandbox/../../etc/passwd`) | Policy Engine | Unit test |

## Evaluation

Run the red-team evaluation suite yourself:
```bash
python scripts/redteam_eval.py
```
Runs 6 crafted attack scenarios (scope violations, blocked domains/commands,
prompt injection, off-task actions, multi-round goal drift) alongside 3
legitimate actions through the full engine.

**Results (averaged over 3 independent runs):**

| Metric | Value |
|---|---|
| Catch rate | 100% (6/6 attacks caught) |
| False-positive rate | 0% (0/3 legitimate actions blocked) |
| Avg. Policy Engine latency | < 200ms |
| Avg. Judge/Drift latency | 400ms – 2100ms (external API dependent) |

## Project layout
agent-sentinel/
├── agent_sentinel/
│ ├── core/ # Policy Engine, Judge, Drift Tracker, Audit Log, Engine
│ ├── adaptors/ # Python middleware decorator + MCP proxy server
│ ├── dashboard/ # Streamlit live audit-log viewer
│ └── cli.py # agent-sentinel command entrypoint
├── config/
│ └── default_policy.yaml
├── examples/ # Live attack-scenario demo scripts
├── scripts/
│ └── redteam_eval.py # Automated catch-rate / false-positive evaluation
└── tests/ # Unit + integration tests (19 passing)
## Setup

```bash
git clone https://github.com/<your-username>/agent-sentinel.git
cd agent-sentinel
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp .env.example .env        # add your GROQ_API_KEY
```

## Usage

**Guard your own agent's tools:**
```python
from agent_sentinel.adaptors.python_middleware import Sentinel

sentinel = Sentinel(config="config/default_policy.yaml")

@sentinel.guard(tool_name="send_email")
def send_email(to, body):
    ...
```

**Protect MCP-connected tools:**
```bash
agent-sentinel mcp-proxy --config config/default_policy.yaml --upstream https://your-mcp-server.com --port 8765
```

**View the live dashboard:**
```bash
agent-sentinel dashboard
```

## Known limitations

- LLM Judge error handling covers JSON parsing failures; broader API
  failures fail closed but aren't yet independently tested.
- Rate limiting is in-memory only — would need Redis to survive restarts
  or scale across processes.
- The MCP proxy currently intercepts `tools/call` only; other MCP methods
  pass through untouched.
- The semantic judge can itself be fooled by sufficiently subtle attacks —
  a known open problem in AI safety, not something this project claims to
  have solved. Sentinel is one layer of defense-in-depth, not a guarantee.

## License

MIT