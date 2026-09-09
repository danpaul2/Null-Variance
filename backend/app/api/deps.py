"""
app/api/deps.py
---------------
FastAPI dependency functions for auth and DB access.
"""

import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.schemas.models import UserOut, UserRole
from app.db.database import SessionLocal
from app.repository.db_repository import DBRepository

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_db_session():
    """Yield a SQLAlchemy session; closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db(db: Session = Depends(get_db_session)) -> DBRepository:
    """Dependency that returns a DBRepository wrapping the current session."""
    return DBRepository(db)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    repo: DBRepository = Depends(get_db)
) -> UserOut:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user_dict = repo.get_user_by_email(email)
    if user_dict is None:
        raise credentials_exception
    return UserOut(
        id=user_dict["id"],
        email=user_dict["email"],
        full_name=user_dict["full_name"],
        role=user_dict["role"],
        is_active=user_dict["is_active"],
    )


def require_role(*roles: UserRole):
    def role_checker(current_user: UserOut = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return role_checker
