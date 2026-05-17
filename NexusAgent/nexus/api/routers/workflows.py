"""NEXUS API — Workflow endpoints."""
from fastapi import APIRouter
from nexus.workflows.engine import get_workflow_engine

router = APIRouter()


@router.get("/list")
async def list_workflows():
    """List all workflows."""
    engine = get_workflow_engine()
    return {"workflows": engine.list_workflows()}


@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str):
    """Run a workflow."""
    engine = get_workflow_engine()
    result = engine.run(workflow_id)
    return {"workflow": workflow_id, "result": result}
