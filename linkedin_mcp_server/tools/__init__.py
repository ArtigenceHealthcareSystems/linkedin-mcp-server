# src/linkedin_mcp_server/tools/__init__.py
"""
LinkedIn scraping tools package.

This package contains the MCP tool implementations for LinkedIn data extraction.
Each tool module provides specific functionality for different LinkedIn entities
while sharing common error handling and driver management patterns.

Available Tools:
- Person tools: LinkedIn profile scraping and analysis
- Company tools: Company profile and information extraction
- Job tools: Job posting details and search functionality
- Messaging tools: Inbox, conversations, search, and sending messages
- Feed tools: Home feed scraping
- Post tools: Global post/content search

Architecture:
- FastMCP integration for MCP-compliant tool registration
- Depends()-based dependency injection for browser/extractor setup
- ToolError-based error handling through centralized raise_tool_error()
- Singleton driver pattern for session persistence
- Structured data return format for consistent MCP responses
"""

from typing import Any


def ensure_clicks_performed(result: dict[str, Any], extractor: Any) -> dict[str, Any]:
    """Ensure every tool result includes the per-call UI action counter."""
    current = result.get("clicks_performed")
    if isinstance(current, int):
        return result

    clicks_performed = getattr(extractor, "clicks_performed", 0)
    if not isinstance(clicks_performed, int):
        clicks_performed = 0

    result["clicks_performed"] = clicks_performed
    return result
