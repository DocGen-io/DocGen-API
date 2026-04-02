import uuid
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from src.saas_api.models.base import Base

def generate_uuid():
    return str(uuid.uuid4())

class TeamConfiguration(Base):
    __tablename__ = "team_configurations"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    team_id = Column(String, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # JSONB field for dynamic configurations (LLM models, storage choices).
    # Sensitive keys inside this JSONB will be symmetrically encrypted via Fernet before insert.
    config_data = Column(JSONB, nullable=False, server_default='{}')
