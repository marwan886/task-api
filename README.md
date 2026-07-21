# Task API

A persistent CRUD API built with Python, FastAPI, PostgreSQL, and Docker Compose. The public API remains unchanged from the in-memory and SQLite versions while PostgreSQL now runs as a separate container.

Repository: <https://github.com/marwan886/task-api>

## Run the complete stack

Docker Desktop or another Docker-compatible engine is required.

```bash
cp .env.example .env
docker compose up --build
```

On Windows PowerShell, use `Copy-Item .env.example .env` for the first command. Change the placeholder password in both values inside `.env` before sharing or deploying the project. The real `.env` file is ignored by Git.

The API is available at <http://localhost:3000>, Swagger UI at <http://localhost:3000/docs>, and PostgreSQL inside the Compose network at `db:5432`. The application creates the `tasks` table and inserts three example tasks only when the table is empty.

Stop the stack with `docker compose down`. The named `taskdata` volume preserves rows across restarts. Use `docker compose down -v` only when you intentionally want a fresh database.

## Configuration

| Variable | Purpose | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string used by the API | `postgresql://postgres:change-me@db:5432/tasks` |
| `POSTGRES_PASSWORD` | Password used by the PostgreSQL container | `change-me` |
| `POSTGRES_DB` | Database created on first startup | `tasks` |

Copy `.env.example` to `.env`; never commit the real file.

## Endpoints

| Method | Path | Purpose | Success |
|---|---|---|---:|
| GET | `/` | Describe the API | 200 |
| GET | `/health` | Check the API and database | 200 |
| GET | `/tasks` | List, filter, search, or paginate tasks | 200 |
| GET | `/tasks/{id}` | Get one task | 200 |
| POST | `/tasks` | Create a task | 201 |
| PUT | `/tasks/{id}` | Update a task | 200 |
| DELETE | `/tasks/{id}` | Delete a task | 204 |
| GET | `/stats` | Count total, completed, and open tasks | 200 |
| POST | `/reset` | Restore the example tasks | 200 |

All client values are passed through parameterized SQL queries. Unknown task IDs return `404`, invalid request bodies return `400`, and errors use `{"error":"message"}`.

## Example request

```console
$ curl -i -X POST http://localhost:3000/tasks -H "Content-Type: application/json" -d '{"title":"Buy milk"}'
HTTP/1.1 201 Created
content-type: application/json

{"id":4,"title":"Buy milk","done":false}
```

## Inspect PostgreSQL

```bash
docker compose exec db psql -U postgres -d tasks -c "\dt"
docker compose exec db psql -U postgres -d tasks -c "SELECT * FROM tasks ORDER BY id;"
```

![The tasks database table](docs/database-screenshot.png)

## Test and verify persistence

Run the unchanged endpoint contract tests:

```bash
pytest -q
```

To prove container persistence, create a task, run `docker compose down`, start again with `docker compose up`, and request `GET /tasks`. The row remains because `taskdata` lives outside the containers.

The same endpoint tests pass across the in-memory, SQLite, and PostgreSQL implementations. This demonstrates that storage is an implementation detail: clients use the same URLs, bodies, responses, and status codes regardless of the database behind the API.

The `/health` endpoint runs `SELECT 1` against the active database. A load balancer can use that result to stop routing traffic to an API instance whose database connection is unavailable.
