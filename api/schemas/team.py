from pydantic import BaseModel, ConfigDict
from typing import Optional
from api.models.team import TeamRole
from api.models.team_invitation import InvitationStatus, InvitationType


from api.schemas.user import UserResponse


# ── Team Schemas ──────────────────────────────────────────────────────────────

class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = True


class TeamUpdate(BaseModel):
    description: Optional[str] = None
    is_public: Optional[bool] = None


class TeamResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str] = None
    is_public: bool
    invite_token: Optional[str] = None  # Only returned to admins

    model_config = ConfigDict(from_attributes=True)


# ── Member Schemas ────────────────────────────────────────────────────────────

class MemberRoleUpdate(BaseModel):
    role: TeamRole


class MemberResponse(BaseModel):
    id: str
    user_id: str
    team_id: str
    role: TeamRole
    user: Optional[UserResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ── Invitation Schemas ────────────────────────────────────────────────────────

class InvitationRespond(BaseModel):
    accept: bool


class TeamInvitationResponse(BaseModel):
    id: str
    team_id: str
    invitee_user_id: str
    actor_user_id: str
    type: InvitationType
    status: InvitationStatus

    model_config = ConfigDict(from_attributes=True)
