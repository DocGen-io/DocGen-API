from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class JobCreate(BaseModel):
    source_type: str
    path: str
    credentials: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    team_id: str
    submitted_by: Optional[str] = None
    source_type: str
    path: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
