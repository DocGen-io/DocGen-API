from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from shared.models import GenerationJob
from api.models.revision import DocumentationRevision, RevisionStatus
from api.models.project import Project
from api.models.team import TeamMember
from api.schemas.dashboard import DashboardStatsResponse


class DashboardService:
    """Service dedicated to fetching aggregated dashboard stats for a team."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_total_jobs(self, team_id: str) -> int:
        stmt = select(func.count(GenerationJob.id)).where(
            GenerationJob.team_id == team_id,
            GenerationJob.source_type.in_(["git", "local"])
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _get_pending_revisions(self, team_id: str) -> int:
        stmt = select(func.count(DocumentationRevision.id)).where(
            DocumentationRevision.team_id == team_id,
            DocumentationRevision.status == RevisionStatus.PENDING
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _get_total_projects(self, team_id: str) -> int:
        stmt = select(func.count(Project.id)).where(Project.team_id == team_id)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _get_total_members(self, team_id: str) -> int:
        stmt = select(func.count(TeamMember.id)).where(TeamMember.team_id == team_id)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_team_stats(self, team_id: str) -> DashboardStatsResponse:
        total_jobs = await self._get_total_jobs(team_id)
        pending_revisions = await self._get_pending_revisions(team_id)
        total_projects = await self._get_total_projects(team_id)
        total_members = await self._get_total_members(team_id)

        return DashboardStatsResponse(
            total_jobs=total_jobs,
            pending_revisions=pending_revisions,
            total_projects=total_projects,
            total_members=total_members
        )
