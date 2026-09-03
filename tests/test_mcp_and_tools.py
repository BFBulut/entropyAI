"""Automated unit tests for MCP Manager and Dynamic Tool Synthesizer."""

import pytest
from pathlib import Path

from entropy.mcp.manager import MCPManager
from entropy.tools.synthesizer import ToolSynthesizer, ToolPermissionTier

def test_mcp_manager_list():
    mgr = MCPManager()
    servers = mgr.list_servers()
    assert len(servers) >= 3
    server_names = [s["name"] for s in servers]
    assert "StitchMCP" in server_names or "obsidian" in server_names

def test_tool_synthesizer_tier_classification(tmp_path):
    synthesizer = ToolSynthesizer(sandbox_root=tmp_path)

    # Safe Read-Only Tool
    tool_safe = synthesizer.register_python_tool(
        name="calculate_ast_complexity",
        description="Calculate cyclomatic complexity of python file",
        code="def calculate_ast_complexity(file_path: str): return 4",
        callable_func=lambda file_path: 4
    )
    assert tool_safe.tier == ToolPermissionTier.TIER_1_SAFE

    # Mutating / Shell Tool
    tool_mutating = synthesizer.register_python_tool(
        name="delete_orphaned_cache",
        description="Deletes cached bytecode files",
        code="def delete_orphaned_cache(folder: str): os.remove('cache.pyc')",
        callable_func=lambda folder: "deleted"
    )
    assert tool_mutating.tier == ToolPermissionTier.TIER_2_MUTATING

def test_tool_execution_safe(tmp_path):
    synthesizer = ToolSynthesizer(sandbox_root=tmp_path)
    synthesizer.register_python_tool(
        name="add_numbers",
        description="Add two integers",
        code="def add_numbers(a: int, b: int) -> int: return a + b",
        callable_func=lambda a, b: a + b
    )
    res = synthesizer.execute_tool("add_numbers", a=10, b=32)
    assert res["status"] == "success"
    assert res["result"] == 42

def test_tool_sandbox_enforcement(tmp_path):
    synthesizer = ToolSynthesizer(sandbox_root=tmp_path)
    synthesizer.register_python_tool(
        name="read_project_file",
        description="Read file from project",
        code="def read_project_file(path: str): pass",
        callable_func=lambda path: "data"
    )

    # Valid inside sandbox
    inside_file = tmp_path / "valid.txt"
    inside_file.write_text("ok", encoding="utf-8")
    res = synthesizer.execute_tool("read_project_file", path=str(inside_file))
    assert res["status"] == "success"

    # Outside sandbox violation
    outside_file = Path("C:/Windows/System32/drivers/etc/hosts")
    with pytest.raises(PermissionError, match="Sandbox Violation"):
        synthesizer.execute_tool("read_project_file", path=str(outside_file))
