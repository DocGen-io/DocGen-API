from fastapi import HTTPException, status
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.user import User
from api.schemas.user import UserCreate
from api.core.security import verify_password, create_access_token
from api.core.config import settings
from api.repositories.user import user_repo

class AuthService:
    """Service layer representing pure business logic decoupled from raw database queries.
       Uses Repositories to interact with the data access layer.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_new_user(self, user_data: UserCreate) -> User:
        existing_email = await user_repo.get_by_email(self.db, user_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
            
        existing_username = await user_repo.get_by_username(self.db, user_data.username)
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        
        # Pass DTO to repository to physically create the DB record
        user = await user_repo.create(self.db, obj_in=user_data)

        # Auto-provision personal team for every new user
        from api.services.team_service import TeamService
        await TeamService(self.db).create_default_team(user.id, user.username)

        return user

    async def authenticate_user(self, login_identifier: str, password: str) -> dict[str, str]:
        if "@" in login_identifier:
            user = await user_repo.get_by_email(self.db, login_identifier)
        else:
            user = await user_repo.get_by_username(self.db, login_identifier)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            subject=user.id, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}

