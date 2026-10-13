"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from contextlib import asynccontextmanager, closing, contextmanager
import json
import os
from pathlib import Path
import sqlite3
from typing import Generator

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

CURRENT_DIR = Path(__file__).parent
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", CURRENT_DIR / "activities.db"))
SEED_FILE = CURRENT_DIR / "activities.json"


@contextmanager
def database_connection() -> Generator[sqlite3.Connection, None, None]:
    with closing(sqlite3.connect(DATABASE_PATH, timeout=10)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with database_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS activities (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL CHECK (max_participants > 0)
            );
            CREATE TABLE IF NOT EXISTS signups (
                id INTEGER PRIMARY KEY,
                activity_name TEXT NOT NULL REFERENCES activities(name)
                    ON DELETE CASCADE,
                email TEXT NOT NULL,
                approval_status TEXT NOT NULL DEFAULT 'approved',
                UNIQUE (activity_name, email)
            );
            """
        )

        has_activities = connection.execute(
            "SELECT 1 FROM activities LIMIT 1"
        ).fetchone()
        if has_activities is None:
            sample_activities = json.loads(SEED_FILE.read_text(encoding="utf-8"))
            for name, activity in sample_activities.items():
                connection.execute(
                    """
                    INSERT INTO activities
                        (name, description, schedule, max_participants)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        name,
                        activity["description"],
                        activity["schedule"],
                        activity["max_participants"],
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO signups (activity_name, email, approval_status)
                    VALUES (?, ?, 'approved')
                    """,
                    ((name, email) for email in activity["participants"]),
                )


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Mergington High School API",
    description="API for viewing and signing up for extracurricular activities",
    lifespan=lifespan,
)

app.mount(
    "/static",
    StaticFiles(directory=CURRENT_DIR / "static"),
    name="static",
)


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    with database_connection() as connection:
        activity_rows = connection.execute(
            """
            SELECT name, description, schedule, max_participants
            FROM activities
            ORDER BY rowid
            """
        ).fetchall()
        activities = {}
        for activity in activity_rows:
            participants = connection.execute(
                """
                SELECT email FROM signups
                WHERE activity_name = ?
                ORDER BY id
                """,
                (activity["name"],),
            ).fetchall()
            activities[activity["name"]] = {
                "description": activity["description"],
                "schedule": activity["schedule"],
                "max_participants": activity["max_participants"],
                "participants": [participant["email"] for participant in participants],
            }
        return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity."""
    with database_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        activity = connection.execute(
            """
            SELECT max_participants FROM activities
            WHERE name = ?
            """,
            (activity_name,),
        ).fetchone()
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        already_signed_up = connection.execute(
            """
            SELECT 1 FROM signups
            WHERE activity_name = ? AND email = ?
            """,
            (activity_name, email),
        ).fetchone()
        if already_signed_up is not None:
            raise HTTPException(
                status_code=400,
                detail="Student is already signed up",
            )

        signup_count = connection.execute(
            """
            SELECT COUNT(*) FROM signups
            WHERE activity_name = ? AND approval_status != 'rejected'
            """,
            (activity_name,),
        ).fetchone()[0]
        if signup_count >= activity["max_participants"]:
            raise HTTPException(status_code=400, detail="Activity is full")

        connection.execute(
            """
            INSERT INTO signups (activity_name, email, approval_status)
            VALUES (?, ?, 'approved')
            """,
            (activity_name, email),
        )
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity."""
    with database_connection() as connection:
        activity = connection.execute(
            "SELECT 1 FROM activities WHERE name = ?",
            (activity_name,),
        ).fetchone()
        if activity is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        signup = connection.execute(
            """
            SELECT 1 FROM signups
            WHERE activity_name = ? AND email = ?
            """,
            (activity_name, email),
        ).fetchone()
        if signup is None:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity",
            )

        connection.execute(
            """
            DELETE FROM signups
            WHERE activity_name = ? AND email = ?
            """,
            (activity_name, email),
        )
    return {"message": f"Unregistered {email} from {activity_name}"}
