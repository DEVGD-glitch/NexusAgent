"""NEXUS API — HITL approval endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/pending")
async def get_pending_approvals():
    """Get pending approval requests."""
    return {"approvals": []}


@router.post("/{approval_id}/respond")
async def respond_to_approval(approval_id: str, request: dict):
    """Respond to an approval request."""
    approved = request.get("approved", False)
    return {"approval": approval_id, "approved": approved}
