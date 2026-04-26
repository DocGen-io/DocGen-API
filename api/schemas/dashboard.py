from pydantic import BaseModel, ConfigDict

class DashboardStatsResponse(BaseModel):
    total_jobs: int
    pending_revisions: int
    total_projects: int
    total_members: int

    model_config = ConfigDict(from_attributes=True)
