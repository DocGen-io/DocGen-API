from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    source_type: str
    path: str

class ProjectCreate(ProjectBase):
    team_id: str

class ProjectResponse(ProjectBase):
    id: str
    team_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
