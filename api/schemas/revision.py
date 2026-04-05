from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional
from api.models.revision import RevisionStatus

class DocumentationRevisionBase(BaseModel):
    endpoint_id: str
    original_content: str
    proposed_content: str

class DocumentationRevisionCreate(DocumentationRevisionBase):
    pass

class DocumentationRevisionUpdate(BaseModel):
    status: RevisionStatus

class DocumentationRevisionResponse(DocumentationRevisionBase):
    id: UUID
    team_id: UUID
    status: RevisionStatus
    submitted_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
