from pathlib import Path
import sqlite3

from fastapi import FastAPI

app = FastAPI(title="SimpleNote API")

# 개발 단계: 기존 SimpleNote 스크립트와 동일한 위치의 SQLite 파일 사용
DB_PATH = Path(__file__).resolve().parent.parent / "notes2.0.db"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/notes")
def list_notes():
    if not DB_PATH.is_file():
        return {"status": "db_not_found", "notes": []}

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, folder_id, title, body, highlights FROM notes ORDER BY rowid"
        ).fetchall()

    return {"status": "ok", "notes": [dict(row) for row in rows]}
