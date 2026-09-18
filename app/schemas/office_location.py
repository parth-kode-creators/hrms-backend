from pydantic import BaseModel, ConfigDict
from typing import Optional


class OfficeLocationBase(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_meters: Optional[int] = 100
    is_active: Optional[bool] = True


class OfficeLocationCreate(OfficeLocationBase):
    pass


class OfficeLocationRead(OfficeLocationBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class OfficeLocationSimple(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)
