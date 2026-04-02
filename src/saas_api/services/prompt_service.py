from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from src.saas_api.models.prompt import PromptTemplate
from src.saas_api.schemas.prompt import PromptTemplateCreate, PromptTemplateUpdate
from src.saas_api.repositories.prompt import prompt_repo

class PromptService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_prompt_for_team(self, name: str, team_id: str) -> PromptTemplate:
        # First check if the team has an override
        team_prompt = await prompt_repo.get_by_name_and_team(self.db, name, team_id)
        if team_prompt:
            return team_prompt
            
        # Fall back to system default
        system_prompt = await prompt_repo.get_system_default(self.db, name)
        if not system_prompt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt template not found")
        return system_prompt

    async def override_prompt_for_team(self, name: str, team_id: str, content: str) -> PromptTemplate:
        # Ensure system default actually exists for this name before allowing override
        sys_prompt = await prompt_repo.get_system_default(self.db, name)
        if not sys_prompt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cannot override unknown system prompt")

        team_prompt = await prompt_repo.get_by_name_and_team(self.db, name, team_id)
        if team_prompt:
            # Update existing override
            team_prompt.content = content
            self.db.add(team_prompt)
            await self.db.commit()
            await self.db.refresh(team_prompt)
            return team_prompt
        else:
            # Create override
            obj_in = PromptTemplateCreate(name=name, content=content, is_system_default=False, team_id=team_id)
            return await prompt_repo.create(self.db, obj_in=obj_in)

    async def revert_prompt_for_team(self, name: str, team_id: str) -> dict:
        team_prompt = await prompt_repo.get_by_name_and_team(self.db, name, team_id)
        if team_prompt:
            await prompt_repo.delete(self.db, id=team_prompt.id)
            return {"status": "reverted to system default"}
        return {"status": "no override found, already using system default"}
