from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, or_, func
from jose import JWTError

from app.db.session import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token
from app.core.deps import get_current_user
from app.models.user import User
from app.models.employee import Employee
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    TokenUser,
    RefreshTokenRequest,
    RefreshTokenResponse,
    CurrentUserResponse,
    ChangePasswordRequest,
)

router = APIRouter()


@router.post("/login", response_model=LoginResponse, summary="User Login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate user by email or employee code, and password.
    Returns access and refresh JWT tokens along with user information.
    """
    identifier = request.email.lower().strip()
    stmt = (
        select(User)
        .outerjoin(User.employee)
        .options(joinedload(User.employee))
        .where(
            or_(
                User.email == identifier,
                func.lower(Employee.employee_code) == identifier
            )
        )
    )
    user = db.execute(stmt).scalar_one_or_none()

    password_valid = False
    if user and user.password_hash:
        password_valid = verify_password(request.password, user.password_hash)
        if not password_valid and request.password != request.password.strip():
            password_valid = verify_password(request.password.strip(), user.password_hash)

    if not user or not password_valid:
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


@router.post("/change-password", summary="Change current user's password")
def change_password(
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Allows the logged-in user to change their password.
    """
    if not verify_password(req.old_password, current_user.password_hash) and not verify_password(req.old_password.strip(), current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password does not match"
        )

    current_user.password_hash = get_password_hash(req.new_password)
    db.commit()
    return {"status": "success", "message": "Password changed successfully"}

