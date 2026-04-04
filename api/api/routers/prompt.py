from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from api.core.database import get_db
from api.api.dependencies import verify_team_membership
from api.schemas.prompt import PromptTemplateUpdate, PromptTemplateResponse
from api.services.prompt_service import PromptService

router = APIRouter(prefix="/teams/{team_id}/prompts", tags=["Prompts"])

def get_prompt_service(db: AsyncSession = Depends(get_db)) -> PromptService:
    return PromptService(db)

@router.get("/{name}", response_model=PromptTemplateResponse)
async def get_prompt(
    team_id: str,
    name: str,
    membership = Depends(verify_team_membership),
    prompt_service: PromptService = Depends(get_prompt_service)
):
    """Get the active prompt template (team override or system default)."""
    return await prompt_service.get_prompt_for_team(name, team_id)

@router.post("/{name}", response_model=PromptTemplateResponse)
async def override_prompt(
    team_id: str,
    name: str,
    prompt_data: PromptTemplateUpdate,
    membership = Depends(verify_team_membership),
    prompt_service: PromptService = Depends(get_prompt_service)
):
    """Override a system default prompt with a team-specific version."""
    return await prompt_service.override_prompt_for_team(name, team_id, prompt_data.content)

@router.delete("/{name}")
async def revert_prompt(
    team_id: str,
    name: str,
    membership = Depends(verify_team_membership),
    prompt_service: PromptService = Depends(get_prompt_service)
):
    """Revert a team-specific prompt override back to the system default."""
    return await prompt_service.revert_prompt_for_team(name, team_id)
