import os
import sqlite3
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator, model_validator


app = FastAPI(
    title="Task API",
    version="1.0",
    description="A small in-memory CRUD API for managing a to-do list.",
)


class Task(BaseModel):
    id: int
    title: str
    done: bool


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("title must not be empty")
        return value


class TaskUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = None
    done: bool | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("title must not be empty")
        return value

    @model_validator(mode="after")
    def body_must_contain_a_change(self) -> "TaskUpdate":
        if self.title is None and self.done is None:
            raise ValueError("provide title and/or done")
        return self


class Stats(BaseModel):
    total: int
    done: int
    open: int


SEED_TASKS = [
    Task(id=1, title="Learn HTTP basics", done=True),
    Task(id=2, title="Build a CRUD API", done=False),
    Task(id=3, title="Test with Swagger UI", done=False),
]

DATABASE_PATH = Path(os.getenv("TASK_DB_PATH", "tasks.db"))


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1))
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks (done)"
        )
        count = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count == 0:
            connection.executemany(
                "INSERT INTO tasks (title, done) VALUES (?, ?)",
                [(task.title, int(task.done)) for task in SEED_TASKS],
            )


init_database()


def row_to_task(row: sqlite3.Row) -> Task:
    return Task(id=row["id"], title=row["title"], done=bool(row["done"]))


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    messages = [error["msg"].removeprefix("Value error, ") for error in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "; ".join(messages)},
    )


def find_task(task_id: int) -> Task:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return row_to_task(row)


@app.get("/", summary="Describe the API")
def read_root() -> dict[str, str | list[str]]:
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health", summary="Check server health")
def read_health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tasks", response_model=list[Task], summary="List tasks")
def list_tasks(
    done: bool | None = Query(default=None, description="Filter by completion status"),
    search: str | None = Query(default=None, description="Search task titles"),
    limit: Annotated[int, Query(ge=1)] | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Task]:
    clauses: list[str] = []
    parameters: list[object] = []
    if done is not None:
        clauses.append("done = ?")
        parameters.append(int(done))
    if search:
        clauses.append("title LIKE ?")
        parameters.append(f"%{search}%")
    query = "SELECT id, title, done FROM tasks"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY id"
    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        parameters.extend([limit, offset])
    elif offset:
        query += " LIMIT -1 OFFSET ?"
        parameters.append(offset)
    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [row_to_task(row) for row in rows]


@app.get("/tasks/{task_id}", response_model=Task, summary="Get one task")
def get_task(task_id: int) -> Task:
    return find_task(task_id)


@app.post(
    "/tasks",
    response_model=Task,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
)
def create_task(payload: TaskCreate) -> Task:
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            (payload.title, 0),
        )
        row = connection.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return row_to_task(row)


@app.put("/tasks/{task_id}", response_model=Task, summary="Update a task")
def update_task(task_id: int, payload: TaskUpdate) -> Task:
    task = find_task(task_id)
    title = payload.title if payload.title is not None else task.title
    done = payload.done if payload.done is not None else task.done
    with get_connection() as connection:
        connection.execute(
            "UPDATE tasks SET title = ?, done = ? WHERE id = ?",
            (title, int(done), task_id),
        )
    return find_task(task_id)


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
def delete_task(task_id: int) -> Response:
    find_task(task_id)
    with get_connection() as connection:
        connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/stats", response_model=Stats, summary="Get task statistics")
def get_stats() -> Stats:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS done
            FROM tasks
            """
        ).fetchone()
    completed = row["done"] or 0
    return Stats(total=row["total"], done=completed, open=row["total"] - completed)


@app.post("/reset", response_model=list[Task], summary="Restore example tasks")
def reset_tasks() -> list[Task]:
    with get_connection() as connection:
        connection.execute("DELETE FROM tasks")
        connection.execute("DELETE FROM sqlite_sequence WHERE name = ?", ("tasks",))
        connection.executemany(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            [(task.title, int(task.done)) for task in SEED_TASKS],
        )
        rows = connection.execute(
            "SELECT id, title, done FROM tasks ORDER BY id"
        ).fetchall()
    return [row_to_task(row) for row in rows]
