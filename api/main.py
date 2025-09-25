import os
from fastapi import FastAPI, Body
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment as early as possible so modules that read env at import time
# see the correct values from .env
load_dotenv()

from controller.loop import run_pipeline, review, SESSIONS
from sessions.store import session_dir
from chains.generator import reload_use_rag as reload_generator_rag
from chains.fixer import reload_use_rag as reload_fixer_rag

# Refresh any cached flags that intentionally support runtime reloads
reload_generator_rag()
reload_fixer_rag()


app = FastAPI(title="DualSPHysics Dual-Agent MVP")

class RunReq(BaseModel):
    query: str

class ReviewReq(BaseModel):
    session_id: str
    decision: str  # "accept" / "reject"
    feedback: str | None = None

@app.post("/run")
def run_endpoint(req: RunReq):
    return run_pipeline(req.query)

@app.post("/review")
def review_endpoint(req: ReviewReq):
    return review(req.session_id, req.decision, req.feedback)

@app.get("/session/{session_id}")
def session_info(session_id: str):
    s = SESSIONS.get(session_id)
    return s or {"error":"not found"}

@app.get("/status/{session_id}")
def status_json(session_id: str):
    import json
    p = session_dir(session_id) / "status.json"
    if not p.exists():
        return {"error": "status not found", "session_id": session_id}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": str(e), "session_id": session_id}


