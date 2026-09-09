from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt

from app.schemas.models import TokenResponse, UserOut, LoginRequest
from app.api.deps import get_db, get_current_user, SECRET_KEY, ALGORITHM
from app.repository.db_repository import DBRepository, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest, repo: DBRepository = Depends(get_db)):
    user_dict = repo.get_user_by_email(login_data.email)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    hashed_password = user_dict.get("hashed_password")
    if not hashed_password or not verify_password(login_data.password, hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = jwt.encode({"sub": user_dict["email"], "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=user_dict["role"],
        username=user_dict["full_name"]
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: UserOut = Depends(get_current_user)):
    return current_user
