from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.models.employee import Employee
from app.models.leave import LeaveType, LeaveBalance


def generate_next_employee_code(db: Session) -> str:
    """
    Generate sequential employee code: EMP0001, EMP0002, etc.
    """
    max_id = db.execute(select(func.max(Employee.id))).scalar_one_or_none()
    next_num = (max_id or 0) + 1
    
    code = f"EMP{next_num:04d}"
    # Verify uniqueness
    while db.execute(select(Employee.id).where(Employee.employee_code == code)).scalar_one_or_none():
        next_num += 1
        code = f"EMP{next_num:04d}"
        
    return code


def initialize_leave_balances(db: Session, employee_id: int, year: int = None) -> None:
    """
    Initialize standard annual leave balances for a newly created employee.
    """
    if year is None:
        year = datetime.now().year

    leave_types = db.execute(select(LeaveType)).scalars().all()
    for lt in leave_types:
        existing = db.execute(
            select(LeaveBalance).where(
                LeaveBalance.employee_id == employee_id,
                LeaveBalance.leave_type_id == lt.id,
                LeaveBalance.year == year
            )
        ).scalar_one_or_none()

        if not existing:
            balance = LeaveBalance(
                employee_id=employee_id,
                leave_type_id=lt.id,
                year=year,
                total_allotted=float(lt.default_days_per_year),
                used=0.0,
                balance=float(lt.default_days_per_year)
            )
            db.add(balance)
