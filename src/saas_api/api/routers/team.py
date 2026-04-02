from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from src.saas_api.core.database import get_db
from src.saas_api.api.dependencies import get_current_active_user
from src.saas_api.models.user import User
from src.saas_api.schemas.team import TeamResponse, TeamCreate
from src.saas_api.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["Teams"])

def get_team_service(db: AsyncSession = Depends(get_db)) -> TeamService:
    return TeamService(db)

@router.post("/", response_model=TeamResponse)
async def create_team(
    team_in: TeamCreate,
    current_user: User = Depends(get_current_active_user),
    team_service: TeamService = Depends(get_team_service)
):
    """Create a new Team. The requesting user automatically becomes the ADMIN."""
    return await team_service.create_team(current_user.id, team_in)

@router.get("/me", response_model=List[TeamResponse])
async def read_my_teams(
    current_user: User = Depends(get_current_active_user),
    team_service: TeamService = Depends(get_team_service)
):
    """Retrieve a list of all Teams the current user belongs to."""
    return await team_service.get_my_teams(current_user.id)
