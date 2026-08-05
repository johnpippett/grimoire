"""Regression tests for the MCP API used by the Grimoire server."""

import unittest

from mcp.server import Server


class TestMcpCompatibility(unittest.TestCase):
    def test_supported_mcp_release_exposes_grimoire_decorator_api(self) -> None:
        """The server implementation requires the MCP 1.x decorator methods."""
        self.assertTrue(hasattr(Server, "list_tools"))
        self.assertTrue(hasattr(Server, "call_tool"))


if __name__ == "__main__":
    unittest.main()
