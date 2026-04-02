from typing import Optional
from pydantic import BaseModel, ConfigDict
from pydantic import BaseModel, ConfigDict

class PromptTemplateBase(BaseModel):
    name: str
    content: str
    is_system_default: bool = False

class PromptTemplateCreate(PromptTemplateBase):
    team_id: Optional[str] = None

class PromptTemplateUpdate(BaseModel):
    content: str

class PromptTemplateResponse(PromptTemplateBase):
    id: str
    team_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
