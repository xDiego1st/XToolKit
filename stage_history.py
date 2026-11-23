"""Private local stage history, independent of checkout authorization."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


def history_path(repo: Path, account: str) -> Path:
    digest = hashlib.sha256(account.strip().lower().encode("utf-8")).hexdigest()
    return repo / "logs" / "stage-history" / (digest + ".json")


def read_history(repo: Path, account: str) -> list:
    try:
        data = json.loads(history_path(repo, account).read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def latest_history(repo: Path) -> list:
    try:
        paths = sorted((repo / "logs" / "stage-history").glob("*.json"),
                       key=lambda path: path.stat().st_mtime_ns, reverse=True)
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
    except (OSError, ValueError):
        pass
    return []


def record_history(repo: Path, account: str, step: int, status: str) -> None:
    path = history_path(repo, account)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = read_history(repo, account)[-99:]
    entries.append({"step": step, "status": status, "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as output:
            temporary = output.name
            json.dump(entries, output)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
