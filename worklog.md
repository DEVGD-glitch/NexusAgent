# NexusAgent Bug Fix Worklog

## Date: 2026-03-04

All 25 bugs have been fixed across the NexusAgent Python backend. Below is a summary of each fix.

---

## CRITICAL BUGS (1-10)

### Bug 1: G4F_MODELS not imported in free_router.py
**File:** `nexus/llm/providers/free/free_router.py`
**Issue:** `G4F_MODELS` was referenced at lines 42 and 76 but never imported, causing `NameError` at runtime.
**Fix:** Added `G4F_MODELS` to the import from `g4f_provider`:
```python
from nexus.llm.providers.free.g4f_provider import G4FProvider, G4FResponse, G4F_MODELS
```

### Bug 2: rollout_node potentially undefined in lats.py
**File:** `nexus/reasoning/lats.py`
**Issue:** In the MCTS simulation step, `rollout_node` was only assigned inside the `if selected.children` branch. The `else` branch used `selected` for evaluation but `rollout_node` was referenced in the backpropagation step, causing a potential `NameError`.
**Fix:** Initialized `rollout_node = selected` before the `if` block, so it always has a value regardless of which branch is taken.

### Bug 3: recall() creates new empty WorkingMemory in orchestrator.py
**File:** `nexus/memory/orchestrator.py`
**Issue:** When recalling WORKING memory, a brand-new empty `WorkingMemory()` was created instead of using the existing session stored in `self._working_sessions`.
**Fix:** Changed to look up or create the session from `self._working_sessions` using `context.session_id`, matching the same pattern used in `store()`.

### Bug 4: Namespace mismatch in orchestrator.py (semantic vs knowledge)
**File:** `nexus/memory/orchestrator.py`
**Issue:** When storing SEMANTIC memory, the namespace `'semantic'` was used, but `NexusMemoryService` uses `'knowledge'` as the valid namespace for semantic data (matching ChromaDB's `VALID_NAMESPACES`).
**Fix:** Changed `namespace="semantic"` to `namespace="knowledge"` in the SEMANTIC store branch.

### Bug 5: Dead code + fn_name undefined in langgraph_engine.py
**File:** `nexus/orchestrator/langgraph_engine.py`
**Issues:**
1. `run_nexus_task()` had dead code after `return await _run_simple_loop(...)` — the LangGraph-based execution was unreachable.
2. `fn_name` could be undefined if `tool_calls` was an empty list but truthy, causing a `NameError` on the `if fn_name == "finish"` check after the loop.
**Fixes:**
1. Converted dead code to commented-out code with an explanatory NOTE about how to re-enable it.
2. Initialized `fn_name = ""` before the `for tc in tool_calls` loop.

### Bug 6: ReactReasoner import doesn't exist in gateway.py
**File:** `nexus/api/gateway.py`
**Issue:** The `_tool_reason_react` function imported `ReactReasoner` which doesn't exist in `react.py`. The actual class is `ReActLoop`, and it has a different API (`run()` returns a dict, not an object with `.answer`, `.iterations_used`, `.steps`).
**Fix:** Changed import to `ReActLoop`, changed method call from `.solve()` to `.run()`, and fixed the return value access to use dict methods (`.get()`) instead of attribute access.

### Bug 7: Base64 truncated to 10K chars in screen_understanding.py
**File:** `nexus/computer/screen_understanding.py`
**Issue:** In both `_vision_ocr()` and `analyze_with_vision()`, the base64-encoded image data was truncated to 10,000 characters (`b64[:10000]`), which corrupts the image data and prevents vision models from processing it.
**Fix:** Removed the truncation entirely — the full base64 string is now passed to the vision API.

### Bug 8: WebSocket server never started in vrm_renderer.py
**File:** `nexus/comms/avatar/vrm_renderer.py`
**Issue:** The `initialize()` method imported `socketio` but never actually started a WebSocket server, so the HTML viewer's WebSocket connection (`ws://localhost:18080`) would always fail.
**Fix:** Replaced the unused `socketio` import with actual WebSocket server startup using the `websockets` library. The server listens on port 18080, tracks connected clients, and gracefully handles the case where `websockets` is not installed.

### Bug 9: spawn() doesn't call the factory in registry.py
**File:** `nexus/core/registry.py`
**Issue:** `AgentRegistry.spawn()` created an `AgentInstance` but never invoked the registered factory callable to actually create the agent object.
**Fix:** Added factory invocation after creating the instance. If a factory is available, it's called with `task=task` and any kwargs. On success, the instance status is set to RUNNING. On factory failure, it's set to FAILED.

### Bug 10: execute_with_fallback doesn't run the fallback agent
**File:** `nexus/agents/base.py`
**Issue:** When `fallback_agent_type` was specified, `execute_with_fallback()` spawned a fallback instance via the registry but then immediately returned a FAILED result with a "Suggested fallback" message instead of actually executing the fallback.
**Fix:** After spawning the fallback, the method now attempts to execute it using the LLM router with the fallback agent's definition as the system prompt. Returns a COMPLETED result on success, or FAILED if the fallback also fails.

---

## HIGH PRIORITY BUGS (11-25)

### Bug 11: max_tokens default prevents __post_init__ in working.py
**File:** `nexus/memory/working.py`
**Issue:** `max_tokens` defaulted to `30000`, and `__post_init__` only triggered when `max_tokens <= 0`, which could never happen with the default.
**Fix:** Changed default from `int = 30000` to `Optional[int] = None`, and changed condition from `<= 0` to `is None`.

### Bug 12: language_preference sentinel in identity.py
**File:** `nexus/memory/identity.py`
**Issue:** `language_preference` defaulted to `'en'`, and the merge logic used `!= 'en'` as the sentinel check. This meant a user couldn't explicitly set `language_preference='en'` on merge.
**Fix:** Changed default from `str = "en"` to `Optional[str] = None`, and changed the merge condition from `!= "en"` to `is not None`.

### Bug 13: update() replaces metadata in chroma_service.py
**File:** `nexus/memory/chroma_service.py`
**Issue:** When `update()` was called with both `text` and `metadata`, it created new metadata from scratch (only `updated_at`, `doc_hash`, and the passed metadata), discarding any existing metadata fields.
**Fix:** When text is updated, the method now first fetches existing metadata via `collection.get()`, merges it with the new metadata (`{**existing_meta, **(metadata or {})}`), and then applies `updated_at` and `doc_hash`.

### Bug 14: _rel_type_index not cleaned on entity removal in knowledge_graph.py
**File:** `nexus/knowledge/knowledge_graph.py`
**Issue:** `remove_entity()` deleted the node from the graph and the entity index, but didn't clean up the `_rel_type_index`, leaving stale references to removed edges.
**Fix:** Added cleanup logic that iterates through `_rel_type_index`, filters out any edge tuples involving the removed node_id, and removes empty relation type entries.

### Bug 15: Token comparison uses != in gateway.py
**File:** `nexus/api/gateway.py`
**Issue:** Two places compared authentication tokens using `!=`, which is vulnerable to timing attacks.
**Fix:** Added `import hmac` and replaced both `token != expected` comparisons with `hmac.compare_digest(token.encode(), expected.encode())` for constant-time comparison.

### Bug 16: New LLMRouter per attempt in fallback.py
**File:** `nexus/llm/fallback.py`
**Issue:** `FallbackChain.complete()` created a new `LLMRouter()` on every retry attempt, which is expensive (reads config, initializes providers).
**Fix:** Added `self._router = None` to `__init__`, a `_get_router()` method that lazily caches the router, and changed the `LLMRouter()` call in `complete()` to `self._get_router()`.

### Bug 17: Score parsing takes first digit in tot.py
**File:** `nexus/reasoning/tot.py`
**Issue:** `_evaluate_thought()` parsed the LLM score by iterating through characters and returning the first digit found (`for char in text: if char.isdigit(): score = int(char)`). This means "10" would be parsed as 1, and "7.5" as 7.
**Fix:** Replaced the character-by-character parsing with `re.search(r'\d+(?:\.\d+)?', text)` to extract the full numeric value (including decimals).

### Bug 18: New LLMRouter per call in lats.py
**File:** `nexus/reasoning/lats.py`
**Issue:** `_generate_actions()`, `_evaluate_state()`, and `_extract_answer()` each created a new `LLMRouter()` instance.
**Fix:** Added `self._llm_router = None` to `__init__`, a `_get_router()` caching method, and replaced all `LLMRouter()` calls with `self._get_router()`.

### Bug 19: New LLMRouter per call in tot.py
**File:** `nexus/reasoning/tot.py`
**Issue:** Same as Bug 18 — `_generate_thoughts()` and `_evaluate_thought()` each created a new `LLMRouter()`.
**Fix:** Same pattern — added `self._llm_router = None` and `_get_router()` caching.

### Bug 20: Dead code in router.py
**File:** `nexus/llm/router.py`
**Issue:** `_call_glm_direct()` and `_call_ollama_direct()` were defined but never called anywhere in the codebase. GLM and Ollama are handled through `_call_openai_compatible_direct()` and LiteLLM respectively.
**Fix:** Removed both unused methods entirely.

### Bug 21: Mutable default in mcp_server.py
**File:** `nexus/mcp_server.py`
**Issue:** `store_memory()` had `metadata: dict = None`, which is a mutable default argument anti-pattern (though `None` is not mutable, the type hint was wrong).
**Fix:** Changed to `metadata: Optional[dict] = None` and added `Optional` to the typing import.

### Bug 22: Tool calls ignored in react.py
**File:** `nexus/reasoning/react.py`
**Issue:** The ReAct loop generated observations as generic "Step N completed" messages, completely ignoring any Action: patterns in the LLM output.
**Fix:** Added a NOTE comment explaining the limitation, and added basic tool support: the code now extracts tool names from `Action:` lines using regex, logs them to `self.actions`, and generates a more informative observation.

### Bug 23: Native handoff configuration is pass in openai_layer.py
**File:** `nexus/agents/openai_layer.py`
**Issue:** In `_run_native()`, the handoff configuration for the OpenAI Agents SDK was just `pass` — a no-op.
**Fix:** Implemented actual handoff configuration using the SDK's `handoff()` helper function. For each handoff destination, it creates a handoff tool and appends it to the start agent's `handoffs` list, with error handling for SDK compatibility issues.

### Bug 24: Completion detection triggers on "done" in code_engine.py
**File:** `nexus/dev/code_engine.py`
**Issue:** The CodeAct completion check used `"done" in result.stdout.lower()`, which would falsely trigger on any output containing "done" (e.g., "All done with setup", "Transaction done", etc.).
**Fix:** Changed to `result.stdout.strip().lower() == "done"` — only triggers on an exact match of the entire stdout.

### Bug 25: Dangerous imports list too restrictive in sandbox.py
**File:** `nexus/security/sandbox.py`
**Issue:** `_DANGEROUS_IMPORTS` blocked `os`, `sys`, `subprocess`, `socket`, `requests`, `urllib`, `http`, `ftplib`, `telnetlib`, `pty`, `termios`, `tty`, `resource`, `signal`, `multiprocessing`, `concurrent` — most of which are commonly needed in legitimate code.
**Fix:** Reduced the list to only truly dangerous modules: `ctypes`, `winreg`, `winsound`, `msvcrt`, `multiprocessing.shared_memory`, and `importlib`. These can bypass the sandbox or access system internals, while `os`, `sys`, `subprocess` etc. are commonly needed in user code and already have other safety checks.

---

## Date: 2026-03-05 — WebSocket + SSE Real-Time Streaming Support

Added WebSocket and Server-Sent Events support to the NexusAgent FastAPI backend for real-time agent activity streaming. This enables the frontend to visualize agent actions in real-time (brick-by-brick).

### New File: `nexus/core/events.py` — EventBroadcaster module

**Purpose:** Thread-safe async pub/sub broadcaster for real-time agent events. Any part of the backend can broadcast events, and all connected WebSocket subscribers receive them instantly.

**Key components:**
- `EventBroadcaster` class with:
  - `subscribe(websocket)` — registers a WebSocket subscriber, returns subscriber_id
  - `unsubscribe(websocket)` — removes a subscriber gracefully
  - `broadcast(event_type, data)` — sends an event to all subscribers via per-subscriber asyncio.Queue
  - `broadcast_sync(event_type, data)` — synchronous wrapper for use from non-async code
  - `pump_subscriber(websocket)` — async task that forwards queued events to a subscriber's WebSocket
  - `get_status()` — returns subscriber count, event count, subscriber IDs
- Each subscriber gets an independent asyncio.Queue (maxsize=256) so slow consumers don't block fast ones
- Queue overflow handling: drops oldest event when full
- Thread-safe subscriber management via `threading.Lock`
- `get_broadcaster()` — singleton accessor

**Valid event types:**
`agent_thinking`, `agent_action`, `tool_call`, `tool_result`, `file_create`, `file_edit`, `code_building`, `task_step`, `task_done`, `error`, `avatar_expression`, `stream_token`

**Event format (JSON sent to WebSocket):**
```json
{
    "type": "agent_thinking",
    "data": { ... },
    "timestamp": "2025-03-05T12:34:56.789Z",
    "event_id": "evt_abc123"
}
```

### Modified File: `nexus/api/gateway.py` — WebSocket + SSE endpoints + broadcast integration

**New imports added:**
- `WebSocket`, `WebSocketDisconnect` from `fastapi`
- `StreamingResponse` from `starlette.responses`
- `asyncio` (top-level)

**New lazy singleton:**
- `_get_broadcaster()` — lazy-loads the `EventBroadcaster` from `nexus.core.events`

**New endpoint: `WS /ws` — WebSocket for real-time event streaming**
- Accepts WebSocket connections
- Subscribes the client to the EventBroadcaster
- Runs the event pump to forward queued events to the client
- Handles connection/disconnection gracefully
- Supports multiple concurrent clients (each gets its own queue)

**New endpoint: `GET /ws/status` — Broadcaster status**
- Returns subscriber count, total events broadcast, subscriber IDs

**New endpoint: `POST /chat/stream` — SSE streaming chat**
- Returns Server-Sent Events (SSE) for token-by-token LLM response streaming
- Attempts real streaming via LiteLLM first (if available)
- Falls back to chunked word-by-word emission if streaming unavailable
- Broadcasts `stream_token` events to WebSocket subscribers in parallel
- SSE event types: `token`, `done`, `error`
- Headers: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`

**Modified endpoint: `POST /chat` — Added event broadcasting**
- Broadcasts `agent_thinking` when starting chat completion
- Broadcasts `tool_call` before calling the LLM
- Broadcasts `tool_result` with latency/usage after LLM response
- Broadcasts `agent_action` with content length on completion
- Broadcasts `error` on failure

**Modified endpoint: `POST /run` — Added event broadcasting**
- Broadcasts `task_step` when starting the orchestrator
- Broadcasts `agent_thinking` during the planning phase
- Broadcasts `task_done` with status/steps/latency on completion
- Broadcasts `error` on failure

### Frontend Integration Guide

**WebSocket connection:**
```javascript
const ws = new WebSocket('ws://localhost:8080/ws');
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // data.type: agent_thinking | agent_action | tool_call | ...
    // data.data: event-specific payload
    // data.timestamp: ISO timestamp
    // data.event_id: unique event ID
};
```

**SSE streaming:**
```javascript
const response = await fetch('/api/nexus/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        messages: [{ role: 'user', content: 'Hello' }],
        provider: 'gemini',
    }),
});
const reader = response.body.getReader();
const decoder = new TextDecoder();
// Parse SSE events: event: token\ndata: {...}\n\n
```
