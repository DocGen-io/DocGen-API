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
    team_id = Column(String, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    submitted_by = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    source_type = Column(String, nullable=False)  # "git" or "local"
    path = Column(String, nullable=False)
    project_name = Column(String, nullable=True, index=True)
    credentials = Column(String, nullable=True)
    api_dir = Column(String, nullable=True)  # Optional subfolder for microservice API extraction

    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    result = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)

class JobLog(Base):
    __tablename__ = "generation_jobs_logs"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    job_id = Column(String, ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    level = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    logger = Column(String, nullable=True)
    timestamp = Column(String, nullable=False)
