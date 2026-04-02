from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
import uuid

from src.saas_api.models.base import Base

def generate_uuid():
    return str(uuid.uuid4())

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, index=True, nullable=False)
    team_id = Column(String, ForeignKey("teams.id"), nullable=False)
    description = Column(String, nullable=True)
    # The source type (e.g., git, local) and path
    source_type = Column(String, nullable=False)
    path = Column(String, nullable=False)

    # Relationships
    team = relationship("Team", back_populates="projects")
