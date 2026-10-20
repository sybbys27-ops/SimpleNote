import os

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="SimpleNote API")


class AppState(BaseModel):
    folders: list[dict]
    notes: list[dict]


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(
            status_code=500,
            detail="DATABASE_URL environment variable is not configured.",
        )
    return database_url


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/sync/load")
def load_state():
    database_url = get_database_url()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT data
                FROM app_state
                WHERE id = 1
                """
            )
            row = cur.fetchone()

    if row is None:
        return {
            "status": "ok",
            "data": {
                "folders": [],
                "notes": [],
            },
        }

    data = row[0] or {}
    return {
        "status": "ok",
        "data": {
            "folders": data.get("folders", []),
            "notes": data.get("notes", []),
        },
    }


@app.post("/sync/save")
def save_state(state: AppState):
    database_url = get_database_url()

    data = {
        "folders": state.folders,
        "notes": state.notes,
    }

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO app_state (id, data, updated_at)
                VALUES (1, %s, NOW())
                ON CONFLICT (id)
                DO UPDATE SET
                    data = EXCLUDED.data,
                    updated_at = NOW()
                """,
                (Jsonb(data),),
            )
        conn.commit()

    return {
        "status": "ok",
        "folder_count": len(state.folders),
        "note_count": len(state.notes),
    }
