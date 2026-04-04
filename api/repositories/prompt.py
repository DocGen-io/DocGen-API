from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.future import select

from api.models.prompt import PromptTemplate
from api.schemas.prompt import PromptTemplateCreate, PromptTemplateUpdate
from api.repositories.base import BaseRepository

class PromptTemplateRepository(BaseRepository[PromptTemplate, PromptTemplateCreate, PromptTemplateUpdate]):
    
    def __init__(self):
        super().__init__(PromptTemplate)

    async def get_by_name_and_team(self, db: AsyncSession, name: str, team_id: str) -> Optional[PromptTemplate]:
        result = await db.execute(
            select(self.model).where(self.model.name == name, self.model.team_id == team_id)
        )
        return result.scalars().first()

    async def get_system_default(self, db: AsyncSession, name: str) -> Optional[PromptTemplate]:
        result = await db.execute(
            select(self.model).where(self.model.name == name, self.model.is_system_default == True, self.model.team_id == None)
        )
        return result.scalars().first()
        
    async def get_all_for_team(self, db: AsyncSession, team_id: str) -> List[PromptTemplate]:
        result = await db.execute(select(self.model).where(self.model.team_id == team_id))
        return result.scalars().all() # type: ignore

prompt_repo = PromptTemplateRepository()
