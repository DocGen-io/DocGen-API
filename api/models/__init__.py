from api.models.base import Base
from api.models.user import User
from api.models.team import Team, TeamMember, TeamRole
from api.models.team_invitation import TeamInvitation, InvitationStatus, InvitationType
from api.models.project import Project
from api.models.team_config import TeamConfiguration
from api.models.prompt import PromptTemplate
from api.models.revision import DocumentationRevision, RevisionStatus
from api.models.grouping import ProjectGrouping

# Lazy import to avoid circular dependency:
# shared.models → api.models.base → this __init__ → shared.models
def _load_shared_models():
    from shared.models import GenerationJob, JobStatus
    return GenerationJob, JobStatus

def __getattr__(name):
    if name in ("GenerationJob", "JobStatus"):
        GenerationJob, JobStatus = _load_shared_models()
        globals()["GenerationJob"] = GenerationJob
        globals()["JobStatus"] = JobStatus
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "Base", "User", "Team", "TeamMember", "TeamRole",
    "TeamInvitation", "InvitationStatus", "InvitationType",
    "Project", "TeamConfiguration", "PromptTemplate",
    "GenerationJob", "JobStatus",
    "DocumentationRevision", "RevisionStatus",
    "ProjectGrouping",
]
