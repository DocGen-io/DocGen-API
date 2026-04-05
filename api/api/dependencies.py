from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from jose import jwt, JWTError

from api.core.database import get_db
from api.core.config import settings
from api.models.user import User
from api.models.team import TeamMember, TeamRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def verify_team_membership(
    team_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> TeamMember:
    result = await db.execute(select(TeamMember).where(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id
    ))
    member = result.scalars().first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this team")
    return member


async def verify_team_maintainer(
    member: TeamMember = Depends(verify_team_membership)
) -> TeamMember:
    """Allow ADMIN or MAINTAINER."""
    if member.role not in (TeamRole.ADMIN, TeamRole.MAINTAINER):
        raise HTTPException(status_code=403, detail="Maintainer or Admin privileges required")
    return member


async def verify_team_admin(
    member: TeamMember = Depends(verify_team_membership)
) -> TeamMember:
    """Allow ADMIN only."""
    if member.role != TeamRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return member
