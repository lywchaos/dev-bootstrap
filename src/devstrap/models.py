from __future__ import annotations

import importlib.resources
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ToolConfig:
    name: str
    description: str
    check: str
    install: dict[str, str]

    @classmethod
    def from_dict(cls, data: dict) -> ToolConfig:
        if "name" not in data:
            raise ValueError("Tool entry missing required field: 'name'")
        if "install" not in data:
            raise ValueError(
                f"Tool '{data.get('name', '?')}' missing required field: 'install'"
            )
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            check=data.get("check", ""),
            install=data["install"],
        )


def load_manifest(path: Path | None = None) -> list[ToolConfig]:
    if path is None:
        ref = importlib.resources.files("devstrap").joinpath("tools.yaml")
        text = ref.read_text(encoding="utf-8")
    else:
        text = Path(path).read_text(encoding="utf-8")

    data = yaml.safe_load(text)
    if not isinstance(data, dict) or "tools" not in data:
        raise ValueError("Manifest must contain a 'tools' key")
    return [ToolConfig.from_dict(entry) for entry in data["tools"]]
