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

tasks: list[Task] = [task.model_copy() for task in SEED_TASKS]


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
    task = next((item for item in tasks if item.id == task_id), None)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return task


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
    result = tasks
    if done is not None:
        result = [task for task in result if task.done is done]
    if search:
        query = search.casefold()
        result = [task for task in result if query in task.title.casefold()]
    return result[offset:] if limit is None else result[offset : offset + limit]


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
    next_id = max((task.id for task in tasks), default=0) + 1
    task = Task(id=next_id, title=payload.title, done=False)
    tasks.append(task)
    return task


@app.put("/tasks/{task_id}", response_model=Task, summary="Update a task")
def update_task(task_id: int, payload: TaskUpdate) -> Task:
    task = find_task(task_id)
    if payload.title is not None:
        task.title = payload.title
    if payload.done is not None:
        task.done = payload.done
    return task


@app.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
def delete_task(task_id: int) -> Response:
    task = find_task(task_id)
    tasks.remove(task)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/stats", response_model=Stats, summary="Get task statistics")
def get_stats() -> Stats:
    completed = sum(task.done for task in tasks)
    return Stats(total=len(tasks), done=completed, open=len(tasks) - completed)


@app.post("/reset", response_model=list[Task], summary="Restore example tasks")
def reset_tasks() -> list[Task]:
    tasks.clear()
    tasks.extend(task.model_copy() for task in SEED_TASKS)
    return tasks
