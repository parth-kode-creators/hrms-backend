from datetime import date
from sqlalchemy import select
from app.db.session import SessionLocal
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.enums import UserRole
from app.models.office_location import OfficeLocation
from app.models.department import Department
from app.models.employee import Employee
from app.models.user import User
from app.models.leave import LeaveType, LeaveBalance


def init_db() -> None:
    db = SessionLocal()
    try:
        print("--- Initializing HRMS Database ---")

        # 1. Seed Office Location
        head_office = db.execute(
            select(OfficeLocation).where(OfficeLocation.name == "Head Office")
        ).scalar_one_or_none()
        if not head_office:
            head_office = OfficeLocation(
                name="Head Office",
                latitude=22.307159,
                longitude=73.181219,
                radius_meters=settings.DEFAULT_GEOFENCE_RADIUS_METERS,
                is_active=True
            )
            db.add(head_office)
            db.flush()
            print(f"Created default Office Location: {head_office.name} (id={head_office.id})")
        else:
            print(f"Office Location already exists: {head_office.name}")

        # 2. Seed Departments
        dept_names = ["Human Resources", "Engineering", "Sales & Marketing", "Finance"]
        departments = {}
        for dname in dept_names:
            dept = db.execute(select(Department).where(Department.name == dname)).scalar_one_or_none()
            if not dept:
                dept = Department(name=dname)
                db.add(dept)
                db.flush()
                print(f"Created Department: {dname} (id={dept.id})")
            departments[dname] = dept

        # 3. Seed Default Leave Types
        leave_types_data = [
            {"name": "Casual", "days": 12, "paid": True, "carry_forward": False},
            {"name": "Sick", "days": 8, "paid": True, "carry_forward": False},
            {"name": "Privilege", "days": 15, "paid": True, "carry_forward": True},
        ]
        leave_types = []
        for lt_data in leave_types_data:
            lt = db.execute(select(LeaveType).where(LeaveType.name == lt_data["name"])).scalar_one_or_none()
            if not lt:
                lt = LeaveType(
                    name=lt_data["name"],
                    default_days_per_year=lt_data["days"],
                    is_paid=lt_data["paid"],
                    carry_forward=lt_data["carry_forward"]
                )
                db.add(lt)
                db.flush()
                print(f"Created Leave Type: {lt.name} ({lt.default_days_per_year} days/yr)")
            leave_types.append(lt)

        # 4. Seed Super Admin Employee
        admin_email = settings.FIRST_SUPER_ADMIN_EMAIL
        admin_emp = db.execute(select(Employee).where(Employee.email == admin_email)).scalar_one_or_none()
        if not admin_emp:
            admin_emp = Employee(
                employee_code="EMP0001",
                full_name=settings.FIRST_SUPER_ADMIN_NAME,
                email=admin_email,
                phone="9998887777",
                department_id=departments["Human Resources"].id,
                designation="System Administrator / HR Director",
                date_of_joining=date(2026, 1, 1),
                office_location_id=head_office.id,
                status="active"
            )
            db.add(admin_emp)
            db.flush()
            print(f"Created Super Admin Employee: {admin_emp.full_name} ({admin_emp.employee_code})")
        else:
            print(f"Admin Employee already exists: {admin_emp.full_name}")

        # 5. Seed Super Admin User Login
        admin_user = db.execute(select(User).where(User.email == admin_email)).scalar_one_or_none()
        if not admin_user:
            admin_user = User(
                employee_id=admin_emp.id,
                email=admin_email,
                password_hash=get_password_hash(settings.FIRST_SUPER_ADMIN_PASSWORD),
                role=UserRole.super_admin,
                is_active=True
            )
            db.add(admin_user)
            db.flush()
            print(f"Created Super Admin User Account: {admin_user.email} (role={admin_user.role.value})")
        else:
            print(f"Admin User Account already exists: {admin_user.email}")

        # 6. Initialize Leave Balances for 2026 for Admin
        current_year = 2026
        for lt in leave_types:
            bal = db.execute(
                select(LeaveBalance).where(
                    LeaveBalance.employee_id == admin_emp.id,
                    LeaveBalance.leave_type_id == lt.id,
                    LeaveBalance.year == current_year
                )
            ).scalar_one_or_none()
            if not bal:
                bal = LeaveBalance(
                    employee_id=admin_emp.id,
                    leave_type_id=lt.id,
                    year=current_year,
                    total_allotted=float(lt.default_days_per_year),
                    used=0.0,
                    balance=float(lt.default_days_per_year)
                )
                db.add(bal)
                print(f"Allocated {lt.name} balance: {bal.balance} days for {current_year}")

        db.commit()
        print("Database initialization completed successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error during DB initialization: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
