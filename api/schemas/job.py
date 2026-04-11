from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class JobCreate(BaseModel):
    source_type: str
    path: str
    project_name: Optional[str] = None
    credentials: Optional[str] = None
    api_dir: Optional[str] = None  # Subfolder to target for API extraction (microservices)


class JobResponse(BaseModel):
    id: str
    team_id: str
    submitted_by: Optional[str] = None
    source_type: str
    path: str
    project_name: Optional[str] = None
    api_dir: Optional[str] = None
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LogEntry(BaseModel):
    id: str
    job_id: str
    level: str
    message: str
    logger: Optional[str] = None
    timestamp: str

    model_config = ConfigDict(from_attributes=True)


class JobStatusResponse(BaseModel):
    job: JobResponse
    logs: List[LogEntry] = []

    model_config = ConfigDict(from_attributes=True)


class ExampleGenerationRequest(BaseModel):
    path: str
    method: str
