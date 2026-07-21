from fastapi.testclient import TestClient

from main import DATABASE_PATH, app, init_database


client = TestClient(app)


def setup_function() -> None:
    client.post("/reset")


def test_root_and_health() -> None:
    assert client.get("/").json() == {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"],
    }
    assert client.get("/health").json() == {"status": "ok", "database": "ok"}


def test_read_tasks_and_missing_task() -> None:
    assert len(client.get("/tasks").json()) == 3
    assert client.get("/tasks/1").status_code == 200
    response = client.get("/tasks/99")
    assert response.status_code == 404
    assert response.json() == {"error": "Task not found"}


def test_full_crud_cycle() -> None:
    created = client.post("/tasks", json={"title": "Buy milk"})
    assert created.status_code == 201
    task = created.json()
    assert task == {"id": 4, "title": "Buy milk", "done": False}

    updated = client.put(
        f"/tasks/{task['id']}", json={"title": "Buy oat milk", "done": True}
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Buy oat milk"
    assert updated.json()["done"] is True

    deleted = client.delete(f"/tasks/{task['id']}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(f"/tasks/{task['id']}").status_code == 404


def test_validation_errors_use_400_and_json_error() -> None:
    for body in ({}, {"title": "   "}):
        response = client.post("/tasks", json=body)
        assert response.status_code == 400
        assert "error" in response.json()

    for body in ({}, {"title": ""}, {"done": "not-a-boolean"}):
        response = client.put("/tasks/1", json=body)
        assert response.status_code == 400
        assert "error" in response.json()


def test_filters_pagination_stats_and_reset() -> None:
    assert len(client.get("/tasks", params={"done": "true"}).json()) == 1
    assert len(client.get("/tasks", params={"search": "swagger"}).json()) == 1
    assert len(client.get("/tasks", params={"limit": 1, "offset": 1}).json()) == 1
    assert client.get("/stats").json() == {"total": 3, "done": 1, "open": 2}
    client.delete("/tasks/1")
    assert len(client.post("/reset").json()) == 3


def test_swagger_and_openapi_are_available() -> None:
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert all(
        path in schema["paths"]
        for path in ["/tasks", "/tasks/{task_id}", "/health", "/stats", "/reset"]
    )


def test_database_persistence_and_idempotent_seed() -> None:
    created = client.post("/tasks", json={"title": "Survive restart"}).json()
    init_database()
    assert DATABASE_PATH.exists()
    assert client.get(f"/tasks/{created['id']}").json() == created
    assert len(client.get("/tasks").json()) == 4
