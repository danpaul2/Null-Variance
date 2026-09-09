from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import jwt

from app.schemas.models import TokenResponse, UserOut, LoginRequest
from app.api.deps import get_store, get_current_user, SECRET_KEY, ALGORITHM
from app.repository.memory_store import MemoryStore, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest, store: MemoryStore = Depends(get_store)):
    user_dict = store.get_user_by_email(login_data.email)
    if not user_dict:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    hashed_password = user_dict.get("hashed_password")
    if not hashed_password or not verify_password(login_data.password, hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.utcnow() + access_token_expires
    to_encode = {"sub": user_dict["email"], "exp": expire}
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=user_dict["role"],
        username=user_dict["full_name"]
    )

@router.get("/me", response_model=UserOut)
def get_me(current_user: UserOut = Depends(get_current_user)):
    return current_user
