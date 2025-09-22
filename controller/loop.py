import os, uuid
from typing import Dict, Any

from chains.generator import generator_chain
from chains.fixer import fixer_chain
from tools.exec import run_dualsphysics
from sessions.store import init_session_storage, persist_iteration, update_status

MAX_ITERS = int(os.environ.get("MAX_ITERS", "2"))

# In-memory session store
SESSIONS: Dict[str, Dict[str, Any]] = {}


def _new_session() -> str:
    sid = str(uuid.uuid4())
    SESSIONS[sid] = {
        "state": "START",
        "history": [],
        "last_xml": "",
        "pending_review": False,
        "user_feedback": None,
        "query": "",
    }
    return sid


def _diagnostics_text(result: Dict[str, Any]) -> str:
    text = (result.get("stderr") or "").strip()
    if not text:
        text = result.get("stdout") or ""
    return (text or "")[:4000]


def _read(path: str) -> str:
    return open(path, "r", encoding="utf-8", errors="ignore").read() if os.path.exists(path) else ""


def _run_iterations(session_id: str, initial_prompt: str) -> Dict[str, Any]:
    sess = SESSIONS[session_id]
    prompt = initial_prompt
    iters = sess.get("iters", 0)
    max_iters = sess.get("max_iters", MAX_ITERS)

    while iters < max_iters:
        iters += 1
        sess["iters"] = iters

        update_status(session_id=session_id, phase="generator", status="running", message="Generating XML", iteration=iters)
        gen_result = generator_chain(prompt)
        xml = gen_result["xml"]
        sources = gen_result.get("sources", [])
        sess["last_xml"] = xml

        update_status(
            session_id=session_id, phase="exec", status="running", message="Running DualSPHysics", iteration=iters
        )
        result = run_dualsphysics(xml)
        history_entry = {"xml": xml, "result": result, "prompt": prompt, "rag_sources": sources}
        sess["history"].append(history_entry)

        diagnostics = _diagnostics_text(result)
        history_entry["diagnostics"] = diagnostics

        if result.get("status") == "success":
            persist_iteration(
                session_id=session_id,
                iteration=len(sess["history"]),
                prompt=prompt,
                xml=xml,
                result=result,
                diagnostics_excerpt=diagnostics,
                rag_sources=sources,
            )
            update_status(
                session_id=session_id,
                phase="waiting_review",
                status="waiting",
                message="Awaiting user review",
                iteration=iters,
                stage=result.get("stage"),
                workdir=result.get("workdir"),
            )
            sess["state"] = "pending_user_review"
            sess["pending_review"] = True
            return {"session_id": session_id, "status": "pending_review"}

        update_status(
            session_id=session_id,
            phase="fixer",
            status="running",
            message="Analyzing failure and preparing fixes",
            iteration=iters,
            stage=result.get("stage"),
            workdir=result.get("workdir"),
        )
        fix_plan = fixer_chain(prev_xml=xml, error_msg=diagnostics)
        history_entry["fix_suggestion"] = fix_plan

        persist_iteration(
            session_id=session_id,
            iteration=len(sess["history"]),
            prompt=prompt,
            xml=xml,
            result=result,
            fix_plan=fix_plan,
            diagnostics_excerpt=diagnostics,
            rag_sources=sources,
        )

        base_request = sess["query"]
        prompt = (
            f"(Fix iteration {iters}) Regenerate the DualSPHysics Case_Def.xml with the following guidance.\n"
            f"[Original Request]\n{base_request}\n"
            f"[Previous XML]\n{xml}\n"
            f"[Simulation Diagnostics]\n{diagnostics}\n"
            f"[Fix Suggestions]\n{fix_plan}\n"
        )

    update_status(
        session_id=session_id,
        phase="failed",
        status="fail",
        message="Reached MAX_ITERS without success",
        iteration=iters,
    )
    sess["state"] = "failed_max_iters"
    return {"session_id": session_id, "status": "failed_max_iters"}


def run_pipeline(user_query: str) -> Dict[str, Any]:
    sid = _new_session()
    SESSIONS[sid]["query"] = user_query
    init_session_storage(sid, user_query)
    update_status(session_id=sid, phase="start", status="running", message="Starting pipeline", iteration=0)

    return _run_iterations(session_id=sid, initial_prompt=user_query)


def review(session_id: str, decision: str, feedback: str | None = None):
    sess = SESSIONS.get(session_id)
    if not sess:
        return {"error": "session not found"}

    if sess["state"] not in ("pending_user_review",):
        return {"error": f"session not in reviewable state: {sess['state']}"}

    if decision.lower() == "accept":
        update_status(session_id=session_id, phase="finished", status="finished", message="User accepted result")
        sess["state"] = "finished"
        sess["pending_review"] = False
        return {"session_id": session_id, "status": "finished"}

    if decision.lower() == "reject":
        fb = feedback or ""
        last_xml = sess["last_xml"]
        update_status(
            session_id=session_id,
            phase="fixer",
            status="running",
            message="User rejected — preparing fix plan",
            iteration=sess.get("iters", 0),
        )

        # Use the specialized fixer prompt for user rejections
        fixer_prompt_template = _read("prompts/user_rejection_fixer_prompt.md")
        # NOTE: For this special fixer call, the user's feedback is the "error_msg"
        fix_plan = fixer_chain(prev_xml=last_xml, error_msg=fb, prompt_template=fixer_prompt_template)

        # Use the specialized generator prompt for user rejections
        generator_prompt_template = _read("prompts/user_rejection_generator_prompt.md")
        regen_query = generator_prompt_template.format(
            original_query=sess["query"],
            user_feedback=fb,
            last_xml=last_xml,
            fix_plan=fix_plan,
        )

        sess["pending_review"] = False
        # Reset the iteration counter to give the repair process a fresh start
        sess["iters"] = 0
        # Kick off a new iteration loop with the rejection-based prompt
        return _run_iterations(session_id=session_id, initial_prompt=regen_query)

    return {"error": "decision must be 'accept' or 'reject'"}
