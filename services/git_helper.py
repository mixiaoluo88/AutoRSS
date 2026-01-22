from __future__ import annotations
import os
import subprocess
from typing import List, Optional

from services.config import get_config


def _run(cmd: List[str], cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def ensure_repo(cwd: Optional[str] = None) -> None:
    cwd = cwd or os.getcwd()
    if not os.path.isdir(os.path.join(cwd, ".git")):
        _run(["git", "init"], cwd=cwd)
    cfg = get_config()
    if cfg.get("GIT_USER_NAME"):
        _run(["git", "config", "user.name", cfg["GIT_USER_NAME"]], cwd=cwd)
    if cfg.get("GIT_USER_EMAIL"):
        _run(["git", "config", "user.email", cfg["GIT_USER_EMAIL"]], cwd=cwd)


def commit(paths: List[str], message: str, tag: Optional[str] = None, cwd: Optional[str] = None) -> str:
    """Add+commit+optional tag. Returns short log or error."""
    cwd = cwd or os.getcwd()
    ensure_repo(cwd)
    add = _run(["git", "add", "--" ] + paths, cwd=cwd)
    if add.returncode != 0:
        return f"git add error: {add.stderr.strip()}"
    commit_res = _run(["git", "commit", "-m", message], cwd=cwd)
    if commit_res.returncode != 0:
        if "nothing to commit" in commit_res.stderr.lower() or "nothing to commit" in commit_res.stdout.lower():
            summary = "nothing to commit"
        else:
            summary = f"git commit error: {commit_res.stderr.strip()}"
    else:
        summary = commit_res.stdout.strip()
    if tag:
        tag_res = _run(["git", "tag", "-a", tag, "-m", message], cwd=cwd)
        if tag_res.returncode != 0:
            summary += f"; tag error: {tag_res.stderr.strip()}"
    return summary
