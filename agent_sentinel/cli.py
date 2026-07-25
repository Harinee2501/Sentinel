"""
CLI entrypoint, registered as `agent-sentinel` (see pyproject.toml [project.scripts]).

Usage (once implemented):
    agent-sentinel mcp-proxy --config config/default_policy.yaml --upstream https://example-mcp-server.com
    agent-sentinel dashboard
"""

import typer
import uvicorn

app = typer.Typer(help="Sentinel — runtime guardrail engine for agentic AI systems.")


@app.command()
def mcp_proxy(
    config: str = typer.Option("config/default_policy.yaml", help="Path to policy YAML."),
    upstream: str = typer.Option(..., help="URL of the real upstream MCP server to protect."),
    port: int = typer.Option(8765, help="Local port to run the proxy on."),
):
    """Start the MCP proxy adaptor."""
    from agent_sentinel.adaptors.mcp_proxy import app as mcp_app
    from agent_sentinel.adaptors.mcp_proxy import configure

    configure(config_path=config, upstream_url=upstream)
    uvicorn.run(mcp_app, host="127.0.0.1", port=port)


@app.command()
def dashboard():
    """Launch the Streamlit audit-log dashboard."""
    import subprocess
    import sys

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "agent_sentinel/dashboard/app.py"]
    )


if __name__ == "__main__":
    app()
