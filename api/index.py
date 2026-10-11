from copy import deepcopy

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="SimpleNote API")


class AppState(BaseModel):
    folders: list[dict]
    notes: list[dict]


# Neon 연결 전 임시 저장소.
# 서버가 재시작되면 초기화되며, 다음 단계에서 Neon JSONB 저장으로 교체합니다.
_memory_state = {
    "folders": [],
    "notes": [],
}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/sync/load")
def load_state():
    return {
        "status": "ok",
        "data": deepcopy(_memory_state),
    }


@app.post("/sync/save")
def save_state(state: AppState):
    global _memory_state

    _memory_state = {
        "folders": deepcopy(state.folders),
        "notes": deepcopy(state.notes),
    }

    return {
        "status": "ok",
        "folder_count": len(_memory_state["folders"]),
        "note_count": len(_memory_state["notes"]),
    }
