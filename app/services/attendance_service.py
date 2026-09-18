import math
from datetime import datetime, timezone
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.employee import Employee
from app.models.office_location import OfficeLocation


def calculate_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on the earth (specified in decimal degrees)
    using the Haversine formula.
    """
    R = 6371000.0  # Radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


def validate_geofence(
    db: Session,
    employee: Employee,
    lat: float,
    lng: float
) -> Tuple[bool, float, OfficeLocation]:
    """
    Validate whether the provided coordinates fall within the employee's assigned office geofence.
    Raises HTTPException(400) if outside the allowed radius.
    """
    if not employee.office_location_id:
        # If no office location assigned, look for default office or allow
        office = db.execute(
            select(OfficeLocation).where(OfficeLocation.is_active == True).limit(1)
        ).scalar_one_or_none()
        if not office:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No office location configured for attendance check"
            )
    else:
        office = db.execute(
            select(OfficeLocation).where(OfficeLocation.id == employee.office_location_id)
        ).scalar_one_or_none()
        if not office or not office.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned office location is not active"
            )

    distance = calculate_distance_meters(
        float(lat), float(lng),
        float(office.latitude), float(office.longitude)
    )

    allowed_radius = office.radius_meters or 100
    if distance > allowed_radius:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You are {int(distance)}m from your office. Check-in not allowed."
        )

    return True, distance, office


def calculate_total_hours(check_in: datetime, check_out: datetime) -> float:
    """
    Compute duration in decimal hours rounded to 2 decimal places.
    """
    seconds = (check_out - check_in).total_seconds()
    if seconds < 0:
        return 0.0
    return round(seconds / 3600.0, 2)
