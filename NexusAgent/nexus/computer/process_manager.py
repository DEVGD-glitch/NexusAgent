"""
NEXUS Process Manager — Launch, kill, and monitor applications.

Provides process management capabilities:
  - Launch processes (with optional sandboxing)
  - Kill processes (by PID or name)
  - List running processes
  - Monitor process resource usage
  - Service management (start/stop/status)
  - Integration with Docker for sandboxed execution

All process operations use asyncio.subprocess for async execution.

Usage:
    from nexus.computer.process_manager import ProcessManager

    pm = ProcessManager()
    result = await pm.launch("python script.py")
    processes = await pm.list_processes()
    await pm.kill(pid=12345)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import signal
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from nexus.core.config import get_settings
from nexus.core.exceptions import NexusError

logger = logging.getLogger(__name__)

CURRENT_PLATFORM = platform.system().lower()


# ── Exceptions ─────────────────────────────────────────────────────

class ProcessError(NexusError):
    """Raised when a process operation fails."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, code="PROCESS_ERROR", details=details)


# ── Data Structures ────────────────────────────────────────────────

@dataclass
class ProcessInfo:
    """Information about a running process."""
    pid: int
    name: str = ""
    command: str = ""
    status: str = "unknown"
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    create_time: float = 0.0
    username: str = ""
    is_sandboxed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "name": self.name,
            "command": self.command[:500],
            "status": self.status,
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_mb": round(self.memory_mb, 2),
            "create_time": self.create_time,
            "username": self.username,
            "is_sandboxed": self.is_sandboxed,
        }


@dataclass
class ProcessResult:
    """Result from a completed process."""
    pid: int
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    execution_time_ms: float = 0.0
    command: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:5000],
            "stderr": self.stderr[:2000],
            "timed_out": self.timed_out,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "command": self.command[:200],
        }


@dataclass
class ServiceStatus:
    """Status of a system service."""
    name: str
    running: bool = False
    pid: Optional[int] = None
    status_text: str = ""
    uptime_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "running": self.running,
            "pid": self.pid,
            "status_text": self.status_text,
            "uptime_seconds": round(self.uptime_seconds, 2),
        }


# ── Process Manager ───────────────────────────────────────────────

class ProcessManager:
    """
    Process management for launching, killing, and monitoring applications.

    Features:
      - Launch processes with optional sandboxing
      - Kill processes by PID or name
      - List running processes with resource info
      - Monitor process resource usage
      - Service management (start/stop/status)
      - Docker integration for sandboxed execution
      - Async process management via asyncio.subprocess

    Usage:
        pm = ProcessManager()
        result = await pm.launch("python script.py")
        processes = await pm.list_processes()
        await pm.kill(pid=12345)
    """

    def __init__(self):
        self.settings = get_settings()
        self._launched_processes: dict[int, asyncio.subprocess.Process] = {}
        self._process_results: dict[int, ProcessResult] = {}
        self._launch_count: int = 0

    # ── Launch Processes ──────────────────────────────────────────

    async def launch(
        self,
        command: str,
        args: Optional[list[str]] = None,
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
        sandbox: bool = False,
        capture_output: bool = True,
    ) -> ProcessResult:
        """
        Launch a process and optionally wait for completion.

        Args:
            command: The command to execute.
            args: Optional list of arguments.
            cwd: Working directory.
            env: Environment variables.
            timeout: Execution timeout in seconds.
            sandbox: Whether to run in a Docker sandbox.
            capture_output: Whether to capture stdout/stderr.

        Returns:
            ProcessResult with the execution outcome.
        """
        self._launch_count += 1

        if sandbox:
            return await self._launch_sandboxed(command, args, timeout)

        # Build command list
        cmd_parts = [command]
        if args:
            cmd_parts.extend(args)

        start_time = time.monotonic()

        try:
            # Build subprocess kwargs
            subprocess_kwargs: dict[str, Any] = {}
            if cwd:
                subprocess_kwargs["cwd"] = cwd
            if env:
                subprocess_kwargs["env"] = {**os.environ, **env}

            if capture_output:
                process = await asyncio.create_subprocess_exec(
                    *cmd_parts,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    **subprocess_kwargs,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    *cmd_parts,
                    **subprocess_kwargs,
                )

            self._launched_processes[process.pid] = process
            logger.info("Launched process PID=%d: %s", process.pid, command[:200])

            # Wait for completion
            timed_out = False
            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                timed_out = True
                process.kill()
                await process.wait()
                stdout_data = b""
                stderr_data = b"Process timed out"

            execution_time = (time.monotonic() - start_time) * 1000

            result = ProcessResult(
                pid=process.pid,
                exit_code=process.returncode or -1,
                stdout=(stdout_data or b"").decode(errors="replace"),
                stderr=(stderr_data or b"").decode(errors="replace"),
                timed_out=timed_out,
                execution_time_ms=execution_time,
                command=command,
            )

            self._process_results[process.pid] = result
            return result

        except FileNotFoundError:
            raise ProcessError(
                f"Command not found: {command}",
                details={"command": command},
            )
        except Exception as e:
            raise ProcessError(
                f"Failed to launch process: {e}",
                details={"command": command, "error": str(e)},
            )

    async def _launch_sandboxed(
        self,
        command: str,
        args: Optional[list[str]] = None,
        timeout: Optional[float] = None,
    ) -> ProcessResult:
        """
        Launch a process in a Docker sandbox.

        Uses the configured sandbox Docker image for isolated execution.

        Args:
            command: The command to execute inside the container.
            args: Optional arguments.
            timeout: Execution timeout.

        Returns:
            ProcessResult with the execution outcome.
        """
        sandbox_image = self.settings.sandbox_docker_image
        cmd_str = command
        if args:
            cmd_str += " " + " ".join(args)

        docker_cmd = [
            "docker", "run",
            "--rm",  # Remove container after execution
            "--network", "none",  # No network access
            "--memory", "512m",
            "--cpus", "1.0",
            sandbox_image,
            "sh", "-c", cmd_str,
        ]

        start_time = time.monotonic()

        try:
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            timed_out = False
            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout or 60,
                )
            except asyncio.TimeoutError:
                timed_out = True
                process.kill()
                await process.wait()
                stdout_data = b""
                stderr_data = b"Process timed out"

            execution_time = (time.monotonic() - start_time) * 1000

            result = ProcessResult(
                pid=process.pid,
                exit_code=process.returncode or -1,
                stdout=(stdout_data or b"").decode(errors="replace"),
                stderr=(stderr_data or b"").decode(errors="replace"),
                timed_out=timed_out,
                execution_time_ms=execution_time,
                command=f"[sandbox] {command}",
            )

            return result

        except FileNotFoundError:
            raise ProcessError(
                "Docker not available for sandboxed execution",
                details={"command": command},
            )
        except Exception as e:
            raise ProcessError(
                f"Sandboxed execution failed: {e}",
                details={"command": command, "error": str(e)},
            )

    async def launch_background(
        self,
        command: str,
        args: Optional[list[str]] = None,
        cwd: Optional[str] = None,
    ) -> int:
        """
        Launch a background process (non-blocking).

        Args:
            command: The command to execute.
            args: Optional arguments.
            cwd: Working directory.

        Returns:
            The process PID.
        """
        cmd_parts = [command]
        if args:
            cmd_parts.extend(args)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                cwd=cwd,
            )

            self._launched_processes[process.pid] = process
            logger.info("Launched background process PID=%d: %s", process.pid, command[:200])
            return process.pid

        except Exception as e:
            raise ProcessError(f"Failed to launch background process: {e}")

    # ── Kill Processes ────────────────────────────────────────────

    async def kill(self, pid: int, force: bool = False) -> bool:
        """
        Kill a process by PID.

        Args:
            pid: Process ID to kill.
            force: Whether to force kill (SIGKILL vs SIGTERM).

        Returns:
            True if the process was killed.
        """
        try:
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)

            # Remove from tracked processes
            if pid in self._launched_processes:
                del self._launched_processes[pid]

            logger.info("Killed process PID=%d (force=%s)", pid, force)
            return True

        except ProcessLookupError:
            logger.warning("Process PID=%d not found", pid)
            return False
        except PermissionError:
            logger.error("Permission denied to kill PID=%d", pid)
            return False
        except Exception as e:
            logger.error("Failed to kill PID=%d: %s", pid, e)
            return False

    async def kill_by_name(self, name: str, force: bool = False) -> int:
        """
        Kill all processes matching a name.

        Args:
            name: Process name to match.
            force: Whether to force kill.

        Returns:
            Number of processes killed.
        """
        processes = await self.list_processes()
        killed = 0

        for proc in processes:
            if name.lower() in proc.name.lower():
                if await self.kill(proc.pid, force=force):
                    killed += 1

        logger.info("Killed %d processes matching '%s'", killed, name)
        return killed

    # ── List Processes ────────────────────────────────────────────

    async def list_processes(
        self,
        filter_name: Optional[str] = None,
    ) -> list[ProcessInfo]:
        """
        List running processes.

        Args:
            filter_name: Optional name filter (case-insensitive partial match).

        Returns:
            List of ProcessInfo objects.
        """
        try:
            import psutil

            processes = []
            for proc in psutil.process_iter(["pid", "name", "cmdline", "status", "cpu_percent", "memory_info", "create_time", "username"]):
                try:
                    info = proc.info
                    name = info.get("name", "")
                    cmdline = info.get("cmdline", [])
                    cmd_str = " ".join(cmdline) if cmdline else ""

                    if filter_name and filter_name.lower() not in name.lower():
                        continue

                    mem_info = info.get("memory_info")
                    memory_mb = mem_info.rss / (1024 * 1024) if mem_info else 0

                    processes.append(ProcessInfo(
                        pid=info.get("pid", 0),
                        name=name,
                        command=cmd_str,
                        status=info.get("status", "unknown"),
                        cpu_percent=info.get("cpu_percent", 0) or 0,
                        memory_mb=memory_mb,
                        create_time=info.get("create_time", 0) or 0,
                        username=info.get("username", ""),
                    ))

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return processes

        except ImportError:
            # Fallback: use subprocess with ps command
            return await self._list_processes_fallback(filter_name)

    async def _list_processes_fallback(self, filter_name: Optional[str] = None) -> list[ProcessInfo]:
        """Fallback process listing using ps command."""
        try:
            if CURRENT_PLATFORM == "windows":
                cmd = ["tasklist", "/FO", "CSV", "/NH"]
            else:
                cmd = ["ps", "aux"]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode(errors="replace")

            processes = []
            for line in output.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue

                if CURRENT_PLATFORM == "windows":
                    # Parse CSV format: "name","pid","session","session_num","mem"
                    parts = [p.strip('"') for p in line.split('","')]
                    if len(parts) >= 2:
                        name = parts[0]
                        try:
                            pid = int(parts[1])
                        except ValueError:
                            continue

                        if filter_name and filter_name.lower() not in name.lower():
                            continue

                        processes.append(ProcessInfo(pid=pid, name=name))
                else:
                    # Parse ps aux format
                    parts = line.split(None, 10)
                    if len(parts) >= 11:
                        try:
                            pid = int(parts[1])
                        except ValueError:
                            continue

                        name = parts[10].split("/")[-1] if "/" in parts[10] else parts[10][:100]
                        cpu = float(parts[2]) if parts[2] != "0.0" else 0

                        if filter_name and filter_name.lower() not in name.lower():
                            continue

                        processes.append(ProcessInfo(
                            pid=pid,
                            name=name,
                            command=parts[10][:500] if len(parts) > 10 else "",
                            cpu_percent=cpu,
                        ))

            return processes[:500]  # Limit results

        except Exception as e:
            logger.error("Process listing failed: %s", e)
            return []

    # ── Monitor Processes ─────────────────────────────────────────

    async def get_process_info(self, pid: int) -> Optional[ProcessInfo]:
        """
        Get detailed information about a specific process.

        Args:
            pid: Process ID.

        Returns:
            ProcessInfo if the process exists, else None.
        """
        try:
            import psutil

            proc = psutil.Process(pid)
            mem_info = proc.memory_info()
            cpu_percent = proc.cpu_percent(interval=0.1)

            return ProcessInfo(
                pid=pid,
                name=proc.name(),
                command=" ".join(proc.cmdline()) if proc.cmdline() else "",
                status=proc.status(),
                cpu_percent=cpu_percent,
                memory_mb=mem_info.rss / (1024 * 1024),
                create_time=proc.create_time(),
                username=proc.username() if hasattr(proc, "username") else "",
            )

        except ImportError:
            # Fallback
            processes = await self.list_processes()
            for p in processes:
                if p.pid == pid:
                    return p
            return None
        except Exception:
            return None

    async def monitor_process(
        self,
        pid: int,
        interval: float = 1.0,
        duration: float = 10.0,
    ) -> list[dict[str, Any]]:
        """
        Monitor a process's resource usage over time.

        Args:
            pid: Process ID to monitor.
            interval: Sampling interval in seconds.
            duration: Total monitoring duration in seconds.

        Returns:
            List of resource usage samples.
        """
        samples = []
        elapsed = 0.0

        while elapsed < duration:
            info = await self.get_process_info(pid)
            if info is None:
                break

            samples.append({
                "timestamp": time.time(),
                "cpu_percent": info.cpu_percent,
                "memory_mb": info.memory_mb,
                "status": info.status,
            })

            await asyncio.sleep(interval)
            elapsed += interval

        return samples

    # ── Service Management ────────────────────────────────────────

    async def service_status(self, service_name: str) -> ServiceStatus:
        """
        Get the status of a system service.

        Args:
            service_name: Name of the service.

        Returns:
            ServiceStatus with the current state.
        """
        try:
            if CURRENT_PLATFORM == "linux":
                proc = await asyncio.create_subprocess_exec(
                    "systemctl", "is-active", service_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                status_text = stdout.decode().strip()

                running = status_text == "active"

                # Get PID if running
                pid = None
                if running:
                    pid_proc = await asyncio.create_subprocess_exec(
                        "systemctl", "show", service_name, "--property=MainPID",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    pid_stdout, _ = await pid_proc.communicate()
                    pid_line = pid_stdout.decode().strip()
                    if "=" in pid_line:
                        try:
                            pid = int(pid_line.split("=")[1])
                        except ValueError:
                            pass

                return ServiceStatus(
                    name=service_name,
                    running=running,
                    pid=pid,
                    status_text=status_text,
                )

            elif CURRENT_PLATFORM == "windows":
                proc = await asyncio.create_subprocess_exec(
                    "sc", "query", service_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                output = stdout.decode(errors="replace")
                running = "RUNNING" in output.upper()

                return ServiceStatus(
                    name=service_name,
                    running=running,
                    status_text="running" if running else "stopped",
                )

            return ServiceStatus(name=service_name, status_text="unsupported_platform")

        except FileNotFoundError:
            return ServiceStatus(name=service_name, status_text="service_manager_not_found")
        except Exception as e:
            return ServiceStatus(name=service_name, status_text=f"error: {e}")

    async def service_start(self, service_name: str) -> bool:
        """
        Start a system service.

        Args:
            service_name: Name of the service.

        Returns:
            True if the service was started.
        """
        try:
            if CURRENT_PLATFORM == "linux":
                proc = await asyncio.create_subprocess_exec(
                    "sudo", "systemctl", "start", service_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                return proc.returncode == 0

            elif CURRENT_PLATFORM == "windows":
                proc = await asyncio.create_subprocess_exec(
                    "net", "start", service_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                return proc.returncode == 0

            return False

        except Exception as e:
            logger.error("Failed to start service '%s': %s", service_name, e)
            return False

    async def service_stop(self, service_name: str) -> bool:
        """
        Stop a system service.

        Args:
            service_name: Name of the service.

        Returns:
            True if the service was stopped.
        """
        try:
            if CURRENT_PLATFORM == "linux":
                proc = await asyncio.create_subprocess_exec(
                    "sudo", "systemctl", "stop", service_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                return proc.returncode == 0

            elif CURRENT_PLATFORM == "windows":
                proc = await asyncio.create_subprocess_exec(
                    "net", "stop", service_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                return proc.returncode == 0

            return False

        except Exception as e:
            logger.error("Failed to stop service '%s': %s", service_name, e)
            return False

    # ── Docker Integration ────────────────────────────────────────

    async def docker_run(
        self,
        image: str,
        command: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        ports: Optional[dict[str, str]] = None,
        volumes: Optional[dict[str, str]] = None,
        remove: bool = True,
        timeout: Optional[float] = 60,
    ) -> ProcessResult:
        """
        Run a command in a Docker container.

        Args:
            image: Docker image name.
            command: Command to run inside the container.
            env: Environment variables.
            ports: Port mappings (host:container).
            volumes: Volume mappings (host:container).
            remove: Whether to remove the container after execution.
            timeout: Execution timeout in seconds.

        Returns:
            ProcessResult with the execution outcome.
        """
        docker_cmd = ["docker", "run"]

        if remove:
            docker_cmd.append("--rm")

        if env:
            for key, value in env.items():
                docker_cmd.extend(["-e", f"{key}={value}"])

        if ports:
            for host_port, container_port in ports.items():
                docker_cmd.extend(["-p", f"{host_port}:{container_port}"])

        if volumes:
            for host_path, container_path in volumes.items():
                docker_cmd.extend(["-v", f"{host_path}:{container_path}"])

        docker_cmd.append(image)

        if command:
            docker_cmd.extend(["sh", "-c", command])

        start_time = time.monotonic()

        try:
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            timed_out = False
            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                timed_out = True
                process.kill()
                await process.wait()
                stdout_data = b""
                stderr_data = b"Docker execution timed out"

            execution_time = (time.monotonic() - start_time) * 1000

            return ProcessResult(
                pid=process.pid,
                exit_code=process.returncode or -1,
                stdout=(stdout_data or b"").decode(errors="replace"),
                stderr=(stderr_data or b"").decode(errors="replace"),
                timed_out=timed_out,
                execution_time_ms=execution_time,
                command=f"docker run {image} {command or ''}",
            )

        except FileNotFoundError:
            raise ProcessError("Docker is not installed or not in PATH")
        except Exception as e:
            raise ProcessError(f"Docker execution failed: {e}")

    # ── Statistics ────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Get process manager statistics."""
        return {
            "platform": CURRENT_PLATFORM,
            "launch_count": self._launch_count,
            "tracked_processes": len(self._launched_processes),
            "completed_results": len(self._process_results),
            "sandbox_enabled": self.settings.sandbox_enabled,
            "sandbox_image": self.settings.sandbox_docker_image,
        }
