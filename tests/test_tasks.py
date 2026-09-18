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


def create_test_employee(role: str = "employee") -> dict:
    admin_token = get_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}"}
    uid = uuid.uuid4().hex[:6]
    email = f"task.user.{uid}@company.com"
    pwd = "Password123!"

    payload = {
        "full_name": f"Task User {uid}",
        "email": email,
        "password": pwd,
        "role": role
    }
    create_res = client.post("/employees", json=payload, headers=headers)
    assert create_res.status_code == 201
    emp_data = create_res.json()

    login_res = client.post("/auth/login", json={"email": email, "password": pwd})
    token = login_res.json()["access_token"]

    return {
        "employee_id": emp_data["id"],
        "email": email,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"}
    }


def test_project_crud_and_members():
    admin_token = get_admin_token()
    headers = {"Authorization": f"Bearer {admin_token}"}
    uid = uuid.uuid4().hex[:6]

    # 1. Create project
    proj_in = {
        "name": f"HRMS Rollout {uid}",
        "description": "Internal HR system rollout",
        "start_date": "2026-09-01",
        "end_date": "2026-12-31",
        "status": "active"
    }
    proj_res = client.post("/projects", json=proj_in, headers=headers)
    assert proj_res.status_code == 201
    proj_data = proj_res.json()
    assert proj_data["name"] == f"HRMS Rollout {uid}"
    proj_id = proj_data["id"]

    # 2. Add member to project
    user = create_test_employee()
    member_in = {
        "employee_id": user["employee_id"],
        "role_in_project": "contributor"
    }
    member_res = client.post(f"/projects/{proj_id}/members", json=member_in, headers=headers)
    assert member_res.status_code == 201
    assert member_res.json()["employee_id"] == user["employee_id"]
    assert member_res.json()["role_in_project"] == "contributor"

    # 3. Get project details
    detail_res = client.get(f"/projects/{proj_id}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["members"]) >= 1


def test_task_flow_and_logging():
    admin_token = get_admin_token()
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    uid = uuid.uuid4().hex[:6]

    # Create project
    proj_res = client.post("/projects", json={
        "name": f"Mobile App {uid}",
        "description": "Employee mobile app"
    }, headers=admin_headers)
    proj_id = proj_res.json()["id"]

    # Create assignee employee
    user = create_test_employee()

    # 1. Admin/Manager creates task
    task_in = {
        "project_id": proj_id,
        "assigned_to": user["employee_id"],
        "title": f"Design leave approval screen {uid}",
        "description": "Figma mockups and design system tokens",
        "priority": "high",
        "due_date": "2026-09-25",
        "status": "pending"
    }
    task_res = client.post("/tasks", json=task_in, headers=admin_headers)
    assert task_res.status_code == 201
    task_data = task_res.json()
    assert task_data["status"] == "pending"
    task_id = task_data["id"]

    # 2. Employee checks /tasks/me
    my_tasks_res = client.get("/tasks/me", headers=user["headers"])
    assert my_tasks_res.status_code == 200
    my_tasks = my_tasks_res.json()["items"]
    assert len(my_tasks) >= 1
    target = next(t for t in my_tasks if t["id"] == task_id)
    assert target["title"] == f"Design leave approval screen {uid}"
    assert target["project"] == f"Mobile App {uid}"
    assert target["priority"] == "high"

    # 3. Employee updates status to in_progress
    update_res = client.put(f"/tasks/{task_id}", json={"status": "in_progress"}, headers=user["headers"])
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "in_progress"

    # 4. Employee logs hours worked
    log_in = {
        "log_date": "2026-09-17",
        "hours_spent": 3.5,
        "notes": "Completed wireframe and review"
    }
    log_res = client.post(f"/tasks/{task_id}/log", json=log_in, headers=user["headers"])
    assert log_res.status_code == 201
    log_data = log_res.json()
    assert log_data["task_id"] == task_id
    assert log_data["hours_spent"] == 3.5
    assert "id" in log_data

    # 5. Get task logs
    logs_res = client.get(f"/tasks/{task_id}/logs", headers=user["headers"])
    assert logs_res.status_code == 200
    logs = logs_res.json()
    assert len(logs) >= 1
    assert logs[0]["hours_spent"] == 3.5
    assert logs[0]["notes"] == "Completed wireframe and review"
