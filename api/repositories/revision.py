from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.revision import DocumentationRevision, RevisionStatus
from api.repositories.base import BaseRepository

from api.schemas.revision import DocumentationRevisionCreate, DocumentationRevisionUpdate

class RevisionRepository(BaseRepository[DocumentationRevision, DocumentationRevisionCreate, DocumentationRevisionUpdate]):
    def __init__(self):
        super().__init__(model=DocumentationRevision)

    async def get_by_team(self, db: AsyncSession, team_id: str, status: Optional[RevisionStatus] = None) -> List[DocumentationRevision]:
        """
        Get all revisions for a specific team, optionally filtered by status.
        """
        query = select(self.model).where(self.model.team_id == team_id)
        if status:
            query = query.where(self.model.status == status)
        query = query.order_by(self.model.created_at.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_by_id_and_team(self, db: AsyncSession, revision_id: str, team_id: str) -> Optional[DocumentationRevision]:
        """
        Get a specific revision ensuring it belongs to the team.
        """
        query = select(self.model).where(
            self.model.id == revision_id,
            self.model.team_id == team_id
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()
        
    async def create_revision(self, db: AsyncSession, *, team_id: str, submitted_by: str, obj_in: DocumentationRevisionCreate) -> DocumentationRevision:
        db_obj = DocumentationRevision(
            team_id=team_id,
            submitted_by=submitted_by,
            endpoint_id=obj_in.endpoint_id,
            original_content=obj_in.original_content,
            proposed_content=obj_in.proposed_content,
            status=RevisionStatus.PENDING
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

revision_repo = RevisionRepository()

