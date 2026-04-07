from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.models.user import User
from api.models.team import TeamMember, TeamRole
from api.api.dependencies import (
    get_current_active_user,
    verify_team_membership,
    verify_team_maintainer,
    verify_team_admin,
)
from api.schemas.team import (
    TeamCreate, TeamUpdate, TeamResponse, MemberRoleUpdate, MemberResponse,
    InvitationRespond, TeamInvitationResponse,
)
from api.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["Teams"])


def get_team_service(db: AsyncSession = Depends(get_db)) -> TeamService:
    return TeamService(db)


# ── Team CRUD ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    team_in: TeamCreate,
    current_user: User = Depends(get_current_active_user),
    svc: TeamService = Depends(get_team_service),
):
    """Create a new team. Requester becomes ADMIN."""
    return await svc.create_team(current_user.id, team_in)


@router.get("/me", response_model=List[TeamResponse])
async def read_my_teams(
    current_user: User = Depends(get_current_active_user),
    svc: TeamService = Depends(get_team_service),
):
    """List all teams the current user belongs to."""
    return await svc.get_my_teams(current_user.id)


@router.get("/search", response_model=List[TeamResponse])
async def search_teams(
    q: Optional[str] = "",
    svc: TeamService = Depends(get_team_service),
):
    """Search public teams by name."""
    return await svc.search_teams(q)


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    svc: TeamService = Depends(get_team_service),
):
    """Get team details (public endpoint)."""
    return await svc.get_team(team_id)


@router.get("/invite/{invite_token}", response_model=TeamResponse)
async def get_team_by_invite_token(
    invite_token: str,
    svc: TeamService = Depends(get_team_service),
):
    """Get team details by invite token (for join page)."""
    return await svc.get_team_by_invite_token(invite_token)


@router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    team_in: TeamUpdate,
    _: TeamMember = Depends(verify_team_maintainer),
    svc: TeamService = Depends(get_team_service),
):
    """Update team details (Admin/Maintainer)."""
    return await svc.update_team(team_id, team_in)


# ── Invite-link join ──────────────────────────────────────────────────────────

@router.post("/join/{invite_token}", response_model=MemberResponse)
async def join_via_invite_link(
    invite_token: str,
    current_user: User = Depends(get_current_active_user),
    svc: TeamService = Depends(get_team_service),
):
    """Join a team using a shareable invite link."""
    return await svc.join_via_invite_link(current_user.id, invite_token)


@router.post("/{team_id}/invite-link/regenerate", response_model=TeamResponse)
async def regenerate_invite_token(
    team_id: str,
    _: TeamMember = Depends(verify_team_admin),
    svc: TeamService = Depends(get_team_service),
):
    """Admin: rotate the invite link so old links no longer work."""
    return await svc.regenerate_invite_token(team_id)


# ── Join requests ─────────────────────────────────────────────────────────────

@router.post("/{team_id}/request-join", response_model=TeamInvitationResponse, status_code=status.HTTP_201_CREATED)
async def request_to_join(
    team_id: str,
    current_user: User = Depends(get_current_active_user),
    svc: TeamService = Depends(get_team_service),
):
    """Request to join a public team. Admin/Maintainer must approve."""
    return await svc.request_to_join(current_user.id, team_id)


# ── Admin-sent invites ────────────────────────────────────────────────────────

@router.post("/{team_id}/invite/{user_id}", response_model=TeamInvitationResponse, status_code=status.HTTP_201_CREATED)
async def send_invite(
    team_id: str,
    user_id: str,
    current_member: TeamMember = Depends(verify_team_maintainer),
    current_user: User = Depends(get_current_active_user),
    svc: TeamService = Depends(get_team_service),
):
    """Admin/Maintainer: send a direct invite to a user."""
    return await svc.send_invite(current_user.id, team_id, user_id)


# ── Invitation management ─────────────────────────────────────────────────────

@router.get("/{team_id}/invitations", response_model=List[TeamInvitationResponse])
async def list_invitations(
    team_id: str,
    _: TeamMember = Depends(verify_team_maintainer),
    svc: TeamService = Depends(get_team_service),
):
    """Admin/Maintainer: list all pending join requests and invites."""
    return await svc.list_pending_invitations(team_id)


@router.post("/{team_id}/invitations/{invitation_id}/respond", response_model=TeamInvitationResponse)
async def respond_to_invitation(
    team_id: str,
    invitation_id: str,
    body: InvitationRespond,
    _: TeamMember = Depends(verify_team_maintainer),
    svc: TeamService = Depends(get_team_service),
):
    """Admin/Maintainer: approve or decline a join request/invite."""
    return await svc.respond_to_invitation(team_id, invitation_id, body.accept)


@router.get("/{team_id}/members", response_model=List[MemberResponse])
async def get_team_members(
    team_id: str,
    _: TeamMember = Depends(verify_team_membership),
    svc: TeamService = Depends(get_team_service),
):
    """List all members of a team."""
    return await svc.get_team_members(team_id)


# ── Member management ─────────────────────────────────────────────────────────

@router.patch("/{team_id}/members/{user_id}/role", response_model=MemberResponse)
async def update_member_role(
    team_id: str,
    user_id: str,
    body: MemberRoleUpdate,
    _: TeamMember = Depends(verify_team_admin),
    svc: TeamService = Depends(get_team_service),
):
    """Admin: change a member's role."""
    return await svc.update_member_role(team_id, user_id, body.role)


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    team_id: str,
    user_id: str,
    _: TeamMember = Depends(verify_team_admin),
    svc: TeamService = Depends(get_team_service),
):
    """Admin: remove a member from the team."""
    await svc.remove_member(team_id, user_id)
