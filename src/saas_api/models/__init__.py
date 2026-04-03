from src.saas_api.models.base import Base
from src.saas_api.models.user import User
from src.saas_api.models.team import Team, TeamMember, TeamRole
from src.saas_api.models.project import Project
from src.saas_api.models.team_config import TeamConfiguration
from src.saas_api.models.prompt import PromptTemplate

# Lazy import to avoid circular dependency:
# shared.models → src.saas_api.models.base → this __init__ → shared.models
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

# Expose models for Alembic auto-generation
__all__ = ["Base", "User", "Team", "TeamMember", "TeamRole", "Project", "TeamConfiguration", "PromptTemplate", "GenerationJob", "JobStatus"]

