from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.core.deps import get_current_user, require_role
from app.models.office_location import OfficeLocation
from app.models.enums import UserRole
from app.schemas.office_location import OfficeLocationRead, OfficeLocationCreate

router = APIRouter()


@router.get("", response_model=List[OfficeLocationRead], summary="List all office locations")
def list_office_locations(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all registered office locations for geofencing.
    """
    locations = db.execute(select(OfficeLocation).order_by(OfficeLocation.name)).scalars().all()
    return locations


@router.post("", response_model=OfficeLocationRead, status_code=status.HTTP_201_CREATED, summary="Create office location")
def create_office_location(
    loc_in: OfficeLocationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_role([UserRole.super_admin, UserRole.hr_admin]))
):
    """
    Register a new office location (HR / Super Admin only).
    """
    location = OfficeLocation(
        name=loc_in.name,
        latitude=loc_in.latitude,
        longitude=loc_in.longitude,
        radius_meters=loc_in.radius_meters or 100,
        is_active=loc_in.is_active if loc_in.is_active is not None else True
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location
