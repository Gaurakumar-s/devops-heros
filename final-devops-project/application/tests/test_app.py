import os, tempfile
import pytest

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["ADMIN_TOKEN"] = "test-admin-token"

from app.main import create_app  # noqa: E402


@pytest.fixture()
def client():
    app = create_app()
    app.testing = True
    return app.test_client()


def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.get_json()["app"] == "taskboard"


def test_health_and_ready(client):
    assert client.get("/health").get_json()["status"] == "ok"
    assert client.get("/ready").get_json()["status"] == "ready"


def test_metrics(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"taskboard_requests_total" in r.data


def test_task_crud(client):
    r = client.post("/api/tasks", json={"title": "write final project"})
    assert r.status_code == 201
    task = r.get_json()
    assert task["done"] is False

    r = client.put(f"/api/tasks/{task['id']}", json={"done": True})
    assert r.get_json()["done"] is True

    assert any(t["id"] == task["id"] for t in client.get("/api/tasks").get_json())

    assert client.delete(f"/api/tasks/{task['id']}").status_code == 401
    assert client.delete(f"/api/tasks/{task['id']}", headers={"X-Admin-Token": "test-admin-token"}).status_code == 204
    assert client.get("/api/tasks").get_json() == [] or all(t["id"] != task["id"] for t in client.get("/api/tasks").get_json())


def test_validation(client):
    assert client.post("/api/tasks", json={}).status_code == 400
    assert client.put("/api/tasks/9999", json={"done": True}).status_code == 404
