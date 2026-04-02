# The Auth router should be importable as a module
from src.saas_api.api.routers.auth import router as auth_router
from src.saas_api.api.routers.team_config import router as team_config_router
from src.saas_api.api.routers.prompt import router as prompt_router
from src.saas_api.api.routers.team import router as team_router
from src.saas_api.api.routers.jobs import router as jobs_router

__all__ = ["auth_router", "team_config_router", "prompt_router", "team_router", "jobs_router"]
