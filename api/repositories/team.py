from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.orm import selectinload
import re
import uuid

from api.models.team import Team, TeamMember, TeamRole
from api.models.team_invitation import TeamInvitation, InvitationStatus, InvitationType
from api.schemas.team import TeamCreate
from api.repositories.base import BaseRepository


def _slugify(name: str) -> str:
    """Convert a team name into a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


class TeamRepository(BaseRepository[Team, TeamCreate, TeamCreate]):
    def __init__(self):
        super().__init__(Team)

    # ── Slug helpers ──────────────────────────────────────────────────────────

    async def _generate_unique_slug(self, db: AsyncSession, name: str) -> str:
        """Generate a slug from name, appending a counter if collisions exist."""
        base = _slugify(name)
        slug = base
        counter = 2
        while await self.get_by_slug(db, slug):
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    # ── Team lookup ───────────────────────────────────────────────────────────

    async def get_by_slug(self, db: AsyncSession, slug: str) -> Optional[Team]:
        result = await db.execute(select(Team).where(Team.slug == slug))
        return result.scalars().first()

    async def get_by_invite_token(self, db: AsyncSession, token: str) -> Optional[Team]:
        result = await db.execute(select(Team).where(Team.invite_token == token))
        return result.scalars().first()

    async def search_by_name(self, db: AsyncSession, query: str, public_only: bool = True) -> List[Team]:
        stmt = select(Team).where(Team.name.ilike(f"%{query}%"))
        if public_only:
            stmt = stmt.where(Team.is_public == True)  # noqa: E712
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ── Creation ──────────────────────────────────────────────────────────────

    async def create_team_with_member(
        self, db: AsyncSession, obj_in: TeamCreate, user_id: str, role: TeamRole
    ) -> Team:
        slug = await self._generate_unique_slug(db, obj_in.name)
        new_team = Team(
            name=obj_in.name,
            slug=slug,
            description=obj_in.description,
            is_public=obj_in.is_public,
            invite_token=str(uuid.uuid4()),
        )
        db.add(new_team)
        await db.flush()

        new_member = TeamMember(team_id=new_team.id, user_id=user_id, role=role)
        db.add(new_member)
        await db.commit()
        await db.refresh(new_team)
        return new_team

    # ── Member helpers ────────────────────────────────────────────────────────

    async def get_user_teams(self, db: AsyncSession, user_id: str) -> List[Team]:
        result = await db.execute(
            select(Team).join(TeamMember).where(TeamMember.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_member(self, db: AsyncSession, team_id: str, user_id: str) -> Optional[TeamMember]:
        result = await db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        return result.scalars().first()

    async def add_member(self, db: AsyncSession, team_id: str, user_id: str, role: TeamRole) -> TeamMember:
        member = TeamMember(team_id=team_id, user_id=user_id, role=role)
        db.add(member)
        await db.commit()
        await db.refresh(member)
        return member

    async def update_member_role(self, db: AsyncSession, member: TeamMember, role: TeamRole) -> TeamMember:
        member.role = role
        db.add(member)
        await db.commit()
        await db.refresh(member)
        return member

    async def remove_member(self, db: AsyncSession, member: TeamMember) -> None:
        await db.delete(member)
        await db.commit()

    async def get_team_members(self, db: AsyncSession, team_id: str) -> List[TeamMember]:
        """Fetch all members of a team, including joined user data."""
        # Join with User to get full user details for the frontend
        result = await db.execute(
            select(TeamMember)
            .options(selectinload(TeamMember.user))
            .where(TeamMember.team_id == team_id)
        )
        return list(result.scalars().all())

    async def rotate_invite_token(self, db: AsyncSession, team: Team) -> Team:
        team.invite_token = str(uuid.uuid4())
        db.add(team)
        await db.commit()
        await db.refresh(team)
        return team


class TeamInvitationRepository:
    async def create(
        self, db: AsyncSession,
        team_id: str, invitee_user_id: str, actor_user_id: str, inv_type: InvitationType
    ) -> TeamInvitation:
        invitation = TeamInvitation(
            team_id=team_id,
            invitee_user_id=invitee_user_id,
            actor_user_id=actor_user_id,
            type=inv_type,
            status=InvitationStatus.PENDING,
        )
        db.add(invitation)
        await db.commit()
        await db.refresh(invitation)
        return invitation

    async def get_by_id(self, db: AsyncSession, invitation_id: str) -> Optional[TeamInvitation]:
        result = await db.execute(
            select(TeamInvitation).where(TeamInvitation.id == invitation_id)
        )
        return result.scalars().first()

    async def get_pending_for_team(self, db: AsyncSession, team_id: str) -> List[TeamInvitation]:
        result = await db.execute(
            select(TeamInvitation).where(
                TeamInvitation.team_id == team_id,
                TeamInvitation.status == InvitationStatus.PENDING,
            )
        )
        return list(result.scalars().all())

    async def update_status(
        self, db: AsyncSession, invitation: TeamInvitation, status: InvitationStatus
    ) -> TeamInvitation:
        invitation.status = status
        db.add(invitation)
        await db.commit()
        await db.refresh(invitation)
        return invitation

    async def get_pending_request(
        self, db: AsyncSession, team_id: str, user_id: str
    ) -> Optional[TeamInvitation]:
        """Check if a user already has a pending request/invite for a team."""
        result = await db.execute(
            select(TeamInvitation).where(
                TeamInvitation.team_id == team_id,
                TeamInvitation.invitee_user_id == user_id,
                TeamInvitation.status == InvitationStatus.PENDING,
            )
        )
        return result.scalars().first()


team_repo = TeamRepository()
invitation_repo = TeamInvitationRepository()
