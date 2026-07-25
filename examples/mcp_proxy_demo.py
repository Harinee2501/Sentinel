"""
Demo: a minimal mock upstream MCP server + walkthrough of the proxy
blocking one call and allowing another.

Run in two terminals:
  Terminal 1: python examples/mcp_proxy_demo.py serve-mock   (mock upstream on :9000)
  Terminal 2: agent-sentinel mcp-proxy --upstream http://localhost:9000 --port 8765
  Terminal 3: python examples/mcp_proxy_demo.py call-proxy   (fires two requests at :8765)
"""

import sys

import httpx
import uvicorn
from fastapi import FastAPI

mock_app = FastAPI()


@mock_app.post("/")
async def mock_tool_call(body: dict):
    return {
        "jsonrpc": "2.0",
        "id": body.get("id"),
        "result": {"status": "executed upstream"},
    }


def serve_mock():
    uvicorn.run(mock_app, host="127.0.0.1", port=9000)


def call_proxy():
    proxy_url = "http://127.0.0.1:8765/mcp"

    print("--- Call 1: Allowed — write_file inside sandbox ---")
    resp = httpx.post(
        proxy_url,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "write_file",
                "arguments": {
                    "path": "sandbox/notes.txt",
                    "content": "Meeting notes draft.",
                },
            },
        },
        headers={"X-Original-Task": "Save notes."},
    )
    print(resp.json())

    print("\n--- Call 2: Blocked by Policy Engine — write_file outside sandbox ---")
    resp = httpx.post(
        proxy_url,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "write_file", "arguments": {"path": "/etc/passwd"}},
        },
        headers={"X-Original-Task": "Save notes."},
    )
    print(resp.json())

    print(
        "\n--- Call 3: Blocked by Judge — off-task action passes policy but fails semantic check ---"
    )
    resp = httpx.post(
        proxy_url,
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "send_email",
                "arguments": {
                    "to": "external@gmail.com",
                    "body": "Here is the confidential API key: sk-xxxx-secret",
                },
            },
        },
        headers={"X-Original-Task": "Summarize this week's sales report."},
    )
    print(resp.json())


if __name__ == "__main__":
    if sys.argv[1] == "serve-mock":
        serve_mock()
    elif sys.argv[1] == "call-proxy":
        call_proxy()
