from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devstrap.cli import app
from devstrap.installer import InstallResult
from devstrap.models import ToolConfig
from devstrap.platform import Platform

runner = CliRunner()


@pytest.fixture
def mock_tools():
    return [
        ToolConfig(
            name="git",
            description="Version control",
            check="git --version",
            install={"brew": "git"},
            deps=[],
        ),
        ToolConfig(
            name="navi",
            description="Cheatsheet",
            check="navi --version",
            install={"brew": "navi"},
            deps=[],
        ),
    ]


@pytest.fixture
def mock_platform():
    return Platform(os_name="Darwin", pkg_manager="brew")


class TestVersion:
    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestList:
    @patch("devstrap.cli.check_tool")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_list_shows_tools(
        self, mock_load, mock_detect, mock_check, mock_tools, mock_platform
    ):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        mock_check.side_effect = [True, False]
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "git" in result.output
        assert "navi" in result.output

    @patch("devstrap.cli.check_tool")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_list_shows_install_method(
        self, mock_load, mock_detect, mock_check, mock_tools, mock_platform
    ):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        mock_check.side_effect = [True, False]
        result = runner.invoke(app, ["list"])
        assert "brew" in result.output


class TestInstall:
    @patch("devstrap.cli.install_tool")
    @patch("devstrap.cli.check_tool")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_install_all(
        self,
        mock_load,
        mock_detect,
        mock_check,
        mock_install,
        mock_tools,
        mock_platform,
    ):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        mock_check.side_effect = [True, False]
        mock_install.return_value = InstallResult(
            name="navi", status="installed", success=True, message=""
        )
        result = runner.invoke(app, ["install"])
        assert result.exit_code == 0

    @patch("devstrap.cli.install_tool")
    @patch("devstrap.cli.check_tool")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_install_single_tool(
        self,
        mock_load,
        mock_detect,
        mock_check,
        mock_install,
        mock_tools,
        mock_platform,
    ):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        mock_check.return_value = False
        mock_install.return_value = InstallResult(
            name="git", status="installed", success=True, message=""
        )
        result = runner.invoke(app, ["install", "git"])
        assert result.exit_code == 0

    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_install_unknown_tool(
        self, mock_load, mock_detect, mock_tools, mock_platform
    ):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        result = runner.invoke(app, ["install", "nonexistent"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    @patch("devstrap.cli.check_tool")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_install_dry_run(
        self, mock_load, mock_detect, mock_check, mock_tools, mock_platform
    ):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        mock_check.side_effect = [True, False]
        result = runner.invoke(app, ["install", "--dry-run"])
        assert result.exit_code == 0

    @patch("devstrap.cli.install_tool")
    @patch("devstrap.cli.check_tool")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_install_exits_nonzero_on_failure(
        self,
        mock_load,
        mock_detect,
        mock_check,
        mock_install,
        mock_tools,
        mock_platform,
    ):
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        mock_check.return_value = False
        mock_install.return_value = InstallResult(
            name="git", status="failed", success=False, message="error"
        )
        result = runner.invoke(app, ["install"])
        assert result.exit_code != 0

    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_install_unknown_tool_with_dry_run(
        self, mock_load, mock_detect, mock_tools, mock_platform
    ):
        """Name validation fires before dry-run."""
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        result = runner.invoke(app, ["install", "nonexistent", "--dry-run"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_interactive_requires_tty(
        self, mock_load, mock_detect, mock_tools, mock_platform
    ):
        """--interactive should error when stdin is not a TTY."""
        mock_load.return_value = mock_tools
        mock_detect.return_value = mock_platform
        # CliRunner does not provide a real TTY
        result = runner.invoke(app, ["install", "--interactive"])
        assert result.exit_code != 0
        assert "tty" in result.output.lower()


class TestInstallWithDeps:
    @patch("devstrap.cli.install_tool")
    @patch("devstrap.cli.check_tool")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_install_single_tool_pulls_deps(
        self,
        mock_load,
        mock_detect,
        mock_check,
        mock_install,
        mock_platform,
    ):
        """Installing a tool with deps should auto-install uninstalled deps first."""
        all_tools = [
            ToolConfig(
                name="oh-my-zsh",
                description="",
                check="test -d ~/.oh-my-zsh",
                install={"scripts": ["echo"]},
                deps=[],
            ),
            ToolConfig(
                name="zsh-autosuggestions",
                description="",
                check="test -d ~/.x",
                install={"scripts": ["echo"]},
                deps=["oh-my-zsh"],
            ),
        ]
        mock_load.return_value = all_tools
        mock_detect.return_value = mock_platform
        mock_check.return_value = False
        mock_install.return_value = InstallResult(
            name="", status="installed", success=True, message=""
        )
        result = runner.invoke(app, ["install", "zsh-autosuggestions"])
        assert result.exit_code == 0
        assert mock_install.call_count == 2
        first_call_tool = mock_install.call_args_list[0][0][0]
        assert first_call_tool.name == "oh-my-zsh"

    @patch("devstrap.cli.install_tool")
    @patch("devstrap.cli.check_tool")
    @patch("devstrap.cli.detect_platform")
    @patch("devstrap.cli.load_manifest")
    def test_dep_failed_skips_dependent(
        self,
        mock_load,
        mock_detect,
        mock_check,
        mock_install,
        mock_platform,
    ):
        """If a dep fails, dependent tools get dep_failed status."""
        all_tools = [
            ToolConfig(
                name="oh-my-zsh",
                description="",
                check="",
                install={"scripts": ["echo"]},
                deps=[],
            ),
            ToolConfig(
                name="plugin",
                description="",
                check="",
                install={"scripts": ["echo"]},
                deps=["oh-my-zsh"],
            ),
        ]
        mock_load.return_value = all_tools
        mock_detect.return_value = mock_platform
        mock_check.return_value = False
        mock_install.return_value = InstallResult(
            name="oh-my-zsh", status="failed", success=False, message="error"
        )
        result = runner.invoke(app, ["install"])
        assert result.exit_code != 0
        assert mock_install.call_count == 1
