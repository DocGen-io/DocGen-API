from pydantic import BaseModel, ConfigDict
from api.models.team import TeamRole

class TeamBase(BaseModel):
    name: str
    description: str | None = None

class TeamCreate(TeamBase):
    pass

class TeamResponse(TeamBase):
    id: str

    model_config = ConfigDict(from_attributes=True)
