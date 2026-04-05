from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.schemas.user import UserCreate, UserResponse
from api.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate, 
    auth_service: AuthService = Depends(get_auth_service)
):
    """Register a new user through the authentication service."""
    return await auth_service.register_new_user(user_data)

@router.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    auth_service: AuthService = Depends(get_auth_service)
):
    """Authenticate user and return JWT access + refresh tokens."""
    return await auth_service.authenticate_user(
        login_identifier=form_data.username, 
        password=form_data.password
    )

@router.post("/refresh")
async def refresh_access_token(
    body: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Exchange a valid refresh token for a new access + refresh token pair."""
    return await auth_service.refresh_access_token(body.refresh_token)
