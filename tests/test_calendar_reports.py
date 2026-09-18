import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)


def get_admin_token() -> str:
    res = client.post("/auth/login", json={
        "email": settings.FIRST_SUPER_ADMIN_EMAIL,
        "password": settings.FIRST_SUPER_ADMIN_PASSWORD
    })
    return res.json()["access_token"]


def create_test_employee() -> dict:
    admin_token = get_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}"}
    uid = uuid.uuid4().hex[:6]
    email = f"cal.rep.{uid}@company.com"
    pwd = "Password123!"

    create_res = client.post("/employees", json={
        "full_name": f"CalRep Tester {uid}",
        "email": email,
        "password": pwd,
        "department_id": 2,
        "office_location_id": 1,
        "role": "employee"
    }, headers=headers)
    assert create_res.status_code == 201

    login_res = client.post("/auth/login", json={"email": email, "password": pwd})
    token = login_res.json()["access_token"]

    return {
        "employee_id": create_res.json()["id"],
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"}
    }


def test_team_calendar_merged_view():
    admin_token = get_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create a holiday for 2026-09-20
    client.post("/holidays", json={
        "name": "Mid-Autumn Festival",
        "date": "2026-09-20",
        "type": "festival",
        "year": 2026
    }, headers=headers)

    # 2. Fetch team calendar for Sept 2026
    cal_res = client.get("/calendar/team?month=9&year=2026", headers=headers)
    assert cal_res.status_code == 200
    data = cal_res.json()
    assert "days" in data
    # 2026-09-20 must have the holiday
    assert "2026-09-20" in data["days"]
    events = data["days"]["2026-09-20"]
    assert any(e["type"] == "holiday" and e["holiday_name"] == "Mid-Autumn Festival" for e in events)


def test_employee_day_detail():
    user = create_test_employee()
    admin_token = get_admin_token()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    uid = uuid.uuid4().hex[:6]

    # Create project and task
    proj_res = client.post("/projects", json={"name": f"Day Detail Proj {uid}"}, headers=admin_headers)
    proj_id = proj_res.json()["id"]

    task_res = client.post("/tasks", json={
        "project_id": proj_id,
        "assigned_to": user["employee_id"],
        "title": "Build UI wireframe"
    }, headers=admin_headers)
    task_id = task_res.json()["id"]

    # Log task work on 2026-09-17
    client.post(f"/tasks/{task_id}/log", json={
        "log_date": "2026-09-17",
        "hours_spent": 4.0,
        "notes": "Wireframe work"
    }, headers=user["headers"])

    # Fetch day detail for user on 2026-09-17
    detail_res = client.get(f"/calendar/day/{user['employee_id']}/2026-09-17", headers=admin_headers)
    assert detail_res.status_code == 200
    day_data = detail_res.json()
    assert day_data["employee"]["id"] == user["employee_id"]
    assert len(day_data["task_logs"]) >= 1
    assert day_data["task_logs"][0]["hours_spent"] == 4.0


def test_dashboard_reports():
    admin_token = get_admin_token()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Admin report
    admin_rep = client.get("/reports/dashboard", headers=admin_headers)
    assert admin_rep.status_code == 200
    rep_data = admin_rep.json()
    assert rep_data["headcount"] >= 1
    assert "today_attendance_pct" in rep_data
    assert "pending_leave_approvals" in rep_data
    assert "active_projects" in rep_data
    assert len(rep_data["leave_trend_last_6_months"]) == 6

    # Employee report
    user = create_test_employee()
    emp_rep = client.get("/reports/dashboard", headers=user["headers"])
    assert emp_rep.status_code == 200
    emp_data = emp_rep.json()
    assert emp_data["headcount"] == 1
    assert len(emp_data["leave_trend_last_6_months"]) == 6
