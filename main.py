from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from auth import get_current_user, get_supabase
from database import DATABASE_PATH, IS_POSTGRES, SEED_TASKS, get_connection, init_database, placeholder


app = FastAPI(
    title="Task API",
    version="1.0",
    description="A PostgreSQL-backed CRUD API for managing a to-do list.",
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


class AuthCredentials(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str
    password: str

    @field_validator("email", "password")
    @classmethod
    def credentials_must_not_be_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("email and password are required")
        return value


init_database()


def row_to_task(row: object) -> Task:
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
    marker = placeholder()
    with get_connection() as connection:
        row = connection.execute(
            f"SELECT id, title, done FROM tasks WHERE id = {marker}", (task_id,)
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
    with get_connection() as connection:
        connection.execute("SELECT 1").fetchone()
    return {"status": "ok", "database": "ok"}


@app.post("/auth/signup", status_code=status.HTTP_201_CREATED, summary="Create an account")
def signup(payload: AuthCredentials) -> dict[str, object]:
    try:
        response = get_supabase().auth.sign_up(
            {"email": payload.email, "password": payload.password}
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    user = response.user
    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "created_at": str(user.created_at),
        }
    }


@app.post("/auth/login", summary="Log in and receive tokens")
def login(payload: AuthCredentials) -> dict[str, str]:
    try:
        response = get_supabase().auth.sign_in_with_password(
            {"email": payload.email, "password": payload.password}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login credentials",
        ) from exc
    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "token_type": "bearer",
    }


@app.get("/public/info", summary="Read public information")
def public_info() -> dict[str, str]:
    return {"message": "Welcome stranger! This info is public."}


@app.get("/protected/profile", summary="Read the current user profile")
def protected_profile(user: object = Depends(get_current_user)) -> dict[str, str]:
    return {
        "id": str(user.id),
        "email": user.email,
        "created_at": str(user.created_at),
    }


@app.get("/protected/dashboard", summary="Read the private dashboard")
def protected_dashboard(user: object = Depends(get_current_user)) -> dict[str, str]:
    return {"message": f"Welcome {user.email}"}


@app.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out",
)
def logout(_user: object = Depends(get_current_user)) -> Response:
    try:
        get_supabase().auth.sign_out()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/tasks", response_model=list[Task], summary="List tasks")
def list_tasks(
    done: bool | None = Query(default=None, description="Filter by completion status"),
    search: str | None = Query(default=None, description="Search task titles"),
    limit: Annotated[int, Query(ge=1)] | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Task]:
    marker = placeholder()
    clauses: list[str] = []
    parameters: list[object] = []
    if done is not None:
        clauses.append(f"done = {marker}")
        parameters.append(done)
    if search:
        clauses.append(f"title LIKE {marker}")
        parameters.append(f"%{search}%")
    query = "SELECT id, title, done FROM tasks"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY id"
    if limit is not None:
        query += f" LIMIT {marker} OFFSET {marker}"
        parameters.extend([limit, offset])
    elif offset:
        query += (f" OFFSET {marker}" if IS_POSTGRES else f" LIMIT -1 OFFSET {marker}")
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
    marker = placeholder()
    with get_connection() as connection:
        if IS_POSTGRES:
            row = connection.execute(
                f"INSERT INTO tasks (title, done) VALUES ({marker}, {marker}) RETURNING id, title, done",
                (payload.title, False),
            ).fetchone()
        else:
            cursor = connection.execute(
                f"INSERT INTO tasks (title, done) VALUES ({marker}, {marker})",
                (payload.title, False),
            )
            row = connection.execute(
                f"SELECT id, title, done FROM tasks WHERE id = {marker}",
                (cursor.lastrowid,),
            ).fetchone()
    return row_to_task(row)


@app.put("/tasks/{task_id}", response_model=Task, summary="Update a task")
def update_task(task_id: int, payload: TaskUpdate) -> Task:
    task = find_task(task_id)
    title = payload.title if payload.title is not None else task.title
    done = payload.done if payload.done is not None else task.done
    marker = placeholder()
    with get_connection() as connection:
        connection.execute(
            f"UPDATE tasks SET title = {marker}, done = {marker} WHERE id = {marker}",
            (title, done, task_id),
        )
    return find_task(task_id)


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
def delete_task(task_id: int) -> Response:
    find_task(task_id)
    marker = placeholder()
    with get_connection() as connection:
        connection.execute(f"DELETE FROM tasks WHERE id = {marker}", (task_id,))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/stats", response_model=Stats, summary="Get task statistics")
def get_stats() -> Stats:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN done THEN 1 ELSE 0 END) AS done
            FROM tasks
            """
        ).fetchone()
    completed = row["done"] or 0
    return Stats(total=row["total"], done=completed, open=row["total"] - completed)


@app.post("/reset", response_model=list[Task], summary="Restore example tasks")
def reset_tasks() -> list[Task]:
    with get_connection() as connection:
        if IS_POSTGRES:
            connection.execute("TRUNCATE tasks RESTART IDENTITY")
        else:
            connection.execute("DELETE FROM tasks")
            connection.execute("DELETE FROM sqlite_sequence WHERE name = ?", ("tasks",))
        marker = placeholder()
        for task in SEED_TASKS:
            connection.execute(
                f"INSERT INTO tasks (title, done) VALUES ({marker}, {marker})",
                task,
            )
        rows = connection.execute(
            "SELECT id, title, done FROM tasks ORDER BY id"
        ).fetchall()
    return [row_to_task(row) for row in rows]
