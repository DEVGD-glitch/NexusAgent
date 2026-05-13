"""
NEXUS Visualization Events — Brick-by-brick build streaming

Emits real-time events as the agent creates/modifies files, runs code, etc.
Think of it like z.ai in agent mode — you see each file being created,
each line of code being written, step by step.
"""
from __future__ import annotations
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class VizEventType(str, Enum):
    FILE_CREATE = "viz_file_create"
    FILE_EDIT = "viz_file_edit"
    FILE_DELETE = "viz_file_delete"
    DIR_CREATE = "viz_dir_create"
    CODE_WRITE = "viz_code_write"       # Line-by-line code writing
    CODE_EXECUTE = "viz_code_execute"
    COMMAND_RUN = "viz_command_run"
    BUILD_STEP = "viz_build_step"
    BUILD_COMPLETE = "viz_build_complete"
    DEPENDENCY_INSTALL = "viz_dependency_install"
    TEST_RUN = "viz_test_run"
    DEPLOY_START = "viz_deploy_start"
    ARTIFACT_RENDER = "viz_artifact_render"  # HTML/chart/document preview
    PROGRESS = "viz_progress"
    DIFF_PREVIEW = "viz_diff_preview"
    FILE_TREE_UPDATE = "viz_file_tree_update"
    ERROR = "viz_error"


@dataclass
class VizEvent:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: VizEventType = field(default=VizEventType.PROGRESS)
    timestamp: float = field(default_factory=time.time)
    title: str = ""
    detail: str = ""
    path: Optional[str] = None
    content: Optional[str] = None
    language: Optional[str] = None
    diff: Optional[dict] = None        # {old: str, new: str}
    progress: float = 0.0              # 0.0 to 1.0
    status: str = "pending"            # pending, running, completed, error
    artifact: Optional[dict] = None    # {type: "html"|"chart"|"image", content: str}
    metadata: dict = field(default_factory=dict)


class VizEventEmitter:
    """Emits visualization events via the broadcaster."""
    
    def __init__(self, broadcaster=None):
        self._broadcaster = broadcaster
        self._active_builds: dict[str, list[VizEvent]] = {}
        
    def set_broadcaster(self, broadcaster):
        self._broadcaster = broadcaster
    
    async def emit(self, event: VizEvent):
        """Emit a visualization event to all connected clients."""
        if self._broadcaster:
            await self._broadcaster.broadcast("viz_event", {
                "id": event.id,
                "type": event.type.value,
                "timestamp": event.timestamp,
                "title": event.title,
                "detail": event.detail,
                "path": event.path,
                "content": event.content,
                "language": event.language,
                "diff": event.diff,
                "progress": event.progress,
                "status": event.status,
                "artifact": event.artifact,
                "metadata": event.metadata,
            })
        # Track in active builds
        build_id = event.metadata.get("build_id", "default")
        if build_id not in self._active_builds:
            self._active_builds[build_id] = []
        self._active_builds[build_id].append(event)
    
    async def emit_file_create(self, path: str, content: str, language: str = "", build_id: str = "default"):
        """Emit a file creation event with content."""
        event = VizEvent(
            type=VizEventType.FILE_CREATE,
            title=f"Creating {path.split('/')[-1]}",
            detail=f"Creating file: {path}",
            path=path,
            content=content,
            language=language,
            status="running",
            metadata={"build_id": build_id},
        )
        await self.emit(event)
        # Then emit line-by-line code writing
        lines = content.split('\n')
        for i, line in enumerate(lines):
            code_event = VizEvent(
                type=VizEventType.CODE_WRITE,
                title=f"Writing {path.split('/')[-1]}",
                detail=line,
                path=path,
                content=line,
                progress=(i + 1) / len(lines),
                status="running",
                metadata={"build_id": build_id, "line": i + 1},
            )
            await self.emit(code_event)
            await asyncio.sleep(0.02)  # Small delay for visual effect
        # Mark complete
        complete_event = VizEvent(
            type=VizEventType.FILE_CREATE,
            title=f"Created {path.split('/')[-1]}",
            path=path,
            progress=1.0,
            status="completed",
            metadata={"build_id": build_id},
        )
        await self.emit(complete_event)
    
    async def emit_file_edit(self, path: str, old_content: str, new_content: str, language: str = "", build_id: str = "default"):
        """Emit a file edit with diff preview."""
        event = VizEvent(
            type=VizEventType.FILE_EDIT,
            title=f"Editing {path.split('/')[-1]}",
            path=path,
            diff={"old": old_content, "new": new_content},
            language=language,
            status="completed",
            metadata={"build_id": build_id},
        )
        await self.emit(event)
    
    async def emit_command(self, command: str, output: str = "", exit_code: int = 0, build_id: str = "default"):
        """Emit a command execution event."""
        event = VizEvent(
            type=VizEventType.COMMAND_RUN,
            title=f"$ {command[:50]}",
            detail=command,
            content=output[:2000],
            metadata={"exit_code": exit_code, "build_id": build_id},
            status="completed" if exit_code == 0 else "error",
        )
        await self.emit(event)
    
    async def emit_build_start(self, build_id: str, description: str = ""):
        """Emit build start event."""
        self._active_builds[build_id] = []
        event = VizEvent(
            type=VizEventType.BUILD_STEP,
            title="Build started",
            detail=description,
            progress=0.0,
            status="running",
            metadata={"build_id": build_id},
        )
        await self.emit(event)
    
    async def emit_build_progress(self, build_id: str, step: str, progress: float):
        """Emit build progress."""
        event = VizEvent(
            type=VizEventType.BUILD_STEP,
            title=step,
            progress=progress,
            status="running",
            metadata={"build_id": build_id},
        )
        await self.emit(event)
    
    async def emit_build_complete(self, build_id: str, summary: str = ""):
        """Emit build complete event."""
        event = VizEvent(
            type=VizEventType.BUILD_COMPLETE,
            title="Build complete",
            detail=summary,
            progress=1.0,
            status="completed",
            metadata={"build_id": build_id, "total_events": len(self._active_builds.get(build_id, []))},
        )
        await self.emit(event)
        if build_id in self._active_builds:
            del self._active_builds[build_id]
    
    async def emit_artifact(self, artifact_type: str, content: str, title: str = "", build_id: str = "default"):
        """Emit a renderable artifact (HTML, chart, image)."""
        event = VizEvent(
            type=VizEventType.ARTIFACT_RENDER,
            title=title or f"{artifact_type} preview",
            artifact={"type": artifact_type, "content": content},
            metadata={"build_id": build_id},
        )
        await self.emit(event)
    
    async def emit_file_tree(self, tree: dict, build_id: str = "default"):
        """Emit an updated file tree."""
        event = VizEvent(
            type=VizEventType.FILE_TREE_UPDATE,
            title="File tree updated",
            metadata={"tree": tree, "build_id": build_id},
        )
        await self.emit(event)
    
    async def emit_error(self, error: str, path: str = "", build_id: str = "default"):
        """Emit an error event."""
        event = VizEvent(
            type=VizEventType.ERROR,
            title="Error",
            detail=error,
            path=path,
            status="error",
            metadata={"build_id": build_id},
        )
        await self.emit(event)
    
    def get_build_history(self, build_id: str) -> list[VizEvent]:
        """Get events for a specific build."""
        return self._active_builds.get(build_id, [])
    
    def get_active_build_ids(self) -> list[str]:
        """Get list of active build IDs."""
        return list(self._active_builds.keys())


# Global singleton
_viz_emitter: VizEventEmitter | None = None

def get_viz_emitter() -> VizEventEmitter:
    global _viz_emitter
    if _viz_emitter is None:
        _viz_emitter = VizEventEmitter()
    return _viz_emitter
