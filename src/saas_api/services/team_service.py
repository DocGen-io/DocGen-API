from sqlalchemy.ext.asyncio import AsyncSession
from src.saas_api.repositories.team import team_repo
from src.saas_api.models.team import Team, TeamRole
from src.saas_api.schemas.team import TeamCreate
from typing import List

class TeamService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_team(self, user_id: str, team_in: TeamCreate) -> Team:
        return await team_repo.create_team_with_member(self.db, team_in, user_id, TeamRole.ADMIN)

    async def get_my_teams(self, user_id: str) -> List[Team]:
        return await team_repo.get_user_teams(self.db, user_id)
