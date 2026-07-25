"""
Adaptor 2: MCP Proxy.
"""

from __future__ import annotations

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agent_sentinel.core.engine import SentinelBlockedError, SentinelEngine
from agent_sentinel.core.types import Action, Source

app = FastAPI(title="Sentinel MCP Proxy")

_engine: SentinelEngine | None = None
_upstream_url: str | None = None


def configure(config_path: str, upstream_url: str) -> None:
    global _engine, _upstream_url
    _engine = SentinelEngine(config_path=config_path)
    _upstream_url = upstream_url


@app.post("/mcp")
async def handle_mcp_request(request: Request):
    body = await request.json()
    method = body.get("method")

    # Only intercept tool calls; let everything else (tools/list, etc.) pass through.
    if method != "tools/call":
        return await _forward(body)

    params = body.get("params", {})
    tool_name = params.get("name", "unknown_tool")
    tool_args = params.get("arguments", {})

    action = Action(
        tool=tool_name,
        args=tool_args,
        agent_id=request.headers.get("X-Agent-Id", "mcp-client"),
        session_id=request.headers.get("X-Session-Id", "mcp-session"),
        source=Source.MCP_PROXY,
        context={"original_task": request.headers.get("X-Original-Task", "")},
    )

    try:
        _engine.guarded_execute(action, execute_fn=lambda a: None)
    except SentinelBlockedError as e:
        return JSONResponse(
            status_code=200,  # JSON-RPC errors are still HTTP 200
            content={
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {
                    "code": -32000,
                    "message": f"Blocked by Sentinel ({e.verdict.layer}): {e.verdict.reason}",
                },
            },
        )

    return await _forward(body)


async def _forward(body: dict):
    async with httpx.AsyncClient() as client:
        response = await client.post(_upstream_url, json=body, timeout=30.0)
    return JSONResponse(status_code=response.status_code, content=response.json())
