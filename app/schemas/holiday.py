from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from app.models.enums import HolidayType


class HolidayItem(BaseModel):
    id: int
    name: str
    date: date
    type: str

    model_config = ConfigDict(from_attributes=True)


class HolidayListResponse(BaseModel):
    items: List[HolidayItem]


class HolidayCreate(BaseModel):
    name: str
    date: date
    type: HolidayType
    year: int
    description: Optional[str] = None


class HolidayDetail(BaseModel):
    id: int
    name: str
    date: date
    type: str
    year: int
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SelectOptionalResponse(BaseModel):
    employee_id: int
    holiday_id: int
    selected_at: datetime

    model_config = ConfigDict(from_attributes=True)
