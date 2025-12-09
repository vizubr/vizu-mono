#!/usr/bin/env python3
"""Test Google Suite MCP tools directly.

Usage:
    python scripts/test_google_tools.py read_emails
    python scripts/test_google_tools.py query_calendar
    python scripts/test_google_tools.py create_sheet
"""
import sys
import asyncio
import json
from datetime import datetime, timedelta

import httpx
import os

# Use environment variables for sensitive values. Keep defaults non-sensitive placeholders.
MCP_URL = os.getenv("MCP_URL", "http://localhost:8006/mcp")
API_KEY = os.getenv("TEST_GOOGLE_API_KEY", "<set TEST_GOOGLE_API_KEY in .env or CI>")
CLIENTE_ID = os.getenv("TEST_CLIENTE_ID", "<set TEST_CLIENTE_ID in .env or CI>")

async def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """Call an MCP tool via HTTP."""
    # Add cliente_id to arguments (will be injected by the tool)
    arguments["cliente_id"] = CLIENTE_ID

    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        },
        "id": 1
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            MCP_URL,
            json=payload,
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "application/json"
            }
        )
        return resp.json()


async def test_read_emails():
    """Test reading recent emails."""
    print("\n=== Testing read_emails ===")
    result = await call_mcp_tool("read_emails", {
        "query": "is:inbox",
        "max_results": 5
    })
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def test_query_calendar():
    """Test querying calendar events."""
    print("\n=== Testing query_calendar ===")

    # Query events for the next 7 days
    now = datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(days=7)).isoformat() + "Z"

    result = await call_mcp_tool("query_calendar", {
        "time_min": time_min,
        "time_max": time_max,
        "calendar_id": "primary"
    })
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def test_create_sheet():
    """Test writing to a sheet (requires existing spreadsheet ID)."""
    print("\n=== Testing write_to_sheet ===")
    print("NOTE: This requires a valid spreadsheet_id. Creating a new sheet is not yet implemented.")
    print("Skipping this test for now.")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_google_tools.py <test_name>")
        print("Available tests: read_emails, query_calendar, create_sheet")
        return

    test_name = sys.argv[1]

    if test_name == "read_emails":
        await test_read_emails()
    elif test_name == "query_calendar":
        await test_query_calendar()
    elif test_name == "create_sheet":
        await test_create_sheet()
    else:
        print(f"Unknown test: {test_name}")


if __name__ == "__main__":
    asyncio.run(main())
