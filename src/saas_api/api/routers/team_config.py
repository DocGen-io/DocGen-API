from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.saas_api.core.database import get_db
from src.saas_api.api.dependencies import verify_team_membership
from src.saas_api.services.team_config_service import TeamConfigService

router = APIRouter(prefix="/teams/{team_id}/config", tags=["Team Configuration"])

def get_team_config_service(db: AsyncSession = Depends(get_db)) -> TeamConfigService:
    return TeamConfigService(db)

@router.get("/")
async def get_team_config(
    team_id: str,
    membership = Depends(verify_team_membership),
    config_service: TeamConfigService = Depends(get_team_config_service)
):
    """Get dynamic configurations for the team."""
    config = await config_service.get_team_config(team_id)
    return config or {}

from src.saas_api.schemas.team_config import TeamConfigurationUpdate

@router.post("/")
async def upsert_team_config(
    team_id: str,
    payload: TeamConfigurationUpdate,
    membership = Depends(verify_team_membership),
    config_service: TeamConfigService = Depends(get_team_config_service)
):
    """Set dynamic configurations for the team (secrets will be securely encrypted)."""
    return await config_service.upsert_team_config(team_id, payload.config_data)
