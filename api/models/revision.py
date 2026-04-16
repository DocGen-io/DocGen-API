from sqlalchemy import Column, String, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
import uuid
import enum

from api.models.base import Base

class RevisionStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

class DocumentationRevision(Base):
    """
    Represents a proposed change to a specific Weaviate documentation endpoint chunk.
    """
    __tablename__ = "documentation_revisions"

    id = Column(String(255), primary_key=True, default=lambda: uuid.uuid4().hex)
    team_id = Column(String(255), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint_id = Column(String(255), nullable=False, index=True)  # Weaviate node_id or similar UI ref
    
    original_content = Column(Text, nullable=False)
    proposed_content = Column(Text, nullable=False)
    
    status = Column(Enum(RevisionStatus), default=RevisionStatus.PENDING, nullable=False)
    
    submitted_by = Column(String(255), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Relationships
    team = relationship("Team")
    submitter = relationship("User")

    def __repr__(self):
        return f"<DocumentationRevision(id={self.id}, endpoint_id='{self.endpoint_id}', status='{self.status}')>"
