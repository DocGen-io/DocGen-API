from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.future import select

from src.saas_api.models.team_config import TeamConfiguration
from src.saas_api.schemas.team_config import TeamConfigurationCreate, TeamConfigurationUpdate
from src.saas_api.repositories.base import BaseRepository

class TeamConfigurationRepository(BaseRepository[TeamConfiguration, TeamConfigurationCreate, TeamConfigurationUpdate]):
    
    def __init__(self):
        super().__init__(TeamConfiguration)

    async def get_by_team_id(self, db: AsyncSession, team_id: str) -> Optional[TeamConfiguration]:
        result = await db.execute(select(self.model).where(self.model.team_id == team_id))
        return result.scalars().first()

    async def update_config(self, db: AsyncSession, db_obj: TeamConfiguration, obj_in: TeamConfigurationUpdate) -> TeamConfiguration:
        db_obj.config_data = obj_in.config_data
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

team_config_repo = TeamConfigurationRepository()
