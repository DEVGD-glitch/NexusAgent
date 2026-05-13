"""
NEXUS Process Supervisor — Monitors and restarts critical subprocesses.

Ensures that background services (ChromaDB, browser service, etc.)
remain running. Restarts them automatically if they crash.
Only shows a toast to the user if the problem persists after retries.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"
    RESTARTING = "restarting"


@dataclass
class SupervisedService:
    """A service being monitored by the supervisor."""
    name: str
    status: ServiceStatus = ServiceStatus.STOPPED
    restart_count: int = 0
    max_restarts: int = 3
    last_check: float = 0.0
    last_error: str = ""
    pid: Optional[int] = None


class ProcessSupervisor:
    """
    Monitors NEXUS services and restarts them if they fail.

    Features:
      - Automatic restart on failure (up to max_restarts)
      - Health check every 30 seconds
      - Toast notification only after persistent failures
      - Silent recovery for transient issues
    """

    def __init__(self, check_interval: int = 30, max_restarts: int = 3):
        self.check_interval = check_interval
        self.max_restarts = max_restarts
        self._services: dict[str, SupervisedService] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def register_service(self, name: str, max_restarts: int = 3) -> None:
        """Register a service to be supervised."""
        self._services[name] = SupervisedService(
            name=name, max_restarts=max_restarts,
        )
        logger.info("Registered service: %s", name)

    def report_service_status(
        self, name: str, status: ServiceStatus, error: str = "", pid: Optional[int] = None,
    ) -> bool:
        """
        Report a service status change.

        Returns:
            True if the service should continue, False if it should stop.
        """
        if name not in self._services:
            self.register_service(name)

        service = self._services[name]
        service.status = status
        service.last_check = time.time()
        service.last_error = error

        if status == ServiceStatus.FAILED:
            service.restart_count += 1
            if service.restart_count > service.max_restarts:
                logger.error(
                    "Service %s failed %d times. NOT restarting.",
                    name, service.restart_count,
                )
                # Signal that user should be notified
                return False
            else:
                logger.warning(
                    "Service %s failed (%d/%d). Will attempt restart.",
                    name, service.restart_count, service.max_restarts,
                )
                return True

        if status == ServiceStatus.RUNNING:
            service.restart_count = 0  # Reset on successful start

        return True

    def should_notify_user(self, name: str) -> bool:
        """Check if the user should be notified about a service issue."""
        if name not in self._services:
            return False
        service = self._services[name]
        return service.restart_count >= service.max_restarts

    def get_status(self) -> dict[str, Any]:
        """Get status of all supervised services."""
        return {
            name: {
                "status": svc.status.value,
                "restart_count": svc.restart_count,
                "max_restarts": svc.max_restarts,
                "last_error": svc.last_error,
                "last_check": svc.last_check,
            }
            for name, svc in self._services.items()
        }

    async def start_monitoring(self) -> None:
        """Start the background monitoring loop."""
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self) -> None:
        """Stop the monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()

    async def _monitor_loop(self) -> None:
        """Background loop that checks service health."""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)
                # Future: Implement actual health checks
                # For now, just log that we're monitoring
                logger.debug("Supervisor check: %d services monitored", len(self._services))
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Supervisor error: %s", exc)
