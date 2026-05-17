# NEXUS Hooks — Built-in hook implementations
#
# This package contains the built-in hook handlers that are registered
# by default when HookEngine.initialize() is called:
#
#   audit_hook.py      — Records tool calls to the audit trail
#   permission_hook.py — Enforces security policies at key lifecycle points
#   logging_hook.py    — Logs all events at DEBUG level for observability
#
# Each module exposes a create_*_hook_handlers() factory function that
# returns the handler callable(s) ready for registration.
