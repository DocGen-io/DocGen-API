import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from celery import Celery

from api.models.revision import DocumentationRevision, RevisionStatus
from api.schemas.revision import DocumentationRevisionCreate
from api.repositories.revision import revision_repo
from api.core.config import settings

_celery_client = Celery(
    "docgen_dispatcher",
    broker=settings.REDIS_URL,
)

import logging
logger = logging.getLogger(__name__)

class RevisionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def propose_revision(self, team_id: str, submitted_by: str, data: DocumentationRevisionCreate) -> DocumentationRevision:
        revision = await revision_repo.create_revision(
            self.db,
            team_id=team_id,
            submitted_by=submitted_by,
            obj_in=data
        )
        return revision

    async def list_revisions(self, team_id: str, status: Optional[str] = None) -> List[DocumentationRevision]:
        filter_status = RevisionStatus(status) if status else None
        return await revision_repo.get_by_team(self.db, team_id, filter_status)

    async def approve_revision(self, team_id: str, revision_id: str) -> DocumentationRevision:
        logger.info(f"Approving revision {revision_id} for team {team_id}")
        revision = await revision_repo.get_by_id_and_team(self.db, revision_id, team_id)
        if not revision:
            logger.warning(f"Revision {revision_id} not found in team {team_id}")
            raise ValueError("Revision not found or does not belong to team.")
        if revision.status != RevisionStatus.PENDING:
            raise ValueError("Only PENDING revisions can be approved.")

        revision = await revision_repo.update(self.db, db_obj=revision, obj_in={"status": RevisionStatus.APPROVED})
        
        # Dispatch Celery worker task to patch Weaviate
        _celery_client.send_task(
            "worker.tasks.update_weaviate_documentation_chunk",
            kwargs={
                "team_id": str(revision.team_id),
                "endpoint_id": revision.endpoint_id,
                "proposed_content": revision.proposed_content
            }
        )
        return revision

    async def reject_revision(self, team_id: str, revision_id: str) -> DocumentationRevision:
        logger.info(f"Rejecting revision {revision_id} for team {team_id}")
        revision = await revision_repo.get_by_id_and_team(self.db, revision_id, team_id)
        if not revision:
            logger.warning(f"Revision {revision_id} not found in team {team_id}")
            raise ValueError("Revision not found or does not belong to team.")
        if revision.status != RevisionStatus.PENDING:
            raise ValueError("Only PENDING revisions can be rejected.")
            
        revision = await revision_repo.update(self.db, db_obj=revision, obj_in={"status": RevisionStatus.REJECTED})
        return revision
