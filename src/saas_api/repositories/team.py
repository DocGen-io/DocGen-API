from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.saas_api.models.team import Team, TeamMember
from src.saas_api.schemas.team import TeamCreate
from src.saas_api.repositories.base import BaseRepository

class TeamRepository(BaseRepository[Team, TeamCreate, TeamCreate]):
    def __init__(self):
        super().__init__(Team)

    async def create_team_with_member(self, db: AsyncSession, obj_in: TeamCreate, user_id: str, role: str) -> Team:
        # Create team
        new_team = Team(name=obj_in.name, description=obj_in.description)
        db.add(new_team)
        await db.flush() # Get the new_team.id locally

        # Associate member
        new_member = TeamMember(team_id=new_team.id, user_id=user_id, role=role)
        db.add(new_member)
        await db.commit()
        await db.refresh(new_team)
        return new_team

    async def get_user_teams(self, db: AsyncSession, user_id: str) -> List[Team]:
        result = await db.execute(
            select(Team).join(TeamMember).where(TeamMember.user_id == user_id)
        )
        return result.scalars().all() # type: ignore

team_repo = TeamRepository()
