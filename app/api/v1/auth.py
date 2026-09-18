from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select
from jose import JWTError

from app.db.session import get_db
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    TokenUser,
    RefreshTokenRequest,
    RefreshTokenResponse,
    CurrentUserResponse,
)

router = APIRouter()


@router.post("/login", response_model=LoginResponse, summary="User Login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user by email and password.
    Returns access and refresh JWT tokens along with user information.
    """
    stmt = (
        select(User)
        .options(joinedload(User.employee))
        .where(User.email == request.email.lower().strip())
    )
    user = db.execute(stmt).scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    # Update last login timestamp
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "employee_id": user.employee_id
    }
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)

    full_name = user.employee.full_name if user.employee else None

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=TokenUser(
            id=user.id,
            employee_id=user.employee_id,
            role=user.role.value,
            full_name=full_name
        )
    )


@router.post("/refresh", response_model=RefreshTokenResponse, summary="Refresh Access Token")
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Generate a new access token using a valid refresh token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(request.refresh_token)
        user_id_str = payload.get("sub")
        token_type = payload.get("type")
        if user_id_str is None or token_type != "refresh":
            raise credentials_exception
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exception

    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "employee_id": user.employee_id
    }
    new_access_token = create_access_token(data=token_data)

    return RefreshTokenResponse(
        access_token=new_access_token,
        token_type="bearer"
    )


@router.get("/me", response_model=CurrentUserResponse, summary="Get Current Authenticated User")
def get_me(current_user: User = Depends(get_current_user)):
    """
    Fetch details of the currently authenticated user.
    """
    return CurrentUserResponse(
        id=current_user.id,
        employee_id=current_user.employee_id,
        email=current_user.email,
        role=current_user.role.value
    )
