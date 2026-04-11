from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from api.models.base import Base

def generate_uuid():
    return str(uuid.uuid4())

class ProjectGrouping(Base):
    __tablename__ = "project_groupings"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Stores the clusters: { "Group Name": ["method path", ...], ... }
    # Also includes api_details if provided during creation
    clusters = Column(JSONB, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project")
