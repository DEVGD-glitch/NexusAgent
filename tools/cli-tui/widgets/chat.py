"""
NEXUS TUI — Chat Panel

Provides an interactive chat interface with message history,
input box, and streaming response display.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import httpx
from textual import work
from textual.containers import Container, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, Label, RichLog, Static

# ═══════════════════════════════════════════════════════════════════════
# Chat Bubble Styles
# ═══════════════════════════════════════════════════════════════════════

CHAT_CSS = """
ChatPanel {
    height: 100%;
}

#chat-container {
    height: 100%;
}

#chat-history {
    height: 1fr;
    background: #0a0a0f;
    border: none;
    margin: 0;
    padding: 1;
    overflow-y: auto;
}

#chat-input-container {
    height: 5;
    background: #0f0f1a;
    border-top: solid #1e1e32;
    padding: 1 1;
}

#chat-input {
    background: #14141f;
    color: #e2e8f0;
    border: solid #1e1e32;
    height: 3;
}

#chat-input:focus {
    border: solid #00d4aa;
}

.message-user {
    color: #22c55e;
    text-style: bold;
}

.message-user-content {
    color: #e2e8f0;
}

.message-nexus {
    color: #00d4aa;
    text-style: bold;
}

.message-nexus-content {
    color: #e2e8f0;
}

.message-system {
    color: #64748b;
    text-style: italic;
}

.message-tool {
    color: #f59e0b;
}

.message-error {
    color: #ef4444;
}

.streaming-cursor {
    color: #00d4aa;
    text-style: blink;
}
"""


# ═══════════════════════════════════════════════════════════════════════
# Message Bubble Widget
# ═══════════════════════════════════════════════════════════════════════

class MessageBubble(Static):
    """A single chat message bubble."""

    def __init__(self, role: str, content: str, meta: str = "") -> None:
        super().__init__()
        self._role = role
        self._content = content
        self._meta = meta
        self._prefix = ""

    def on_mount(self) -> None:
        """Render the message when mounted."""
        self._render()

    def _render(self) -> None:
        """Render the message bubble."""
        role = self._role
        content = self._content
        meta = self._meta

        if role == "user":
            prefix = f"[bold #22c55e]┌─ You[/]"
            if meta:
                prefix += f" [dim]{meta}[/]"
            body = f"[#e2e8f0]{content}[/]"
            self.styles.margin = (0, 0, 0, 0)
        elif role == "assistant" or role == "nexus":
            prefix = f"[bold #00d4aa]┌─ NEXUS[/]"
            if meta:
                prefix += f" [dim]{meta}[/]"
            body = f"[#e2e8f0]{content}[/]"
        elif role == "system":
            prefix = f"[dim #64748b]── system ──[/]"
            body = f"[italic #64748b]{content}[/]"
        elif role == "tool":
            prefix = f"[bold #f59e0b]┌─ Tool[/]"
            if meta:
                prefix += f" [dim]{meta}[/]"
            body = f"[#f59e0b]{content[:500]}[/]"
        elif role == "error":
            prefix = f"[bold #ef4444]┌─ Error[/]"
            body = f"[#ef4444]{content}[/]"
        else:
            prefix = f"[bold #64748b]┌─ {role}[/]"
            body = f"[#e2e8f0]{content}[/]"

        self.update(f"{prefix}\n{body}\n")


class StreamingMessage(Static):
    """A message that can be updated incrementally with streamed tokens."""

    def __init__(self) -> None:
        super().__init__()
        self._tokens: list[str] = []
        self._full_content = ""
        self._meta = ""

    def on_mount(self) -> None:
        self._render()

    def add_token(self, token: str) -> None:
        """Append a token to the streaming response."""
        self._tokens.append(token)
        self._full_content = "".join(self._tokens)
        self._render()

    def set_meta(self, meta: str) -> None:
        """Set metadata (provider/model)."""
        self._meta = meta
        self._render()

    def finalize(self, meta: str = "") -> None:
        """Mark streaming as complete."""
        if meta:
            self._meta = meta
        self._render(final=True)

    def _render(self, final: bool = False) -> None:
        """Render the streaming response."""
        prefix = f"[bold #00d4aa]┌─ NEXUS[/]"
        if self._meta:
            prefix += f" [dim]{self._meta}[/]"

        body = f"[#e2e8f0]{self._full_content}[/]"
        cursor = "" if final else " [blink #00d4aa]▊[/]"

        self.update(f"{prefix}\n{body}{cursor}\n")


# ═══════════════════════════════════════════════════════════════════════
# Chat Panel
# ═══════════════════════════════════════════════════════════════════════

class ChatPanel(Container):
    """Chat panel with message history and streaming responses."""

    CSS = CHAT_CSS

    def __init__(self) -> None:
        super().__init__()
        self._conversation: list[dict[str, str]] = []
        self._streaming_message: StreamingMessage | None = None
        self._is_streaming = False

    def compose(self) -> ComposeResult:
        with Vertical(id="chat-container"):
            yield VerticalScroll(id="chat-history")
            with Container(id="chat-input-container"):
                yield Input(
                    placeholder="Type your message here...",
                    id="chat-input",
                )

    def on_mount(self) -> None:
        """Setup after mounting."""
        self._add_system_message(
            "Welcome to NEXUS Agent Terminal Interface.\n"
            "Type a message to start a conversation, or use /help for commands."
        )

    # ── Message Management ─────────────────────────────────────────

    def _add_system_message(self, text: str) -> None:
        """Add a system information message."""
        history = self.query_one("#chat-history", VerticalScroll)
        bubble = MessageBubble("system", text)
        history.mount(bubble)
        history.scroll_end(animate=False)

    def _add_user_message(self, content: str) -> None:
        """Add a user message to the history."""
        history = self.query_one("#chat-history", VerticalScroll)
        bubble = MessageBubble("user", content)
        history.mount(bubble)
        self._conversation.append({"role": "user", "content": content})
        history.scroll_end(animate=False)

    def _start_streaming(self) -> StreamingMessage:
        """Create and mount a streaming message bubble."""
        history = self.query_one("#chat-history", VerticalScroll)
        msg = StreamingMessage()
        history.mount(msg)
        history.scroll_end(animate=False)
        self._streaming_message = msg
        return msg

    def _add_complete_message(self, role: str, content: str, meta: str = "") -> None:
        """Add a complete (non-streamed) message."""
        history = self.query_one("#chat-history", VerticalScroll)
        bubble = MessageBubble(role, content, meta)
        history.mount(bubble)
        self._conversation.append({"role": role, "content": content})
        history.scroll_end(animate=False)

    # ── Input Handling ─────────────────────────────────────────────

    async def send_message(self, message: str) -> None:
        """Send a chat message (called from command bar or local input)."""
        if not message.strip() or self._is_streaming:
            return

        # Also handle commands from chat input
        if message.startswith("/"):
            return

        self._add_user_message(message)

        # Try streaming first, fall back to regular
        try:
            self._is_streaming = True
            stream_msg = self._start_streaming()

            async with httpx.AsyncClient(
                base_url="http://127.0.0.1:8081", timeout=30.0
            ) as client:
                payload = {
                    "messages": self._conversation,
                    "provider": None,
                    "model": None,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                }

                # Attempt streaming
                async with client.stream("POST", "/chat/stream", json=payload) as resp:
                    if resp.status_code == 200:
                        # Stream response
                        provider = "auto"
                        model = "unknown"
                        buffer = ""

                        async for chunk in resp.aiter_bytes():
                            buffer += chunk.decode()
                            while "\n\n" in buffer:
                                event_block, buffer = buffer.split("\n\n", 1)
                                for line in event_block.split("\n"):
                                    if line.startswith("data: "):
                                        try:
                                            data = json.loads(line[6:])
                                            # Handle token vs done
                                            if "token" in data:
                                                stream_msg.add_token(data["token"])
                                                provider = data.get("provider", provider)
                                                model = data.get("model", model)
                                            elif "provider" in data and "token" not in data:
                                                # Done event
                                                provider = data.get("provider", provider)
                                                model = data.get("model", model)
                                                meta = f"({provider}/{model})"
                                                stream_msg.finalize(meta)
                                                self._conversation.append({
                                                    "role": "assistant",
                                                    "content": stream_msg._full_content,
                                                })
                                        except json.JSONDecodeError:
                                            pass

                        # Clean up buffer
                        if buffer.strip():
                            for line in buffer.split("\n"):
                                if line.startswith("data: "):
                                    try:
                                        data = json.loads(line[6:])
                                        if "provider" in data and "token" not in data:
                                            meta = f"({data.get('provider', provider)}/{data.get('model', model)})"
                                            stream_msg.finalize(meta)
                                            self._conversation.append({
                                                "role": "assistant",
                                                "content": stream_msg._full_content,
                                            })
                                    except json.JSONDecodeError:
                                        pass

                    else:
                        # Streaming not available, fall back to regular
                        # Remove the streaming message placeholder
                        if self._streaming_message:
                            self._streaming_message.remove()

                        resp2 = await client.post("/chat", json=payload)
                        if resp2.status_code == 200:
                            data = resp2.json()
                            content = data.get("content", "")
                            provider = data.get("provider", "auto")
                            model = data.get("model", "unknown")
                            meta = f"({provider}/{model})"
                            self._add_complete_message("assistant", content, meta)
                        else:
                            self._add_complete_message(
                                "error",
                                f"Chat request failed: HTTP {resp2.status_code}",
                            )

        except httpx.ConnectError:
            if self._streaming_message:
                self._streaming_message.remove()
                self._streaming_message = None
            self._add_complete_message(
                "error",
                "Cannot connect to NEXUS backend. Ensure the server is running (nexus serve).",
            )
        except Exception as exc:
            if self._streaming_message:
                self._streaming_message.remove()
                self._streaming_message = None
            self._add_complete_message("error", f"Error: {exc}")
        finally:
            self._is_streaming = False
            self._streaming_message = None

    @on(Input.Submitted, "#chat-input")
    async def on_chat_input(self, event: Input.Submitted) -> None:
        """Handle input submitted from the chat input box."""
        inp = self.query_one("#chat-input", Input)
        msg = inp.value.strip()
        inp.clear()

        if not msg:
            return

        if msg.startswith("/"):
            # Pass to parent app command system
            try:
                app = self.app
                if hasattr(app, "_execute_command"):
                    await app._execute_command(msg)
            except Exception:
                pass
            return

        await self.send_message(msg)

    async def refresh_data(self) -> None:
        """Refresh the chat panel (called from external refresh)."""
        pass
