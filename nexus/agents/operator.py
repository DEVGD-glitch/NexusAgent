"""
NEXUS Operator Agent — Specialized in system operations and automation.

The Operator excels at:
  - System administration and monitoring
  - Deployment and infrastructure management
  - Process automation and scheduling
  - Security operations and compliance checks
  - Incident response and troubleshooting
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from nexus.agents.base import BaseAgent, AgentContext, AgentCapability
from nexus.core.registry import AgentCapability as Cap

logger = logging.getLogger(__name__)


class OperatorAgent(BaseAgent):
    """
    Operations Agent for system management and automation.

    Uses a systematic operations methodology:
      1. Assess the operational request
      2. Plan the execution steps
      3. Execute with safety checks
      4. Verify the outcome
      5. Document and report

    Tools: file_ops, code_execute, system_admin, git_integration,
           deployment, monitoring
    """

    def __init__(self):
        super().__init__(
            agent_type="operator",
            description="Operations agent for system management and automation",
            skills=[
                "system_admin", "deployment", "monitoring",
                "automation", "security_operations", "backup_restore",
                "troubleshooting", "compliance",
            ],
        )

    @property
    def system_prompt(self) -> str:
        return (
            "You are NEXUS Operator, a specialized operations agent. Your role is to:\n"
            "1. Execute system operations safely and reliably\n"
            "2. Automate repetitive tasks and processes\n"
            "3. Monitor system health and performance\n"
            "4. Manage deployments and infrastructure\n"
            "5. Respond to incidents and troubleshoot issues\n\n"
            "Operations methodology:\n"
            "- Always assess impact before making changes\n"
            "- Use least-privilege principles\n"
            "- Create backups before destructive operations\n"
            "- Verify changes after execution\n"
            "- Document all operations for audit trail\n"
            "- Follow runbook procedures when available\n\n"
            "Use tools: code_execute for scripts, file_read/file_write for configuration, "
            "git_integration for version control, memory for accessing operational runbooks."
        )

    @property
    def capabilities(self) -> list[AgentCapability]:
        return [Cap.OPERATION, Cap.FILE_OPS, Cap.BROWSING]

    async def plan(self, context: AgentContext) -> list[dict[str, Any]]:
        """Create an operations plan."""
        task = context.task
        task_lower = task.lower()

        # Detect operation type
        if any(kw in task_lower for kw in ["deploy", "release", "rollout", "ship"]):
            plan = self._deployment_plan(task)
        elif any(kw in task_lower for kw in ["monitor", "health", "status", "check"]):
            plan = self._monitoring_plan(task)
        elif any(kw in task_lower for kw in ["automate", "schedule", "cron", "routine"]):
            plan = self._automation_plan(task)
        elif any(kw in task_lower for kw in ["incident", "alert", "error", "down", "failure"]):
            plan = self._incident_plan(task)
        else:
            plan = self._general_ops_plan(task)

        return plan

    def _deployment_plan(self, task: str) -> list[dict[str, Any]]:
        return [
            {"action": "pre_deployment_check", "params": {"task": task}, "description": "Run pre-deployment checks"},
            {"action": "create_backup", "params": {}, "description": "Create backup of current state"},
            {"action": "execute_deployment", "params": {}, "description": "Execute deployment steps"},
            {"action": "verify_deployment", "params": {}, "description": "Verify deployment success"},
            {"action": "post_deployment_report", "params": {}, "description": "Generate post-deployment report"},
        ]

    def _monitoring_plan(self, task: str) -> list[dict[str, Any]]:
        return [
            {"action": "assess_monitoring_scope", "params": {"task": task}, "description": "Define monitoring scope"},
            {"action": "check_system_health", "params": {}, "description": "Check system health metrics"},
            {"action": "analyze_metrics", "params": {}, "description": "Analyze collected metrics"},
            {"action": "generate_health_report", "params": {}, "description": "Generate health report"},
        ]

    def _automation_plan(self, task: str) -> list[dict[str, Any]]:
        return [
            {"action": "analyze_automation_target", "params": {"task": task}, "description": "Analyze what to automate"},
            {"action": "design_automation", "params": {}, "description": "Design automation workflow"},
            {"action": "implement_automation", "params": {}, "description": "Implement automation script"},
            {"action": "test_automation", "params": {}, "description": "Test automation in safe mode"},
            {"action": "deploy_automation", "params": {}, "description": "Deploy automation to production"},
        ]

    def _incident_plan(self, task: str) -> list[dict[str, Any]]:
        return [
            {"action": "triage_incident", "params": {"task": task}, "description": "Triage and assess the incident"},
            {"action": "diagnose_root_cause", "params": {}, "description": "Diagnose root cause"},
            {"action": "implement_mitigation", "params": {}, "description": "Implement mitigation or fix"},
            {"action": "verify_resolution", "params": {}, "description": "Verify incident is resolved"},
            {"action": "post_incident_report", "params": {}, "description": "Create post-incident report"},
        ]

    def _general_ops_plan(self, task: str) -> list[dict[str, Any]]:
        return [
            {"action": "assess_request", "params": {"task": task}, "description": "Assess the operational request"},
            {"action": "plan_execution", "params": {}, "description": "Plan execution steps"},
            {"action": "execute_operations", "params": {}, "description": "Execute the operations"},
            {"action": "verify_results", "params": {}, "description": "Verify results"},
            {"action": "document_operations", "params": {}, "description": "Document what was done"},
        ]

    async def execute_step(self, step: dict[str, Any], context: AgentContext) -> dict[str, Any]:
        """Execute an operations step."""
        action = step.get("action", "")
        params = step.get("params", {})

        try:
            handler = getattr(self, f"_step_{action}", None)
            if handler:
                result = await handler(params, context)
            else:
                result = await self._generic_ops_step(action, params, context)

            return {"success": True, "result": result, "action": action}

        except Exception as e:
            logger.error("Operator step '%s' failed: %s", action, e)
            return {"success": False, "error": str(e), "action": action}

    async def _step_assess_request(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Assess the operational request."""
        task = params.get("task", context.task)

        messages = [
            {"role": "system", "content": (
                "Assess this operational request. Identify:\n"
                "1. Type of operation (deployment, monitoring, automation, incident)\n"
                "2. Affected systems and components\n"
                "3. Risk level (low/medium/high)\n"
                "4. Required permissions and access\n"
                "5. Prerequisites and dependencies\n"
                "6. Rollback strategy\n"
                "Return a structured assessment."
            )},
            {"role": "user", "content": task},
        ]

        assessment = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("assessment", assessment)

        return {"assessment": assessment}

    async def _step_pre_deployment_check(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Run pre-deployment checks."""
        task = params.get("task", context.task)

        messages = [
            {"role": "system", "content": (
                "Create a pre-deployment checklist for the following deployment. Include:\n"
                "1. Environment readiness checks\n"
                "2. Dependency version compatibility\n"
                "3. Configuration validation\n"
                "4. Resource availability (disk, memory, CPU)\n"
                "5. Backup verification\n"
                "6. Rollback plan\n"
                "Return a structured checklist with pass/fail items."
            )},
            {"role": "user", "content": task},
        ]

        checklist = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("pre_deploy_checklist", checklist)

        return {"checklist": checklist}

    async def _step_create_backup(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Create backup before destructive operations. NOTE: This generates a plan, does NOT execute it."""
        # Log the backup intent
        await self._log_action("backup_initiated", {"task": context.task[:200]})

        messages = [
            {"role": "system", "content": (
                "Design a backup strategy for the current deployment. Specify:\n"
                "1. What needs to be backed up (configs, data, code)\n"
                "2. Backup command or script\n"
                "3. Verification steps\n"
                "4. Retention policy\n"
                "Return executable backup commands."
            )},
            {"role": "user", "content": context.task[:2000]},
        ]

        backup_plan = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("backup_plan", backup_plan)

        # NOTE: This agent operates in ADVISORY mode - generates plans, does not execute
        return {"backup_plan": backup_plan, "mode": "advisory", "note": "Generated backup plan - manual execution required"}

    async def _step_execute_deployment(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Execute deployment steps. NOTE: This generates a script, does NOT execute it."""
        checklist = context.artifacts.get("pre_deploy_checklist", "")

        messages = [
            {"role": "system", "content": (
                "Generate deployment commands/steps based on the checklist and task. "
                "Include:\n"
                "1. Step-by-step deployment commands\n"
                "2. Environment variable checks\n"
                "3. Service restart commands\n"
                "4. Smoke test commands\n"
                "Return executable deployment script."
            )},
            {"role": "user", "content": (
                f"Task: {context.task[:1000]}\n\n"
                f"Pre-deploy checklist:\n{str(checklist)[:2000]}"
            )},
        ]

        deploy_script = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("deploy_script", deploy_script)

        # NOTE: This agent operates in ADVISORY mode - generates scripts, does not execute
        return {"deploy_script": deploy_script, "mode": "advisory", "note": "Generated deployment script - manual execution required"}

    async def _step_verify_deployment(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Verify deployment success."""
        deploy_script = context.artifacts.get("deploy_script", "")

        messages = [
            {"role": "system", "content": (
                "Create verification steps to confirm the deployment was successful. Include:\n"
                "1. Service health checks\n"
                "2. Endpoint availability tests\n"
                "3. Log error checks\n"
                "4. Performance baseline comparison\n"
                "Return executable verification commands."
            )},
            {"role": "user", "content": str(deploy_script)[:3000]},
        ]

        verification = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("verification", verification)

        return {"verification": verification}

    async def _step_post_deployment_report(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Generate post-deployment report."""
        all_artifacts = {k: str(v)[:500] for k, v in context.artifacts.items()}

        messages = [
            {"role": "system", "content": (
                "Create a post-deployment report summarizing:\n"
                "1. What was deployed\n"
                "2. Pre-deployment checks status\n"
                "3. Deployment steps executed\n"
                "4. Verification results\n"
                "5. Any issues encountered\n"
                "6. Recommendations\n"
                "Format as a professional deployment report."
            )},
            {"role": "user", "content": str(all_artifacts)},
        ]

        report = await self._call_llm(messages, temperature=0.3)
        context.store_artifact("report", report)

        return {"report": report}

    async def _step_check_system_health(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Check system health."""
        # Generate health check script
        messages = [
            {"role": "system", "content": (
                "Generate a system health check script that:\n"
                "1. Checks CPU, memory, disk usage\n"
                "2. Checks service status\n"
                "3. Checks network connectivity\n"
                "4. Checks log for recent errors\n"
                "Return Python code that can be executed."
            )},
            {"role": "user", "content": context.task[:2000]},
        ]

        health_script = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("health_script", health_script)

        # Try to execute
        result = await self._use_tool("code_execute", {
            "code": health_script,
            "language": "python",
            "timeout": 30,
        })
        context.store_artifact("health_result", result)

        return {"health": result, "tool_used": "code_execute"}

    async def _step_analyze_metrics(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Analyze collected metrics."""
        health_result = context.artifacts.get("health_result", {})

        messages = [
            {"role": "system", "content": (
                "Analyze the following system metrics. Identify:\n"
                "1. Any metrics outside normal ranges\n"
                "2. Trends or patterns of concern\n"
                "3. Potential root causes for anomalies\n"
                "4. Recommended actions\n"
            )},
            {"role": "user", "content": str(health_result)[:3000]},
        ]

        analysis = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("metrics_analysis", analysis)

        return {"analysis": analysis}

    async def _step_generate_health_report(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Generate health report."""
        metrics_analysis = context.artifacts.get("metrics_analysis", "")
        health_result = context.artifacts.get("health_result", {})

        messages = [
            {"role": "system", "content": (
                "Create a system health report with:\n"
                "1. Executive summary\n"
                "2. Current system status\n"
                "3. Key metrics and trends\n"
                "4. Issues identified\n"
                "5. Recommendations\n"
            )},
            {"role": "user", "content": (
                f"Metrics analysis:\n{str(metrics_analysis)[:2000]}\n\n"
                f"Raw data:\n{str(health_result)[:1000]}"
            )},
        ]

        report = await self._call_llm(messages, temperature=0.3)
        context.store_artifact("report", report)

        return {"report": report}

    async def _step_triage_incident(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Triage and assess an incident."""
        task = params.get("task", context.task)

        messages = [
            {"role": "system", "content": (
                "Triage this incident. Determine:\n"
                "1. Severity level (P1-P4)\n"
                "2. Affected services and users\n"
                "3. Blast radius\n"
                "4. Time of onset\n"
                "5. Immediate mitigation steps\n"
                "Return a structured incident triage."
            )},
            {"role": "user", "content": task},
        ]

        triage = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("triage", triage)

        return {"triage": triage}

    async def _step_diagnose_root_cause(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Diagnose root cause of incident."""
        triage = context.artifacts.get("triage", "")

        messages = [
            {"role": "system", "content": (
                "Based on the incident triage, diagnose the likely root cause. "
                "Consider:\n"
                "1. Recent changes that could have caused this\n"
                "2. Infrastructure issues (network, storage, compute)\n"
                "3. Application-level errors\n"
                "4. External dependencies\n"
                "5. Configuration drift\n"
                "Provide ranked hypotheses with supporting evidence."
            )},
            {"role": "user", "content": str(triage)[:3000]},
        ]

        diagnosis = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("diagnosis", diagnosis)

        return {"diagnosis": diagnosis}

    async def _step_implement_mitigation(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Implement incident mitigation."""
        diagnosis = context.artifacts.get("diagnosis", "")

        messages = [
            {"role": "system", "content": (
                "Based on the diagnosis, provide mitigation steps. Include:\n"
                "1. Immediate mitigation (stop the bleeding)\n"
                "2. Root cause fix\n"
                "3. Verification steps\n"
                "4. Commands/scripts to execute\n"
                "Return executable mitigation steps."
            )},
            {"role": "user", "content": str(diagnosis)[:3000]},
        ]

        mitigation = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("mitigation", mitigation)

        return {"mitigation": mitigation}

    async def _step_verify_resolution(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Verify incident is resolved."""
        mitigation = context.artifacts.get("mitigation", "")

        messages = [
            {"role": "system", "content": (
                "Create verification steps to confirm the incident is resolved. "
                "Include service health checks, error log verification, and "
                "user-facing functionality tests."
            )},
            {"role": "user", "content": str(mitigation)[:2000]},
        ]

        verification = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("resolution_verification", verification)

        return {"verification": verification}

    async def _step_post_incident_report(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Create post-incident report."""
        triage = context.artifacts.get("triage", "")
        diagnosis = context.artifacts.get("diagnosis", "")
        mitigation = context.artifacts.get("mitigation", "")

        messages = [
            {"role": "system", "content": (
                "Create a post-incident report with:\n"
                "1. Incident summary\n"
                "2. Timeline of events\n"
                "3. Root cause analysis\n"
                "4. Mitigation and resolution steps\n"
                "5. Impact assessment\n"
                "6. Lessons learned\n"
                "7. Action items to prevent recurrence\n"
            )},
            {"role": "user", "content": (
                f"Triage:\n{str(triage)[:1000]}\n\n"
                f"Diagnosis:\n{str(diagnosis)[:1000]}\n\n"
                f"Mitigation:\n{str(mitigation)[:1000]}"
            )},
        ]

        report = await self._call_llm(messages, temperature=0.3)
        context.store_artifact("report", report)

        return {"report": report}

    # Automation steps
    async def _step_analyze_automation_target(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Analyze what to automate."""
        task = params.get("task", context.task)

        messages = [
            {"role": "system", "content": (
                "Analyze this automation request. Identify:\n"
                "1. The manual process to automate\n"
                "2. Trigger conditions (schedule, event, manual)\n"
                "3. Required inputs and expected outputs\n"
                "4. Error handling requirements\n"
                "5. Success criteria\n"
            )},
            {"role": "user", "content": task},
        ]

        analysis = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("automation_analysis", analysis)

        return {"analysis": analysis}

    async def _step_design_automation(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Design the automation workflow."""
        analysis = context.artifacts.get("automation_analysis", "")

        messages = [
            {"role": "system", "content": (
                "Design an automation workflow. Include:\n"
                "1. Flow diagram (text-based)\n"
                "2. Decision points and branching\n"
                "3. Error handling and retries\n"
                "4. Logging and monitoring\n"
                "5. Notification on completion/failure\n"
            )},
            {"role": "user", "content": str(analysis)[:3000]},
        ]

        design = await self._call_llm(messages, temperature=0.3)
        context.store_artifact("automation_design", design)

        return {"design": design}

    async def _step_implement_automation(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Implement the automation script."""
        design = context.artifacts.get("automation_design", "")

        messages = [
            {"role": "system", "content": (
                "Write a complete Python automation script based on the design. Include:\n"
                "1. Argument parsing\n"
                "2. Main workflow logic\n"
                "3. Error handling with retries\n"
                "4. Logging configuration\n"
                "5. Dry-run mode for testing\n"
                "Write COMPLETE, executable code."
            )},
            {"role": "user", "content": str(design)[:3000]},
        ]

        code = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("automation_code", code)

        return {"code": code, "tool_used": "code_generation"}

    async def _step_test_automation(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Test the automation in safe mode."""
        code = context.artifacts.get("automation_code", "")

        result = await self._use_tool("code_execute", {
            "code": code,
            "language": "python",
            "timeout": 30,
        })
        context.store_artifact("automation_test", result)

        return {"test_result": result, "tool_used": "code_execute"}

    async def _step_deploy_automation(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Deploy the automation to production."""
        messages = [
            {"role": "system", "content": (
                "Provide deployment instructions for the automation script. Include:\n"
                "1. Where to deploy (crontab, systemd, task scheduler)\n"
                "2. Environment setup\n"
                "3. Monitoring and alerting setup\n"
                "4. Rollback procedure\n"
            )},
            {"role": "user", "content": context.task[:2000]},
        ]

        deploy_instructions = await self._call_llm(messages, temperature=0.3)
        context.store_artifact("deploy_instructions", deploy_instructions)

        return {"deploy_instructions": deploy_instructions}

    # Remaining plan steps
    async def _step_plan_execution(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Plan execution steps for general operations."""
        assessment = context.artifacts.get("assessment", context.task)

        messages = [
            {"role": "system", "content": (
                "Create a step-by-step execution plan for this operational task. "
                "Include commands, verification steps, and rollback procedures."
            )},
            {"role": "user", "content": str(assessment)[:3000]},
        ]

        execution_plan = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("execution_plan", execution_plan)

        return {"execution_plan": execution_plan}

    async def _step_execute_operations(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Execute the planned operations."""
        execution_plan = context.artifacts.get("execution_plan", "")

        messages = [
            {"role": "system", "content": (
                "Generate executable commands/scripts for the following plan. "
                "Include safety checks between steps."
            )},
            {"role": "user", "content": str(execution_plan)[:3000]},
        ]

        script = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("ops_script", script)

        return {"script": script}

    async def _step_verify_results(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Verify operational results."""
        messages = [
            {"role": "system", "content": "Create verification steps for the completed operation."},
            {"role": "user", "content": f"Task: {context.task[:1000]}\nArtifacts: {list(context.artifacts.keys())}"},
        ]

        verification = await self._call_llm(messages, temperature=0.2)
        context.store_artifact("ops_verification", verification)

        return {"verification": verification}

    async def _step_document_operations(self, params: dict, context: AgentContext) -> dict[str, Any]:
        """Document what was done."""
        all_artifacts = {k: str(v)[:300] for k, v in context.artifacts.items()}

        messages = [
            {"role": "system", "content": (
                "Create an operational log documenting what was done. Include:\n"
                "1. Task description\n"
                "2. Steps taken\n"
                "3. Results\n"
                "4. Issues encountered\n"
                "5. Recommendations for future\n"
            )},
            {"role": "user", "content": str(all_artifacts)},
        ]

        doc = await self._call_llm(messages, temperature=0.3)
        context.store_artifact("report", doc)

        return {"documentation": doc}

    async def _generic_ops_step(self, action: str, params: dict, context: AgentContext) -> dict[str, Any]:
        """Handle generic operations steps."""
        messages = [
            {"role": "system", "content": f"You are performing the operations step: {action}"},
            {"role": "user", "content": f"Task: {context.task}\nStep: {action}\nParams: {params}"},
        ]
        result = await self._call_llm(messages, temperature=0.3)
        return {"result": result}

    async def reflect(self, context: AgentContext) -> dict[str, Any]:
        """Reflect on operations progress."""
        if "report" in context.artifacts:
            return {
                "should_continue": False,
                "assessment": "Operations complete. Report generated.",
            }

        if "verification" in context.artifacts or "resolution_verification" in context.artifacts:
            return {
                "should_continue": True,
                "assessment": "Verification done. Generating report.",
                "adjustments": {"next_action": "report"},
            }

        return {
            "should_continue": True,
            "assessment": "Operations in progress. Continuing.",
        }
