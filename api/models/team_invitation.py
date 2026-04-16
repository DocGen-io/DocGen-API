from sqlalchemy import Column, String, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum
import uuid

from api.models.base import Base


def generate_uuid():
    return str(uuid.uuid4())


class InvitationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class InvitationType(str, enum.Enum):
    INVITE = "INVITE"    # Admin-initiated: admin invites a user
    REQUEST = "REQUEST"  # User-initiated: user requests to join


class TeamInvitation(Base):
    __tablename__ = "team_invitations"

    id = Column(String, primary_key=True, default=generate_uuid)
    team_id = Column(String, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)

    # The user being invited or requesting
    invitee_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # The user who triggered the action (admin for INVITE, the user themselves for REQUEST)
    actor_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    type = Column(SQLEnum(InvitationType), nullable=False)
    status = Column(SQLEnum(InvitationStatus), default=InvitationStatus.PENDING, nullable=False)

    # Relationships
    team = relationship("Team", back_populates="invitations")
    invitee = relationship("User", foreign_keys=[invitee_user_id])
    actor = relationship("User", foreign_keys=[actor_user_id])
