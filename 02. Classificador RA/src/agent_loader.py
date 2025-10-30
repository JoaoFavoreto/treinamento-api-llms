"""Utility helpers to load agent prompts and parameters from YAML files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import yaml


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_AGENTS_DIR = _PROJECT_ROOT / "agents"


def _to_readable_path(path: Path) -> str:
    try:
        return str(path.relative_to(_PROJECT_ROOT))
    except ValueError:
        return str(path)


def load_agent_config(agent_name: str) -> Dict[str, Any]:
    """Load a YAML agent definition.

    Parameters
    ----------
    agent_name: str
        Name of the agent file without extension.

    Returns
    -------
    dict
        Parsed YAML content.
    """
    agent_path = _AGENTS_DIR / f"{agent_name}.yaml"
    if not agent_path.exists():
        raise FileNotFoundError(
            f"Agent definition not found: {_to_readable_path(agent_path)}"
        )

    with agent_path.open("r", encoding="utf-8") as handler:
        data = yaml.safe_load(handler)

    if not isinstance(data, dict):
        raise ValueError(
            f"Agent definition must be a YAML object: {_to_readable_path(agent_path)}"
        )

    return data


def format_message(template: str, **kwargs: Any) -> str:
    """Format a template string using ``str.format``.

    Agent templates should escape literal braces (``{{`` and ``}}``) when
    necessary so the formatting succeeds.
    """
    return template.format(**kwargs)


def dump_agent_example(agent_config: Dict[str, Any]) -> str:
    """Return a compact JSON preview of an agent configuration (debug helper)."""
    return json.dumps(agent_config, indent=2, ensure_ascii=False)
