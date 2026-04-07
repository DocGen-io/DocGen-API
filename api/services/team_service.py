from typing import List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.team import Team, TeamMember, TeamRole
from api.models.team_invitation import TeamInvitation, InvitationStatus, InvitationType
from api.schemas.team import TeamCreate, TeamUpdate, MemberRoleUpdate
from api.repositories.team import team_repo, invitation_repo


class TeamService:
    """Business logic for team management. Fully decoupled from routing."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Team CRUD ─────────────────────────────────────────────────────────────

    async def create_team(self, user_id: str, team_in: TeamCreate) -> Team:
        return await team_repo.create_team_with_member(self.db, team_in, user_id, TeamRole.ADMIN)

    async def update_team(self, team_id: str, team_in: TeamUpdate) -> Team:
        team = await self.get_team(team_id)
        return await team_repo.update(self.db, db_obj=team, obj_in=team_in)

    async def create_default_team(self, user_id: str, username: str) -> Team:
        """Auto-create a personal team for each newly registered user."""
        team_in = TeamCreate(name=username, description=f"{username}'s personal team", is_public=False)
        return await team_repo.create_team_with_member(self.db, team_in, user_id, TeamRole.ADMIN)

    async def get_my_teams(self, user_id: str) -> List[Team]:
        return await team_repo.get_user_teams(self.db, user_id)

    async def get_team(self, team_id: str) -> Team:
        team = await team_repo.get(self.db, id=team_id)
        if not team:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        return team

    async def get_team_by_invite_token(self, token: str) -> Team:
        team = await team_repo.get_by_invite_token(self.db, token)
        if not team:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired invite link")
        return team

    async def search_teams(self, query: str) -> List[Team]:
        return await team_repo.search_by_name(self.db, query, public_only=True)

    # ── Invite link ───────────────────────────────────────────────────────────

    async def join_via_invite_link(self, user_id: str, token: str) -> TeamMember:
        team = await team_repo.get_by_invite_token(self.db, token)
        if not team:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite link")

        existing = await team_repo.get_member(self.db, team.id, user_id)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already a team member")

        return await team_repo.add_member(self.db, team.id, user_id, TeamRole.VIEWER)

    async def regenerate_invite_token(self, team_id: str) -> Team:
        team = await self.get_team(team_id)
        return await team_repo.rotate_invite_token(self.db, team)

    # ── Join requests (user → team) ───────────────────────────────────────────

    async def request_to_join(self, user_id: str, team_id: str) -> TeamInvitation:
        team = await self.get_team(team_id)

        if not team.is_public:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Team is private")

        existing_member = await team_repo.get_member(self.db, team_id, user_id)
        if existing_member:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already a team member")

        existing_request = await invitation_repo.get_pending_request(self.db, team_id, user_id)
        if existing_request:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Join request already pending")

        return await invitation_repo.create(
            self.db, team_id=team_id, invitee_user_id=user_id,
            actor_user_id=user_id, inv_type=InvitationType.REQUEST
        )

    # ── Admin-sent invites ────────────────────────────────────────────────────

    async def send_invite(self, actor_id: str, team_id: str, target_user_id: str) -> TeamInvitation:
        existing_member = await team_repo.get_member(self.db, team_id, target_user_id)
        if existing_member:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a team member")

        existing_request = await invitation_repo.get_pending_request(self.db, team_id, target_user_id)
        if existing_request:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already has a pending invite")

        return await invitation_repo.create(
            self.db, team_id=team_id, invitee_user_id=target_user_id,
            actor_user_id=actor_id, inv_type=InvitationType.INVITE
        )

    # ── Respond to invitation / request ──────────────────────────────────────

    async def list_pending_invitations(self, team_id: str) -> List[TeamInvitation]:
        return await invitation_repo.get_pending_for_team(self.db, team_id)

    async def respond_to_invitation(
        self, team_id: str, invitation_id: str, accept: bool
    ) -> TeamInvitation:
        invitation = await invitation_repo.get_by_id(self.db, invitation_id)
        if not invitation or invitation.team_id != team_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
        if invitation.status != InvitationStatus.PENDING:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation already resolved")

        new_status = InvitationStatus.ACCEPTED if accept else InvitationStatus.DECLINED
        updated = await invitation_repo.update_status(self.db, invitation, new_status)

        if accept:
            await team_repo.add_member(self.db, team_id, invitation.invitee_user_id, TeamRole.VIEWER)

        return updated

    # ── Member management ─────────────────────────────────────────────────────

    async def update_member_role(self, team_id: str, target_user_id: str, role: TeamRole) -> TeamMember:
        member = await team_repo.get_member(self.db, team_id, target_user_id)
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        return await team_repo.update_member_role(self.db, member, role)

    async def remove_member(self, team_id: str, target_user_id: str) -> None:
        member = await team_repo.get_member(self.db, team_id, target_user_id)
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        if member.role == TeamRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove team admin")
        await team_repo.remove_member(self.db, member)

    async def get_team_members(self, team_id: str) -> List[TeamMember]:
        return await team_repo.get_team_members(self.db, team_id)
