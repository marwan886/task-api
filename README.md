# Task API

A beginner-friendly CRUD API for an in-memory to-do list, built with Python and FastAPI. It supports creating, reading, updating, and deleting tasks, with interactive Swagger documentation.

Repository: <https://github.com/marwan886/task-api>

## Install and run

Python 3.10 or newer is required.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

On macOS or Linux, use `source .venv/bin/activate` instead of the Windows activation command.

Open <http://localhost:8000/docs> for Swagger UI. The API stores data only in memory, so changes disappear when the server restarts. That is expected: there is no database in this assignment.

## Endpoints

| Method | Path | Purpose | Success |
|---|---|---|---:|
| GET | `/` | Describe the API | 200 |
| GET | `/health` | Check server health | 200 |
| GET | `/tasks` | List, filter, search, or paginate tasks | 200 |
| GET | `/tasks/{id}` | Get one task | 200 |
| POST | `/tasks` | Create a task | 201 |
| PUT | `/tasks/{id}` | Update a task's title and/or status | 200 |
| DELETE | `/tasks/{id}` | Delete a task | 204 |
| GET | `/stats` | Count total, completed, and open tasks | 200 |
| POST | `/reset` | Restore the three example tasks | 200 |

Optional list parameters include `done=true`, `search=milk`, `limit=2`, and `offset=2`.

## Example

```console
$ curl -i -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d '{"title":"Buy milk"}'
HTTP/1.1 201 Created
content-type: application/json

{"id":4,"title":"Buy milk","done":false}
```

Try a complete create-update-delete cycle in Swagger UI at `/docs`.

## Run the tests

```bash
pytest -q
```

The test suite checks the full CRUD cycle, validation, 400/404 errors, filters, pagination, statistics, reset behavior, and Swagger/OpenAPI availability.
