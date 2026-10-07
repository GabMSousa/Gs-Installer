"""Compatibility adapter for the WinScript manager."""

from src.core.winscript_manager import ScriptExecutionResult, WinScriptManager


class WinScriptService(WinScriptManager):
    pass


__all__ = ["ScriptExecutionResult", "WinScriptManager", "WinScriptService"]
