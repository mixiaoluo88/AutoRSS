from __future__ import annotations
import os
from typing import Any, Dict

try:
    import streamlit as st 
except Exception:
    st = None


try:
    from streamlit.runtime.secrets import StreamlitSecretNotFoundError 
except Exception: 
    class StreamlitSecretNotFoundError(Exception): 
        pass


def _from_secrets() -> Dict[str, Any]:
    if st is None:
        return {}
    try:
        sec = st.secrets
        freshrss = sec.get("freshrss", {}) or {}
        llm = sec.get("llm", {}) or {}
        git = sec.get("git", {}) or {}

        cfg: Dict[str, Any] = {
            "FRESHRSS_HOST": freshrss.get("host"),
            "FRESHRSS_USER": freshrss.get("username"),
            "FRESHRSS_PASS": freshrss.get("password"),
            "LLM_BASE_URL": llm.get("base_url"),
            "LLM_MODEL": llm.get("model"),
            "LLM_API_KEY": llm.get("api_key"),
            "GIT_AUTO_COMMIT": bool(git.get("auto_commit", True)),
            "GIT_AUTO_TAG": bool(git.get("auto_tag", False)),
            "GIT_USER_NAME": git.get("user_name"),
            "GIT_USER_EMAIL": git.get("user_email"),
            "FETCH_DAYS": int(sec.get("fetch_days", 7)),
            "FETCH_MAX_COUNT": int(sec.get("fetch_max_count", 100)),
            "DEDUP_THRESHOLD": float(sec.get("dedup_threshold", 0.65)),
            "CONCURRENCY": int(sec.get("concurrency", 1)),
        }
        return cfg
    except StreamlitSecretNotFoundError:
        return {}
    except Exception:
        return {}


def _from_env() -> Dict[str, Any]:
    return {
        "FRESHRSS_HOST": os.getenv("FRESHRSS_HOST"),
        "FRESHRSS_USER": os.getenv("FRESHRSS_USER"),
        "FRESHRSS_PASS": os.getenv("FRESHRSS_PASS"),
        "LLM_BASE_URL": os.getenv("LLM_BASE_URL"),
        "LLM_MODEL": os.getenv("LLM_MODEL"),
        "LLM_API_KEY": os.getenv("LLM_API_KEY"),
        "GIT_AUTO_COMMIT": os.getenv("GIT_AUTO_COMMIT", "true").lower() == "true",
        "GIT_AUTO_TAG": os.getenv("GIT_AUTO_TAG", "false").lower() == "true",
        "GIT_USER_NAME": os.getenv("GIT_USER_NAME"),
        "GIT_USER_EMAIL": os.getenv("GIT_USER_EMAIL"),
        "FETCH_DAYS": int(os.getenv("FETCH_DAYS", "7")),
        "FETCH_MAX_COUNT": int(os.getenv("FETCH_MAX_COUNT", "100")),
        "DEDUP_THRESHOLD": float(os.getenv("DEDUP_THRESHOLD", "0.65")),
        "CONCURRENCY": int(os.getenv("CONCURRENCY", "1")),
    }


def get_config() -> Dict[str, Any]:
    """聚合 st.secrets 与环境变量，secrets 优先。"""
    cfg = {**_from_env(), **_from_secrets()}
    return cfg


def is_config_ready(cfg: Dict[str, Any]) -> bool:
    keys = [
        "FRESHRSS_HOST", "FRESHRSS_USER", "FRESHRSS_PASS",
        "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY",
    ]
    return all(bool(cfg.get(k)) for k in keys)
