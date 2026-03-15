import subprocess
from unittest.mock import MagicMock, patch

import pytest

from devstrap.installer import (
    InstallResult,
    _describe_install,
    check_tool,
    install_all,
    install_tool,
    resolve_install_order,
)
from devstrap.models import ToolConfig
from devstrap.platform import Platform


@pytest.fixture
def git_tool():
    return ToolConfig.from_dict(
        {
            "name": "git",
            "description": "Version control",
            "check": "git --version",
            "install": {"brew": "git", "apt": "git"},
        }
    )


@pytest.fixture
def navi_tool():
    return ToolConfig.from_dict(
        {
            "name": "navi",
            "description": "Cheatsheet tool",
            "check": "navi --version",
            "install": {
                "brew": "navi",
                "script": "curl -sL https://example.com | bash",
            },
        }
    )


@pytest.fixture
def mac_platform():
    return Platform(os_name="Darwin", pkg_manager="brew")


class TestCheckTool:
    @patch("devstrap.installer.subprocess.run")
    def test_tool_installed(self, mock_run, git_tool):
        mock_run.return_value = MagicMock(returncode=0)
        assert check_tool(git_tool) is True

    @patch("devstrap.installer.subprocess.run")
    def test_tool_not_installed(self, mock_run, git_tool):
        mock_run.side_effect = FileNotFoundError()
        assert check_tool(git_tool) is False

    @patch("devstrap.installer.subprocess.run")
    def test_tool_check_timeout(self, mock_run, git_tool):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git --version", timeout=5)
        assert check_tool(git_tool) is False

    @patch("devstrap.installer.subprocess.run")
    def test_tool_nonzero_exit(self, mock_run, git_tool):
        mock_run.return_value = MagicMock(returncode=1)
        assert check_tool(git_tool) is False

    def test_tool_no_check_command(self):
        tool = ToolConfig.from_dict(
            {
                "name": "x",
                "description": "",
                "check": "",
                "install": {"brew": "x"},
            }
        )
        assert check_tool(tool) is False


class TestInstallTool:
    @patch("devstrap.installer.subprocess.run")
    def test_install_via_pkg_manager(self, mock_run, git_tool, mac_platform):
        mock_run.return_value = MagicMock(returncode=0)
        result = install_tool(git_tool, mac_platform)
        assert result.success is True
        mock_run.assert_called_once_with(
            ["brew", "install", "git"],
            check=True,
            text=True,
        )

    @patch("devstrap.installer.subprocess.run")
    def test_install_via_script(self, mock_run, navi_tool):
        platform = Platform(os_name="Linux", pkg_manager="apt")
        mock_run.return_value = MagicMock(returncode=0)
        result = install_tool(navi_tool, platform)
        assert result.success is True
        mock_run.assert_called_once_with(
            "curl -sL https://example.com | bash",
            shell=True,
            check=True,
            text=True,
        )

    @patch("devstrap.installer.subprocess.run")
    def test_install_via_multiline_script_prepends_set_e(self, mock_run):
        tool = ToolConfig.from_dict(
            {
                "name": "test",
                "description": "",
                "check": "",
                "install": {"script": "line1\nline2"},
            }
        )
        platform = Platform(os_name="Linux", pkg_manager="apt")
        mock_run.return_value = MagicMock(returncode=0)
        result = install_tool(tool, platform)
        assert result.success is True
        mock_run.assert_called_once_with(
            "set -e\nline1\nline2",
            shell=True,
            check=True,
            text=True,
        )

    @patch("devstrap.installer.subprocess.run")
    def test_install_via_script_no_set_e_for_single_line(self, mock_run):
        tool = ToolConfig.from_dict(
            {
                "name": "test",
                "description": "",
                "check": "",
                "install": {"script": "curl -sL example.com | sh"},
            }
        )
        platform = Platform(os_name="Linux", pkg_manager="apt")
        mock_run.return_value = MagicMock(returncode=0)
        result = install_tool(tool, platform)
        assert result.success is True
        mock_run.assert_called_once_with(
            "curl -sL example.com | sh",
            shell=True,
            check=True,
            text=True,
        )

    @patch("devstrap.installer.subprocess.run")
    def test_install_via_script_no_set_e_when_shebang(self, mock_run):
        tool = ToolConfig.from_dict(
            {
                "name": "test",
                "description": "",
                "check": "",
                "install": {"script": "#!/bin/bash\nline1\nline2"},
            }
        )
        platform = Platform(os_name="Linux", pkg_manager="apt")
        mock_run.return_value = MagicMock(returncode=0)
        result = install_tool(tool, platform)
        assert result.success is True
        mock_run.assert_called_once_with(
            "#!/bin/bash\nline1\nline2",
            shell=True,
            check=True,
            text=True,
        )

    @patch("devstrap.installer.subprocess.run")
    def test_install_via_script_no_set_e_when_already_present(self, mock_run):
        tool = ToolConfig.from_dict(
            {
                "name": "test",
                "description": "",
                "check": "",
                "install": {"script": "set -euo pipefail\nline1\nline2"},
            }
        )
        platform = Platform(os_name="Linux", pkg_manager="apt")
        mock_run.return_value = MagicMock(returncode=0)
        result = install_tool(tool, platform)
        assert result.success is True
        mock_run.assert_called_once_with(
            "set -euo pipefail\nline1\nline2",
            shell=True,
            check=True,
            text=True,
        )

    @patch("devstrap.installer.subprocess.run")
    @patch("devstrap.installer.Path.read_text", return_value="#!/bin/bash\necho hello")
    def test_install_via_script_file(self, mock_read, mock_run):
        tool = ToolConfig.from_dict(
            {
                "name": "test",
                "description": "",
                "check": "",
                "install": {"script_file": "scripts/install.sh"},
            }
        )
        platform = Platform(os_name="Linux", pkg_manager="apt")
        mock_run.return_value = MagicMock(returncode=0)
        result = install_tool(tool, platform)
        assert result.success is True
        mock_read.assert_called_once()
        mock_run.assert_called_once_with(
            "#!/bin/bash\necho hello",
            shell=True,
            check=True,
            text=True,
        )

    @patch("devstrap.installer.subprocess.run")
    def test_install_alternatives_fallback(self, mock_run):
        """First alternative fails, second succeeds."""
        tool = ToolConfig.from_dict(
            {
                "name": "test",
                "description": "",
                "check": "",
                "install": {
                    "alternatives": [
                        {"script": "curl fail"},
                        {"script": "wget ok"},
                    ],
                },
            }
        )
        platform = Platform(os_name="Linux", pkg_manager="apt")
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "curl fail"),
            MagicMock(returncode=0),
        ]
        result = install_tool(tool, platform)
        assert result.success is True
        assert mock_run.call_count == 2

    @patch("devstrap.installer.subprocess.run")
    def test_install_alternatives_all_fail(self, mock_run):
        """All alternatives fail — returns failure with last error."""
        tool = ToolConfig.from_dict(
            {
                "name": "test",
                "description": "",
                "check": "",
                "install": {
                    "alternatives": [
                        {"script": "curl fail"},
                        {"script": "wget fail"},
                    ],
                },
            }
        )
        platform = Platform(os_name="Linux", pkg_manager="apt")
        mock_run.side_effect = [
            subprocess.CalledProcessError(1, "curl fail"),
            subprocess.CalledProcessError(1, "wget fail"),
        ]
        result = install_tool(tool, platform)
        assert result.success is False
        assert mock_run.call_count == 2

    def test_install_no_method(self, mac_platform):
        tool = ToolConfig.from_dict(
            {
                "name": "x",
                "description": "",
                "check": "",
                "install": {"apt": "x"},
            }
        )
        result = install_tool(tool, mac_platform)
        assert result.success is False
        assert "no install method" in result.message.lower()

    @patch("devstrap.installer.subprocess.run")
    def test_install_failure(self, mock_run, git_tool, mac_platform):
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "brew install git", stderr="Error: something went wrong"
        )
        result = install_tool(git_tool, mac_platform)
        assert result.success is False


class TestInstallAll:
    @patch("devstrap.installer.install_tool")
    @patch("devstrap.installer.check_tool")
    def test_skips_installed_tools(
        self, mock_check, mock_install, git_tool, mac_platform
    ):
        mock_check.return_value = True
        results = install_all([git_tool], mac_platform)
        assert len(results) == 1
        assert results[0].status == "skipped"
        mock_install.assert_not_called()

    @patch("devstrap.installer.install_tool")
    @patch("devstrap.installer.check_tool")
    def test_installs_missing_tools(
        self, mock_check, mock_install, git_tool, mac_platform
    ):
        mock_check.return_value = False
        mock_install.return_value = InstallResult(
            name="git", status="installed", success=True, message=""
        )
        results = install_all([git_tool], mac_platform)
        assert len(results) == 1
        assert results[0].status == "installed"

    @patch("devstrap.installer.install_tool")
    @patch("devstrap.installer.check_tool")
    def test_continues_after_failure(self, mock_check, mock_install, mac_platform):
        tools = [
            ToolConfig.from_dict(
                {
                    "name": "a",
                    "description": "",
                    "check": "a",
                    "install": {"brew": "a"},
                }
            ),
            ToolConfig.from_dict(
                {
                    "name": "b",
                    "description": "",
                    "check": "b",
                    "install": {"brew": "b"},
                }
            ),
        ]
        mock_check.return_value = False
        mock_install.side_effect = [
            InstallResult(name="a", status="failed", success=False, message="error"),
            InstallResult(name="b", status="installed", success=True, message=""),
        ]
        results = install_all(tools, mac_platform)
        assert len(results) == 2
        assert results[0].status == "failed"
        assert results[1].status == "installed"


class TestResolveInstallOrder:
    def test_no_deps_preserves_order(self):
        tools = [
            ToolConfig.from_dict(
                {
                    "name": "a",
                    "description": "",
                    "check": "",
                    "install": {"brew": "a"},
                }
            ),
            ToolConfig.from_dict(
                {
                    "name": "b",
                    "description": "",
                    "check": "",
                    "install": {"brew": "b"},
                }
            ),
            ToolConfig.from_dict(
                {
                    "name": "c",
                    "description": "",
                    "check": "",
                    "install": {"brew": "c"},
                }
            ),
        ]
        result = resolve_install_order(tools)
        assert [t.name for t in result] == ["a", "b", "c"]

    def test_deps_sorted_before_dependents(self):
        tools = [
            ToolConfig.from_dict(
                {
                    "name": "plugin",
                    "description": "",
                    "check": "",
                    "install": {"script": "echo"},
                    "deps": ["framework"],
                }
            ),
            ToolConfig.from_dict(
                {
                    "name": "framework",
                    "description": "",
                    "check": "",
                    "install": {"script": "echo"},
                }
            ),
        ]
        result = resolve_install_order(tools)
        assert [t.name for t in result] == ["framework", "plugin"]

    def test_transitive_deps(self):
        tools = [
            ToolConfig.from_dict(
                {
                    "name": "c",
                    "description": "",
                    "check": "",
                    "install": {"script": "echo"},
                    "deps": ["b"],
                }
            ),
            ToolConfig.from_dict(
                {
                    "name": "b",
                    "description": "",
                    "check": "",
                    "install": {"script": "echo"},
                    "deps": ["a"],
                }
            ),
            ToolConfig.from_dict(
                {
                    "name": "a",
                    "description": "",
                    "check": "",
                    "install": {"script": "echo"},
                }
            ),
        ]
        result = resolve_install_order(tools)
        names = [t.name for t in result]
        assert names.index("a") < names.index("b") < names.index("c")

    def test_unknown_dep_raises(self):
        tools = [
            ToolConfig.from_dict(
                {
                    "name": "plugin",
                    "description": "",
                    "check": "",
                    "install": {"script": "echo"},
                    "deps": ["nonexistent"],
                }
            ),
        ]
        with pytest.raises(ValueError, match="unknown tool 'nonexistent'"):
            resolve_install_order(tools)

    def test_cycle_raises(self):
        tools = [
            ToolConfig.from_dict(
                {
                    "name": "a",
                    "description": "",
                    "check": "",
                    "install": {"script": "echo"},
                    "deps": ["b"],
                }
            ),
            ToolConfig.from_dict(
                {
                    "name": "b",
                    "description": "",
                    "check": "",
                    "install": {"script": "echo"},
                    "deps": ["a"],
                }
            ),
        ]
        with pytest.raises(ValueError, match="cycle"):
            resolve_install_order(tools)

    def test_diamond_deps(self):
        """A and B both depend on C; D depends on A and B."""
        tools = [
            ToolConfig.from_dict(
                {
                    "name": "d",
                    "description": "",
                    "check": "",
                    "install": {"script": "echo"},
                    "deps": ["a", "b"],
                }
            ),
            ToolConfig.from_dict(
                {
                    "name": "a",
                    "description": "",
                    "check": "",
                    "install": {"script": "echo"},
                    "deps": ["c"],
                }
            ),
            ToolConfig.from_dict(
                {
                    "name": "b",
                    "description": "",
                    "check": "",
                    "install": {"script": "echo"},
                    "deps": ["c"],
                }
            ),
            ToolConfig.from_dict(
                {
                    "name": "c",
                    "description": "",
                    "check": "",
                    "install": {"script": "echo"},
                }
            ),
        ]
        result = resolve_install_order(tools)
        names = [t.name for t in result]
        assert names.index("c") < names.index("a")
        assert names.index("c") < names.index("b")
        assert names.index("a") < names.index("d")
        assert names.index("b") < names.index("d")


class TestDescribeInstall:
    def test_describe_pkg_manager(self, mac_platform):
        tool = ToolConfig.from_dict(
            {
                "name": "git",
                "description": "",
                "check": "",
                "install": {"brew": "git"},
            }
        )
        result = _describe_install(tool, mac_platform)
        assert result == "brew install git"

    def test_describe_single_line_script(self):
        tool = ToolConfig.from_dict(
            {
                "name": "test",
                "description": "",
                "check": "",
                "install": {"script": "curl -sL example.com | sh"},
            }
        )
        platform = Platform(os_name="Linux", pkg_manager="apt")
        result = _describe_install(tool, platform)
        assert result == "curl -sL example.com | sh"

    def test_describe_multiline_script_truncates(self):
        tool = ToolConfig.from_dict(
            {
                "name": "test",
                "description": "",
                "check": "",
                "install": {"script": "line1\nline2\nline3"},
            }
        )
        platform = Platform(os_name="Linux", pkg_manager="apt")
        result = _describe_install(tool, platform)
        assert result == "line1..."

    def test_describe_script_file(self):
        tool = ToolConfig.from_dict(
            {
                "name": "test",
                "description": "",
                "check": "",
                "install": {"script_file": "scripts/install.sh"},
            }
        )
        platform = Platform(os_name="Linux", pkg_manager="apt")
        result = _describe_install(tool, platform)
        assert result == "run scripts/install.sh"

    def test_describe_alternatives(self):
        tool = ToolConfig.from_dict(
            {
                "name": "test",
                "description": "",
                "check": "",
                "install": {
                    "alternatives": [
                        {"script": "curl ... | sh"},
                        {"script": "wget ... | sh"},
                    ],
                },
            }
        )
        platform = Platform(os_name="Linux", pkg_manager="apt")
        result = _describe_install(tool, platform)
        assert result == "curl ... | sh || wget ... | sh"
