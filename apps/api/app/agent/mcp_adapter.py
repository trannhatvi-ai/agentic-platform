from __future__ import annotations


class MCPAdapter:
    def format_tool_request(self, tool_name: str, payload: str) -> dict[str, str]:
        return {
            "protocol": "mcp",
            "tool": tool_name,
            "payload": payload,
        }
