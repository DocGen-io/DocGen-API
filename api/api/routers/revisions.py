from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from api.schemas.revision import DocumentationRevisionResponse, DocumentationRevisionCreate
from api.services.revision_service import RevisionService
from api.core.database import get_db
from api.models.team import TeamMember
from api.api.dependencies import verify_team_membership, verify_team_maintainer

router = APIRouter()

@router.post("/{team_id}/docs/propose", response_model=DocumentationRevisionResponse, status_code=status.HTTP_201_CREATED)
async def propose_revision(
    team_id: str,
    proposal: DocumentationRevisionCreate,
    current_member: TeamMember = Depends(verify_team_membership),
    db: AsyncSession = Depends(get_db)
):
    # Security: verify_team_membership validates team_id == current_user.teams association
        
    service = RevisionService(db)
    return await service.propose_revision(team_id, str(current_member.user_id), proposal)

@router.get("/{team_id}/docs/revisions", response_model=List[DocumentationRevisionResponse])
async def list_revisions(
    team_id: str,
    rev_status: Optional[str] = None,
    current_member: TeamMember = Depends(verify_team_membership),
    db: AsyncSession = Depends(get_db)
):
    service = RevisionService(db)
    return await service.list_revisions(team_id, rev_status)

@router.post("/{team_id}/docs/approve/{revision_id}", response_model=DocumentationRevisionResponse)
async def approve_revision(
    team_id: str,
    revision_id: str,
    _: TeamMember = Depends(verify_team_maintainer),
    db: AsyncSession = Depends(get_db)
):
    service = RevisionService(db)
    try:
        return await service.approve_revision(team_id, revision_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{team_id}/docs/reject/{revision_id}", response_model=DocumentationRevisionResponse)
async def reject_revision(
    team_id: str,
    revision_id: str,
    _: TeamMember = Depends(verify_team_maintainer),
    db: AsyncSession = Depends(get_db)
):
    service = RevisionService(db)
    try:
        return await service.reject_revision(team_id, revision_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
