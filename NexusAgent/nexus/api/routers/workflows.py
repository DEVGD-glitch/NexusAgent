"""NEXUS API — Workflow endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/list")
async def list_workflows():
    """List all workflows."""
    return {"workflows": [], "note": "Workflow engine requires initialization"}


@router.post("/{workflow_id}/run")
async def run_workflow(workflow_id: str):
    """Run a workflow."""
    return {"workflow": workflow_id, "status": "not_implemented", "note": "Workflow execution requires initialization"}
