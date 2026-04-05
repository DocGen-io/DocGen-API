from datetime import datetime, timedelta
from typing import Optional, Union, Any
from jose import jwt
from passlib.context import CryptContext
from api.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    subject: Union[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_refresh_token(token: str) -> str:
    """Decode a refresh token and return the user_id. Raises ValueError on failure."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        user_id: str = payload.get("sub")
        if not user_id:
            raise ValueError("Missing subject")
        return user_id
    except jwt.ExpiredSignatureError:
        raise ValueError("Refresh token expired")
    except jwt.JWTError as exc:
        raise ValueError(f"Invalid token: {exc}")

# Symmetric Encryption for JSONB fields
from cryptography.fernet import Fernet
fernet = Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_value(value: str | None) -> str | None:
    if not value:
        return value
    return fernet.encrypt(value.encode()).decode()

def decrypt_value(value: str | None) -> str | None:
    if not value:
        return value
    return fernet.decrypt(value.encode()).decode()
