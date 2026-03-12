from unittest.mock import patch, MagicMock
import subprocess
import pytest
from devstrap.models import ToolConfig
from devstrap.platform import Platform
from devstrap.installer import check_tool, install_tool, install_all, InstallResult


@pytest.fixture
def git_tool():
    return ToolConfig(
        name="git",
        description="Version control",
        check="git --version",
        install={"brew": "git", "apt": "git"},
    )


@pytest.fixture
def navi_tool():
    return ToolConfig(
        name="navi",
        description="Cheatsheet tool",
        check="navi --version",
        install={"brew": "navi", "script": "curl -sL https://example.com | bash"},
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
        tool = ToolConfig(name="x", description="", check="", install={"brew": "x"})
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
            capture_output=True,
            text=True,
        )

    @patch("devstrap.installer.subprocess.run")
    def test_install_via_script_fallback(self, mock_run, navi_tool):
        platform = Platform(os_name="Linux", pkg_manager="apt")
        mock_run.return_value = MagicMock(returncode=0)
        result = install_tool(navi_tool, platform)
        assert result.success is True
        mock_run.assert_called_once_with(
            "curl -sL https://example.com | bash",
            shell=True,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_install_no_method(self, mac_platform):
        tool = ToolConfig(name="x", description="", check="", install={"dnf": "x"})
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
    def test_skips_installed_tools(self, mock_check, mock_install, git_tool, mac_platform):
        mock_check.return_value = True
        results = install_all([git_tool], mac_platform)
        assert len(results) == 1
        assert results[0].status == "skipped"
        mock_install.assert_not_called()

    @patch("devstrap.installer.install_tool")
    @patch("devstrap.installer.check_tool")
    def test_installs_missing_tools(self, mock_check, mock_install, git_tool, mac_platform):
        mock_check.return_value = False
        mock_install.return_value = InstallResult(name="git", status="installed", success=True, message="")
        results = install_all([git_tool], mac_platform)
        assert len(results) == 1
        assert results[0].status == "installed"

    @patch("devstrap.installer.install_tool")
    @patch("devstrap.installer.check_tool")
    def test_continues_after_failure(self, mock_check, mock_install, mac_platform):
        tools = [
            ToolConfig(name="a", description="", check="a", install={"brew": "a"}),
            ToolConfig(name="b", description="", check="b", install={"brew": "b"}),
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
