"""
NEXUS Deployer — Deployment automation.

Supports:
  - Docker container building and deployment
  - GitHub Actions workflow generation
  - Cloud deployment support (generic Docker-based)
  - Configuration management for different environments
  - Rollback capabilities
  - Health check after deployment
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from nexus.core.config import get_settings

logger = logging.getLogger(__name__)


class DeployEnvironment(str, Enum):
    """Deployment environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DeployStatus(str, Enum):
    """Deployment status."""
    PENDING = "pending"
    BUILDING = "building"
    DEPLOYING = "deploying"
    RUNNING = "running"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    STOPPED = "stopped"


@dataclass
class DeployConfig:
    """Configuration for a deployment."""
    name: str
    environment: DeployEnvironment = DeployEnvironment.STAGING
    dockerfile: str = "Dockerfile"
    image_name: str = ""
    image_tag: str = "latest"
    container_port: int = 8080
    host_port: int = 8080
    env_vars: dict[str, str] = field(default_factory=dict)
    volumes: list[str] = field(default_factory=list)
    health_check_url: str = ""
    health_check_interval: int = 10
    health_check_timeout: int = 60
    cpu_limit: str = "0.5"
    memory_limit: str = "512m"
    replicas: int = 1
    registry: str = ""
    pre_deploy_commands: list[str] = field(default_factory=list)
    post_deploy_commands: list[str] = field(default_factory=list)
    rollback_on_failure: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "environment": self.environment.value,
            "dockerfile": self.dockerfile,
            "image_name": self.image_name,
            "image_tag": self.image_tag,
            "container_port": self.container_port,
            "host_port": self.host_port,
            "cpu_limit": self.cpu_limit,
            "memory_limit": self.memory_limit,
            "replicas": self.replicas,
        }


@dataclass
class DeployResult:
    """Result of a deployment operation."""
    config_name: str
    status: DeployStatus = DeployStatus.PENDING
    image_id: str = ""
    container_id: str = ""
    container_name: str = ""
    deploy_time_ms: float = 0.0
    health_check_passed: bool = False
    health_check_url: str = ""
    previous_container_id: str = ""  # For rollback
    error: str = ""
    logs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_name": self.config_name,
            "status": self.status.value,
            "image_id": self.image_id,
            "container_id": self.container_id,
            "container_name": self.container_name,
            "deploy_time_ms": self.deploy_time_ms,
            "health_check_passed": self.health_check_passed,
            "error": self.error,
        }


class Deployer:
    """
    Automated deployment engine.

    Supports building Docker images, deploying containers,
    generating CI/CD workflows, and performing health checks.

    Usage:
        deployer = Deployer()
        config = DeployConfig(name="my-app", image_name="my-app")
        result = await deployer.deploy(config)
    """

    # Default Dockerfile template
    DOCKERFILE_TEMPLATE = """\
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE {port}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \\
    CMD curl -f http://localhost:{port}/health || exit 1

# Run the application
CMD ["python", "-m", "{module}"]
"""

    # GitHub Actions workflow template
    GITHUB_ACTIONS_TEMPLATE = """\
name: {name} Deploy

on:
  push:
    branches: [{branch}]
  workflow_dispatch:

env:
  IMAGE_NAME: {image_name}
  REGISTRY: {registry}

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{{ env.REGISTRY }}}
          username: ${{{{ secrets.REGISTRY_USERNAME }}}}
          password: ${{{{ secrets.REGISTRY_PASSWORD }}}}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{{ env.REGISTRY }}}/${{{{ env.IMAGE_NAME }}}}
          tags: |
            type=sha,prefix=
            type=raw,value=latest,enable={{{{is_default_branch}}}}

      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{{{ steps.meta.outputs.tags }}}}
          labels: ${{{{ steps.meta.outputs.labels }}}}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Deploy
        run: |
          echo "Deploying ${{{{ steps.meta.outputs.tags }}}} to {environment}"
          {deploy_command}
"""

    def __init__(self, project_dir: Optional[str] = None):
        """
        Initialize the Deployer.

        Args:
            project_dir: Root directory of the project to deploy.
                         Defaults to current working directory.
        """
        self.settings = get_settings()
        self.project_dir = project_dir or os.getcwd()
        self._deployments: dict[str, DeployResult] = {}

    async def _run_command(
        self,
        command: str,
        timeout: int = 300,
        cwd: Optional[str] = None,
    ) -> tuple[int, str, str]:
        """
        Run a shell command and return (exit_code, stdout, stderr).

        Args:
            command: Shell command to execute.
            timeout: Timeout in seconds.
            cwd: Working directory.

        Returns:
            Tuple of (exit_code, stdout, stderr).
        """
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd or self.project_dir,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
                return (
                    proc.returncode or 0,
                    stdout_bytes.decode("utf-8", errors="replace"),
                    stderr_bytes.decode("utf-8", errors="replace"),
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return -1, "", f"Command timed out after {timeout}s"

        except Exception as exc:
            return 1, "", str(exc)

    async def build_docker_image(
        self,
        config: DeployConfig,
        build_args: Optional[dict[str, str]] = None,
        no_cache: bool = False,
    ) -> tuple[bool, str]:
        """
        Build a Docker image from a Dockerfile.

        Args:
            config: Deployment configuration.
            build_args: Additional Docker build arguments.
            no_cache: Disable Docker build cache.

        Returns:
            Tuple of (success, image_id_or_error).
        """
        image_name = config.image_name or config.name
        image_tag = config.image_tag
        full_tag = f"{image_name}:{image_tag}"

        # Add registry prefix if configured
        if config.registry:
            full_tag = f"{config.registry}/{full_tag}"

        # Build the docker build command
        cmd_parts = [
            "docker", "build",
            "-f", config.dockerfile,
            "-t", full_tag,
        ]

        if no_cache:
            cmd_parts.append("--no-cache")

        if build_args:
            for key, value in build_args.items():
                cmd_parts.extend(["--build-arg", f"{key}={value}"])

        cmd_parts.append(".")

        command = " ".join(cmd_parts)
        logger.info("Building Docker image: %s", full_tag)

        exit_code, stdout, stderr = await self._run_command(command, timeout=600)

        if exit_code != 0:
            error_msg = stderr or stdout
            logger.error("Docker build failed: %s", error_msg[:500])
            return False, error_msg[:500]

        # Extract image ID from build output
        image_id = ""
        for line in stdout.split("\n"):
            if "Successfully built" in line:
                image_id = line.split()[-1]
            elif "Successfully tagged" in line:
                full_tag = line.split()[-1]

        logger.info("Docker image built successfully: %s (id=%s)", full_tag, image_id)
        return True, full_tag

    async def deploy(
        self,
        config: DeployConfig,
        skip_build: bool = False,
    ) -> DeployResult:
        """
        Deploy an application.

        Steps:
        1. Run pre-deploy commands
        2. Build Docker image (if not skipped)
        3. Stop existing container (if running)
        4. Start new container
        5. Run health check
        6. Run post-deploy commands
        7. Rollback on failure (if configured)

        Args:
            config: Deployment configuration.
            skip_build: Skip the Docker build step.

        Returns:
            DeployResult with deployment status and details.
        """
        start = time.monotonic()
        result = DeployResult(config_name=config.name)
        container_name = f"nexus-{config.name}-{config.environment.value}"
        result.container_name = container_name

        # Run pre-deploy commands
        if config.pre_deploy_commands:
            for cmd in config.pre_deploy_commands:
                exit_code, stdout, stderr = await self._run_command(cmd)
                result.logs.append(f"[pre-deploy] {cmd}: exit={exit_code}")
                if exit_code != 0:
                    result.status = DeployStatus.FAILED
                    result.error = f"Pre-deploy command failed: {cmd}"
                    return result

        # Build Docker image
        result.status = DeployStatus.BUILDING
        if not skip_build:
            success, image_ref = await self.build_docker_image(config)
            if not success:
                result.status = DeployStatus.FAILED
                result.error = f"Docker build failed: {image_ref}"
                result.deploy_time_ms = (time.monotonic() - start) * 1000
                self._deployments[config.name] = result
                return result
            result.image_id = image_ref
        else:
            image_name = config.image_name or config.name
            image_tag = config.image_tag
            prefix = f"{config.registry}/" if config.registry else ""
            result.image_id = f"{prefix}{image_name}:{image_tag}"

        # Stop existing container
        result.status = DeployStatus.DEPLOYING
        existing_id = await self._get_container_id(container_name)
        if existing_id:
            result.previous_container_id = existing_id
            await self._stop_container(existing_id)
            result.logs.append(f"Stopped existing container: {existing_id[:12]}")

        # Start new container
        container_id = await self._start_container(config, container_name, result.image_id)
        if not container_id:
            result.status = DeployStatus.FAILED
            result.error = "Failed to start container"
            # Rollback if configured
            if config.rollback_on_failure and result.previous_container_id:
                await self._rollback(config, result)
            result.deploy_time_ms = (time.monotonic() - start) * 1000
            self._deployments[config.name] = result
            return result

        result.container_id = container_id
        result.logs.append(f"Started container: {container_id[:12]}")

        # Health check
        health_passed = False
        if config.health_check_url:
            health_passed = await self._health_check(config)
            result.health_check_url = config.health_check_url
            result.health_check_passed = health_passed

            if not health_passed:
                result.status = DeployStatus.FAILED
                result.error = "Health check failed"
                if config.rollback_on_failure and result.previous_container_id:
                    await self._rollback(config, result)
                result.deploy_time_ms = (time.monotonic() - start) * 1000
                self._deployments[config.name] = result
                return result
        else:
            result.health_check_passed = True

        # Run post-deploy commands
        if config.post_deploy_commands:
            for cmd in config.post_deploy_commands:
                exit_code, stdout, stderr = await self._run_command(cmd)
                result.logs.append(f"[post-deploy] {cmd}: exit={exit_code}")

        result.status = DeployStatus.RUNNING
        result.deploy_time_ms = (time.monotonic() - start) * 1000
        self._deployments[config.name] = result

        logger.info(
            "Deployment complete: %s (%s) in %.0fms",
            config.name, result.status.value, result.deploy_time_ms,
        )
        return result

    async def stop(self, config_name: str) -> DeployResult:
        """
        Stop a running deployment.

        Args:
            config_name: Name of the deployment to stop.

        Returns:
            DeployResult with the stop status.
        """
        result = self._deployments.get(config_name)
        if not result:
            return DeployResult(
                config_name=config_name,
                status=DeployStatus.STOPPED,
                error="Deployment not found",
            )

        if result.container_id:
            await self._stop_container(result.container_id)

        result.status = DeployStatus.STOPPED
        logger.info("Stopped deployment: %s", config_name)
        return result

    async def rollback(self, config_name: str) -> DeployResult:
        """
        Rollback a deployment to its previous version.

        Args:
            config_name: Name of the deployment to rollback.

        Returns:
            DeployResult with the rollback status.
        """
        result = self._deployments.get(config_name)
        if not result:
            return DeployResult(
                config_name=config_name,
                status=DeployStatus.FAILED,
                error="Deployment not found",
            )

        if not result.previous_container_id:
            return DeployResult(
                config_name=config_name,
                status=DeployStatus.FAILED,
                error="No previous container to rollback to",
            )

        # Stop current container
        if result.container_id:
            await self._stop_container(result.container_id)

        # Restart previous container
        success, output = await self._restart_container(result.previous_container_id)
        if success:
            result.status = DeployStatus.ROLLED_BACK
            result.container_id = result.previous_container_id
            logger.info("Rolled back deployment: %s", config_name)
        else:
            result.status = DeployStatus.FAILED
            result.error = f"Rollback failed: {output}"

        return result

    async def _rollback(self, config: DeployConfig, result: DeployResult) -> None:
        """Perform rollback by restarting the previous container."""
        if not result.previous_container_id:
            return

        logger.warning("Rolling back deployment: %s", config.name)
        success, output = await self._restart_container(result.previous_container_id)
        if success:
            result.status = DeployStatus.ROLLED_BACK
            result.logs.append(f"Rolled back to container: {result.previous_container_id[:12]}")
        else:
            result.logs.append(f"Rollback failed: {output}")

    @staticmethod
    def _validate_docker_name(name: str) -> str:
        """Validate a Docker container name/ID to prevent shell injection."""
        import re
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$', name):
            raise ValueError(f"Invalid Docker name: {name!r}")
        return name

    async def _get_container_id(self, container_name: str) -> str:
        """Get the container ID for a given container name."""
        self._validate_docker_name(container_name)
        exit_code, stdout, _ = await self._run_command(
            f"docker ps -q -f name={container_name}",
            timeout=10,
        )
        return stdout.strip()

    async def _stop_container(self, container_id: str) -> bool:
        """Stop a Docker container."""
        self._validate_docker_name(container_id)
        exit_code, _, stderr = await self._run_command(
            f"docker stop {container_id}",
            timeout=30,
        )
        if exit_code != 0:
            logger.warning("Failed to stop container %s: %s", container_id[:12], stderr)
            # Try to force remove
            await self._run_command(f"docker rm -f {container_id}", timeout=10)  # container_id already validated above
        return exit_code == 0

    async def _start_container(
        self,
        config: DeployConfig,
        container_name: str,
        image: str,
    ) -> str:
        """Start a Docker container and return its ID."""
        cmd_parts = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{config.host_port}:{config.container_port}",
            "--memory", config.memory_limit,
            "--cpus", config.cpu_limit,
        ]

        # Add environment variables
        for key, value in config.env_vars.items():
            cmd_parts.extend(["-e", f"{key}={value}"])

        # Add volumes
        for vol in config.volumes:
            cmd_parts.extend(["-v", vol])

        # Add restart policy
        cmd_parts.extend(["--restart", "unless-stopped"])

        cmd_parts.append(image)

        command = " ".join(cmd_parts)
        exit_code, stdout, stderr = await self._run_command(command, timeout=60)

        if exit_code != 0:
            logger.error("Failed to start container: %s", stderr[:500])
            return ""

        return stdout.strip()

    async def _restart_container(self, container_id: str) -> tuple[bool, str]:
        """Restart a stopped Docker container."""
        exit_code, stdout, stderr = await self._run_command(
            f"docker start {container_id}",
            timeout=30,
        )
        if exit_code != 0:
            return False, stderr or "Unknown error"
        return True, stdout.strip()

    async def _health_check(self, config: DeployConfig) -> bool:
        """
        Perform a health check on the deployed service.

        Makes HTTP requests to the health check URL until it
        responds with 200 OK or the timeout is exceeded.
        """
        import httpx

        url = config.health_check_url
        timeout = config.health_check_timeout
        interval = config.health_check_interval
        elapsed = 0

        logger.info("Running health check against: %s", url)

        while elapsed < timeout:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        logger.info("Health check passed: %s", url)
                        return True
            except Exception:
                pass

            await asyncio.sleep(interval)
            elapsed += interval

        logger.warning("Health check failed after %ds: %s", timeout, url)
        return False

    def generate_dockerfile(
        self,
        port: int = 8080,
        module: str = "nexus",
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate a Dockerfile for the project.

        Args:
            port: The port to expose.
            module: The Python module to run.
            output_path: Optional path to write the Dockerfile.

        Returns:
            The generated Dockerfile content.
        """
        content = self.DOCKERFILE_TEMPLATE.format(port=port, module=module)

        if output_path:
            Path(output_path).write_text(content)
            logger.info("Generated Dockerfile at: %s", output_path)

        return content

    def generate_github_actions_workflow(
        self,
        name: str = "nexus",
        branch: str = "main",
        image_name: str = "nexus",
        registry: str = "ghcr.io",
        environment: str = "staging",
        deploy_command: str = "echo 'Add deploy command here'",
        output_path: Optional[str] = None,
    ) -> str:
        """
        Generate a GitHub Actions workflow file.

        Args:
            name: Workflow name.
            branch: Branch to trigger on.
            image_name: Docker image name.
            registry: Container registry URL.
            environment: Target deployment environment.
            deploy_command: Command to run for deployment.
            output_path: Optional path to write the workflow file.

        Returns:
            The generated workflow YAML content.
        """
        content = self.GITHUB_ACTIONS_TEMPLATE.format(
            name=name,
            branch=branch,
            image_name=image_name,
            registry=registry,
            environment=environment,
            deploy_command=deploy_command,
        )

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(content)
            logger.info("Generated GitHub Actions workflow at: %s", output_path)

        return content

    def get_deployment_status(self, config_name: Optional[str] = None) -> dict[str, Any]:
        """
        Get the status of one or all deployments.

        Args:
            config_name: Optional specific deployment name. If None, returns all.

        Returns:
            Dict with deployment status information.
        """
        if config_name:
            result = self._deployments.get(config_name)
            return result.to_dict() if result else {"error": "Deployment not found"}

        return {
            name: result.to_dict()
            for name, result in self._deployments.items()
        }
