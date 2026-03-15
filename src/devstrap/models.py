from __future__ import annotations

import importlib.resources
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ScriptEntry:
    """A single script specification — either inline or file reference."""

    script: str | None = None
    script_file: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> ScriptEntry:
        has_script = "script" in data
        has_script_file = "script_file" in data
        if has_script and has_script_file:
            raise ValueError("'script' and 'script_file' are mutually exclusive")
        if not has_script and not has_script_file:
            raise ValueError("Entry must have 'script' or 'script_file'")
        return cls(script=data.get("script"), script_file=data.get("script_file"))


# Known package manager keys — everything else is a script-related key
# Note: snap is excluded because its value is a full command, not a package name
# TODO: Add proper snap support with a different install command format
_PKG_MANAGER_KEYS = {"brew", "apt"}
_SCRIPT_KEYS = {"script", "script_file", "alternatives"}


def _check_exclusive(data: dict, keys: tuple[str, ...]) -> None:
    """Raise ValueError if more than one of *keys* appears in *data*."""
    present = [k for k in keys if k in data]
    if len(present) > 1:
        raise ValueError(
            f"Install keys {present} are mutually exclusive — use only one"
        )


@dataclass
class InstallSpec:
    """Parsed install specification for a tool."""

    package_managers: dict[str, str]
    script: str | None = None
    script_file: str | None = None
    alternatives: list[ScriptEntry] | None = None

    @classmethod
    def from_dict(cls, data: dict) -> InstallSpec:
        _check_exclusive(data, ("script", "script_file", "alternatives"))
        pkg_managers = {k: v for k, v in data.items() if k in _PKG_MANAGER_KEYS}
        alternatives_raw = data.get("alternatives")
        alternatives = (
            [ScriptEntry.from_dict(entry) for entry in alternatives_raw]
            if alternatives_raw is not None
            else None
        )
        return cls(
            package_managers=pkg_managers,
            script=data.get("script"),
            script_file=data.get("script_file"),
            alternatives=alternatives,
        )


@dataclass
class ToolConfig:
    name: str
    description: str
    check: str
    install: InstallSpec
    deps: list[str]

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
            install=InstallSpec.from_dict(data["install"]),
            deps=data.get("deps", []),
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
