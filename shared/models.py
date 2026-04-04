"""
GenerationJob model — shared between SaaS API and Worker.

The SaaS API creates job records; the Worker updates their status.
"""
import uuid
import enum
from sqlalchemy import Column, String, Text, Enum as SQLEnum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from api.models.base import Base


def generate_uuid():
    return str(uuid.uuid4())


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    team_id = Column(String, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    submitted_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    source_type = Column(String, nullable=False)  # "git" or "local"
    path = Column(String, nullable=False)
    credentials = Column(String, nullable=True)

    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    result = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)
