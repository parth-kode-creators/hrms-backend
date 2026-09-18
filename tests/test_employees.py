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


def test_department_crud():
    admin_token = get_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}"}

    # List departments
    list_res = client.get("/departments", headers=headers)
    assert list_res.status_code == 200
    depts = list_res.json()
    assert len(depts) >= 2  # Human Resources and Engineering seeded in Phase 1

    # Create new unique department as Admin
    uid = uuid.uuid4().hex[:6]
    create_res = client.post("/departments", json={"name": f"Product Design {uid}"}, headers=headers)
    assert create_res.status_code == 201
    assert f"Product Design {uid}" in create_res.json()["name"]


def test_create_employee_flow():
    admin_token = get_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}"}

    uid = uuid.uuid4().hex[:6]
    test_email = f"jane.{uid}@company.com"

    # Create Employee as Admin
    payload = {
        "full_name": f"Jane Smith {uid}",
        "email": test_email,
        "phone": "9998887777",
        "department_id": 2,  # Engineering
        "designation": "Software Engineer",
        "date_of_joining": "2026-01-15",
        "office_location_id": 1,
        "password": "JanePassword123!",
        "role": "employee"
    }
    create_res = client.post("/employees", json=payload, headers=headers)
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["full_name"] == f"Jane Smith {uid}"
    assert data["employee_code"].startswith("EMP")
    assert data["status"] == "active"
    assert data["department"]["name"] == "Engineering"

    # Verify that Jane can log in with her new user account
    login_res = client.post("/auth/login", json={
        "email": test_email,
        "password": "JanePassword123!"
    })
    assert login_res.status_code == 200
    jane_token = login_res.json()["access_token"]

    # Verify that Jane can fetch her own profile
    jane_headers = {"Authorization": f"Bearer {jane_token}"}
    jane_me = client.get("/auth/me", headers=jane_headers)
    assert jane_me.status_code == 200
    assert jane_me.json()["email"] == test_email


def test_employee_update_field_restrictions():
    admin_token = get_admin_token()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    uid = uuid.uuid4().hex[:6]
    test_email = f"emp.update.{uid}@company.com"

    create_res = client.post("/employees", json={
        "full_name": f"Update Target {uid}",
        "email": test_email,
        "password": "SecretPassword123!",
        "role": "employee"
    }, headers=admin_headers)
    assert create_res.status_code == 201
    emp_id = create_res.json()["id"]

    # Login as this employee
    login_res = client.post("/auth/login", json={
        "email": test_email,
        "password": "SecretPassword123!"
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Employee updates phone and address (allowed)
    update_res = client.put(
        f"/employees/{emp_id}",
        json={"phone": "9998887778", "address": "123 Tech Park"},
        headers=headers
    )
    assert update_res.status_code == 200
    assert update_res.json()["phone"] == "9998887778"
    assert update_res.json()["address"] == "123 Tech Park"

    # 2. Employee tries to promote themselves or change designation (disallowed)
    hacked_res = client.put(
        f"/employees/{emp_id}",
        json={"designation": "Vice President"},
        headers=headers
    )
    assert hacked_res.status_code == 403
    assert "Employees can only update" in hacked_res.json()["detail"]

    # 3. Admin can update administrative fields like designation
    admin_update_res = client.put(
        f"/employees/{emp_id}",
        json={"designation": "Senior Software Engineer"},
        headers=admin_headers
    )
    assert admin_update_res.status_code == 200
    assert admin_update_res.json()["designation"] == "Senior Software Engineer"


def test_query_scoping_by_role():
    admin_token = get_admin_token()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    uid = uuid.uuid4().hex[:6]

    # 1. Create a Manager
    mgr_email = f"manager.{uid}@company.com"
    mgr_payload = {
        "full_name": f"Manager {uid}",
        "email": mgr_email,
        "phone": "9991112222",
        "department_id": 2,
        "designation": "Engineering Manager",
        "date_of_joining": "2026-01-01",
        "office_location_id": 1,
        "password": "Password123!",
        "role": "manager"
    }
    mgr_res = client.post("/employees", json=mgr_payload, headers=admin_headers)
    assert mgr_res.status_code == 201
    mgr_id = mgr_res.json()["id"]

    # 2. Create Direct Report under Manager
    report_email = f"report.{uid}@company.com"
    report_payload = {
        "full_name": f"Report {uid}",
        "email": report_email,
        "manager_id": mgr_id,
        "password": "Password123!",
        "role": "employee"
    }
    report_res = client.post("/employees", json=report_payload, headers=admin_headers)
    assert report_res.status_code == 201
    report_id = report_res.json()["id"]

    # 3. Create another independent employee
    other_email = f"other.{uid}@company.com"
    other_payload = {
        "full_name": f"Other {uid}",
        "email": other_email,
        "password": "Password123!",
        "role": "employee"
    }
    other_res = client.post("/employees", json=other_payload, headers=admin_headers)
    assert other_res.status_code == 201
    other_id = other_res.json()["id"]

    # --- Test Scoping ---
    # A) Admin sees all
    all_emps = client.get("/employees?limit=100", headers=admin_headers).json()
    all_emp_ids = [item["id"] for item in all_emps["items"]]
    assert mgr_id in all_emp_ids
    assert report_id in all_emp_ids
    assert other_id in all_emp_ids

    # B) Manager sees self and direct report
    mark_login = client.post("/auth/login", json={"email": mgr_email, "password": "Password123!"})
    mark_token = mark_login.json()["access_token"]
    mark_headers = {"Authorization": f"Bearer {mark_token}"}

    mgr_view = client.get("/employees", headers=mark_headers).json()
    mgr_emp_ids = [item["id"] for item in mgr_view["items"]]
    assert mgr_id in mgr_emp_ids
    assert report_id in mgr_emp_ids
    assert other_id not in mgr_emp_ids  # Scoped out!

    # C) Other employee sees only self
    other_login = client.post("/auth/login", json={"email": other_email, "password": "Password123!"})
    other_token = other_login.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    other_view = client.get("/employees", headers=other_headers).json()
    assert other_view["total"] == 1
    assert other_view["items"][0]["id"] == other_id
