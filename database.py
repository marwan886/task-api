import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass


SEED_TASKS = [
    ("Learn HTTP basics", True),
    ("Build a CRUD API", False),
    ("Test with Swagger UI", False),
]

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///tasks.db")
DATABASE_PATH = Path(DATABASE_URL.removeprefix("sqlite:///"))
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))


@contextmanager
def get_connection() -> Iterator[object]:
    if IS_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
            yield connection
    else:
        connection = sqlite3.connect(DATABASE_PATH)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()


def placeholder() -> str:
    return "%s" if IS_POSTGRES else "?"


def init_database() -> None:
    identity = "SERIAL PRIMARY KEY" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with get_connection() as connection:
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS tasks (id {identity}, title TEXT NOT NULL, done BOOLEAN NOT NULL DEFAULT FALSE)"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks (done)")
        count = connection.execute("SELECT COUNT(*) AS total FROM tasks").fetchone()
        total = count["total"] if IS_POSTGRES else count[0]
        if total == 0:
            marker = placeholder()
            for task in SEED_TASKS:
                connection.execute(
                    f"INSERT INTO tasks (title, done) VALUES ({marker}, {marker})",
                    task,
                )
