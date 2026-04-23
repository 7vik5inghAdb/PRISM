"""Run directory + JSON artifact helpers.

Every PRISM-v0 run lives in `runs/<run_id>/` with one JSON file per step,
so the PM can review, hand-edit, and re-enter the pipeline at any checkpoint.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from prism.schemas import RunConfig


REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = REPO_ROOT / "runs"


def load_config(path: str | Path) -> RunConfig:
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return RunConfig.model_validate(data)


def run_dir(run_id: str) -> Path:
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_artifact(run_id: str, name: str, obj: BaseModel | dict | list) -> Path:
    path = run_dir(run_id) / f"{name}.json"
    if isinstance(obj, BaseModel):
        payload: Any = obj.model_dump(mode="json")
    else:
        payload = obj
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def load_artifact(run_id: str, name: str, model: type[BaseModel] | None = None):
    path = run_dir(run_id) / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing artifact {path}. Run the earlier step first."
        )
    with open(path, "r") as f:
        data = json.load(f)
    if model is None:
        return data
    return model.model_validate(data)


def resolve_asset_path(relative: str) -> Path:
    p = REPO_ROOT / relative
    if not p.exists():
        raise FileNotFoundError(f"Asset not found: {p}")
    return p
