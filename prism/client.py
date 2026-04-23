"""Anthropic client factory with sane PRISM-v0 defaults."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from anthropic import Anthropic


def _load_env_file(env_path: Path) -> None:
    """Simple .env parser — robust to missing trailing newlines."""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Override empty env vars too (shells may pre-set them to "")
        if key and not os.environ.get(key):
            os.environ[key] = value


@lru_cache(maxsize=1)
def get_client() -> Anthropic:
    repo_root = Path(__file__).resolve().parent.parent
    _load_env_file(repo_root / ".env")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            f"ANTHROPIC_API_KEY is not set. Create {repo_root / '.env'} "
            f"with `ANTHROPIC_API_KEY=sk-ant-...`."
        )
    return Anthropic(api_key=api_key)
