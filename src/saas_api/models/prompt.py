import uuid
from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from src.saas_api.models.base import Base

def generate_uuid():
    return str(uuid.uuid4())

class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    name = Column(String, index=True, nullable=False)
    content = Column(Text, nullable=False)
    is_system_default = Column(Boolean, default=False, nullable=False)
    
    # If team_id is null, it's a global system default template.
    team_id = Column(String, ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
