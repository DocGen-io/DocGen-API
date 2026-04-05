# The Auth router should be importable as a module
from api.api.routers.auth import router as auth_router
from api.api.routers.team_config import router as team_config_router
from api.api.routers.prompt import router as prompt_router
from api.api.routers.team import router as team_router
from api.api.routers.jobs import router as jobs_router
from api.api.routers.revisions import router as revisions_router
from api.api.routers.logs import router as logs_router
from api.api.routers.traces import router as traces_router

__all__ = [
    "auth_router", "team_config_router", "prompt_router", "team_router",
    "jobs_router", "revisions_router", "logs_router", "traces_router",
]
