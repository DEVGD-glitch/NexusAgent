# Task: Live Visualization System for NexusAgent

## Summary

Implemented a brick-by-brick visualization event system that streams real-time events to the frontend as the agent builds things. Three files were created/modified:

### Files Created

1. **`nexus/core/viz_events.py`** — New module providing the visualization event system
   - `VizEventType` enum with 17 event types (FILE_CREATE, CODE_WRITE, BUILD_STEP, etc.)
   - `VizEvent` dataclass for structured event data
   - `VizEventEmitter` class with methods:
     - `emit()` — Core event emission via broadcaster
     - `emit_file_create()` — Emits file creation + line-by-line code writing with visual delay
     - `emit_file_edit()` — Emits file edit with diff preview
     - `emit_command()` — Emits command execution events
     - `emit_build_start/progress/complete()` — Build lifecycle events
     - `emit_artifact()` — HTML/chart/document preview events
     - `emit_file_tree()` — File tree update events
     - `emit_error()` — Error events
     - `get_build_history()` — Get events for a specific build
     - `get_active_build_ids()` — List active builds
   - Global singleton via `get_viz_emitter()`

### Files Modified

2. **`nexus/agents/base.py`** — Integrated VizEmitter into the agent base
   - Added import: `from nexus.core.viz_events import get_viz_emitter, VizEventType`
   - Added `self._viz = None` to `__init__`
   - Added `viz_emitter` lazy property
   - In `run()`: emit `viz_build_start` at start, `viz_build_progress` per step, `viz_build_complete` on success, `viz_error` on failure
   - In `_use_tool()`: emit `viz_file_create` for write_file tools, `viz_code_execute` for code execution tools, `viz_dependency_install` for install_package
   - All viz emissions wrapped in try/except so they never break agent execution

3. **`nexus/api/gateway.py`** — Added Viz endpoints and broadcaster wiring
   - Added `GET /viz/history/{build_id}` — Returns visualization history for a build
   - Added `GET /viz/active` — Returns list of active build IDs with event counts
   - Modified `_get_broadcaster()` to wire up `VizEventEmitter` with the broadcaster on first access

4. **`nexus/core/events.py`** — Added "viz_event" to `VALID_EVENT_TYPES` so viz events are properly broadcast through the WebSocket system
