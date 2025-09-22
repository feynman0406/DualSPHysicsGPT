import argparse
import json
import os
import sys
import time
from pathlib import Path


def read_status(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except Exception:
        return None


def format_status(s: dict) -> str:
    sid = s.get("session_id") or "?"
    it = s.get("iteration")
    phase = s.get("phase") or "?"
    status = s.get("status") or "?"
    stage = s.get("stage") or ""
    msg = s.get("message") or ""
    ts = s.get("updated_at") or ""
    parts = [f"{ts}", f"session={sid}"]
    if it is not None:
        parts.append(f"iter={it}")
    parts.append(f"phase={phase}")
    parts.append(f"status={status}")
    if stage:
        parts.append(f"stage={stage}")
    if msg:
        parts.append(f"msg={msg}")
    return " | ".join(parts)


def main():
    p = argparse.ArgumentParser(description="Watch live status for a session")
    p.add_argument("session_id", help="Session ID (folder name under sessions/)")
    p.add_argument("--sessions-dir", default=os.environ.get("DSPH_SESSIONS_DIR", "sessions"), help="Base sessions directory")
    p.add_argument("--interval", type=float, default=0.5, help="Polling interval seconds")
    args = p.parse_args()

    base = Path(args.sessions_dir).expanduser().resolve()
    target = base / args.session_id / "status.json"
    if not target.exists():
        print(f"Status file not found: {target}")
        print("It will appear once a run starts. Waiting...")

    last_mtime = 0.0
    last_payload = None
    try:
        while True:
            try:
                if target.exists():
                    mtime = target.stat().st_mtime
                    if mtime != last_mtime:
                        payload = read_status(target)
                        if payload and payload != last_payload:
                            print(format_status(payload))
                            last_payload = payload
                        last_mtime = mtime
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

