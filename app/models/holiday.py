from sqlalchemy import String, Text, Date, DateTime, Integer, ForeignKey, Enum as SQLEnum, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime
from typing import Optional, List, TYPE_CHECKING
from app.db.base import Base
from app.models.enums import HolidayType

if TYPE_CHECKING:
    from app.models.employee import Employee


class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[HolidayType] = mapped_column(
        SQLEnum(HolidayType, name="holiday_type", native_enum=True),
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    optional_selections: Mapped[List["EmployeeOptionalHoliday"]] = relationship(
        "EmployeeOptionalHoliday", back_populates="holiday", cascade="all, delete-orphan"
    )


class EmployeeOptionalHoliday(Base):
    __tablename__ = "employee_optional_holidays"
    __table_args__ = (
        UniqueConstraint("employee_id", "holiday_id", name="uq_emp_holiday"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    holiday_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("holidays.id", ondelete="CASCADE"), nullable=False
    )
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    holiday: Mapped["Holiday"] = relationship("Holiday", back_populates="optional_selections")
    employee: Mapped["Employee"] = relationship("Employee")
