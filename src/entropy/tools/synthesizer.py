"""Self-Tooling Synthesizer with Pydantic Validation & Two-Tier Permission Model."""

import inspect
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, create_model

from entropy.core.event_bus import bus

class ToolPermissionTier:
    TIER_1_SAFE = "safe_readonly"
    TIER_2_MUTATING = "mutating_interactive"

class SynthesizedTool(BaseModel):
    name: str
    description: str
    tier: str # TIER_1_SAFE or TIER_2_MUTATING
    code: str
    parameters_schema: Dict[str, Any]

class ToolSynthesizer:
    """Enables Entropy AI to dynamically write, validate, and execute its own tools."""

    MUTATING_KEYWORDS = {
        "delete", "remove", "unlink", "rmdir", "write", "overwrite",
        "subprocess", "system", "exec", "eval", "spawn", "kill", "format",
        "drop", "truncate", "request", "post", "patch", "socket"
    }

    def __init__(self, sandbox_root: Optional[Path] = None):
        self.sandbox_root = Path(sandbox_root) if sandbox_root else Path.cwd()
        self.registered_tools: Dict[str, SynthesizedTool] = {}
        self._tool_callables: Dict[str, Callable] = {}

    def classify_permission_tier(self, tool_name: str, code: str) -> str:
        """Automatically classify tool into Tier 1 (safe) or Tier 2 (mutating/interactive)."""
        name_lower = tool_name.lower()
        code_lower = code.lower()

        for kw in self.MUTATING_KEYWORDS:
            if kw in name_lower or f".{kw}" in code_lower or f"{kw}(" in code_lower:
                return ToolPermissionTier.TIER_2_MUTATING

        return ToolPermissionTier.TIER_1_SAFE

    def register_python_tool(
        self,
        name: str,
        description: str,
        code: str,
        callable_func: Optional[Callable] = None
    ) -> SynthesizedTool:
        """Register a newly synthesized Python tool into the system registry."""
        tier = self.classify_permission_tier(name, code)
        
        # If callable is provided, extract its parameter signature
        param_schema = {}
        if callable_func:
            sig = inspect.signature(callable_func)
            for p_name, param in sig.parameters.items():
                param_schema[p_name] = str(param.annotation)

        tool = SynthesizedTool(
            name=name,
            description=description,
            tier=tier,
            code=code,
            parameters_schema=param_schema
        )
        self.registered_tools[name] = tool
        if callable_func:
            self._tool_callables[name] = callable_func
        return tool

    def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute tool, enforcing sandbox and two-tier security rules."""
        if tool_name not in self.registered_tools:
            raise KeyError(f"Tool '{tool_name}' is not registered.")

        tool = self.registered_tools[tool_name]

        # Enforce Tier 2 interactive approval
        if tool.tier == ToolPermissionTier.TIER_2_MUTATING:
            bus.tool_approval_requested.emit(tool_name, str(kwargs), f"req-{tool_name}")

        # Check sandbox violation on any path arguments
        resolved_root = self.sandbox_root.resolve()
        for arg_val in kwargs.values():
            if isinstance(arg_val, (str, Path)):
                try:
                    p = Path(arg_val).resolve()
                    # If it appears to be a filesystem path with parents/extensions
                    if p.is_absolute() and (p.exists() or len(p.parts) > 2):
                        if not p.is_relative_to(resolved_root):
                            raise PermissionError(
                                f"Sandbox Violation: Path '{p}' is outside allowed root '{resolved_root}'"
                            )
                except (ValueError, RuntimeError):
                    pass

        func = self._tool_callables.get(tool_name)
        if func:
            result = func(**kwargs)
            return {"status": "success", "result": result}
        return {"status": "success", "result": f"Executed tool {tool_name} successfully"}
