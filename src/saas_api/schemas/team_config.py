from typing import Dict, Any, Optional
from pydantic import BaseModel, ConfigDict
from pydantic import BaseModel, ConfigDict

class TeamConfigurationBase(BaseModel):
    # This will be raw JSON, where sensitive credentials are sent unencrypted to the API,
    # but the API encrypts them before passing to the Repository.
    config_data: Dict[str, Any]

class TeamConfigurationCreate(TeamConfigurationBase):
    team_id: str

class TeamConfigurationUpdate(TeamConfigurationBase):
    pass

class TeamConfigurationResponse(TeamConfigurationBase):
    id: str
    team_id: str

    model_config = ConfigDict(from_attributes=True)
