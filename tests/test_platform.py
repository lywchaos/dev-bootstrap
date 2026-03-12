from unittest.mock import patch
import pytest
from devstrap.platform import detect_platform, Platform


class TestDetectPlatform:
    @patch("devstrap.platform.shutil.which", side_effect=lambda cmd: "/opt/homebrew/bin/brew" if cmd == "brew" else None)
    @patch("devstrap.platform.platform_system", return_value="Darwin")
    def test_macos_with_brew(self, mock_sys, mock_which):
        p = detect_platform()
        assert p.os_name == "Darwin"
        assert p.pkg_manager == "brew"

    @patch("devstrap.platform.shutil.which", side_effect=lambda cmd: "/usr/bin/apt-get" if cmd == "apt-get" else None)
    @patch("devstrap.platform.platform_system", return_value="Linux")
    def test_linux_with_apt(self, mock_sys, mock_which):
        p = detect_platform()
        assert p.os_name == "Linux"
        assert p.pkg_manager == "apt"

    @patch("devstrap.platform.shutil.which", side_effect=lambda cmd: "/usr/bin/dnf" if cmd == "dnf" else None)
    @patch("devstrap.platform.platform_system", return_value="Linux")
    def test_linux_with_dnf(self, mock_sys, mock_which):
        p = detect_platform()
        assert p.os_name == "Linux"
        assert p.pkg_manager == "dnf"

    @patch("devstrap.platform.shutil.which", side_effect=lambda cmd: "/usr/bin/pacman" if cmd == "pacman" else None)
    @patch("devstrap.platform.platform_system", return_value="Linux")
    def test_linux_with_pacman(self, mock_sys, mock_which):
        p = detect_platform()
        assert p.os_name == "Linux"
        assert p.pkg_manager == "pacman"

    @patch("devstrap.platform.shutil.which", return_value=None)
    @patch("devstrap.platform.platform_system", return_value="Linux")
    def test_linux_no_pkg_manager(self, mock_sys, mock_which):
        p = detect_platform()
        assert p.os_name == "Linux"
        assert p.pkg_manager is None

    @patch("devstrap.platform._handle_missing_homebrew", return_value="brew")
    @patch("devstrap.platform.shutil.which", return_value=None)
    @patch("devstrap.platform.platform_system", return_value="Darwin")
    def test_macos_no_brew_installs_homebrew(self, mock_sys, mock_which, mock_handle):
        p = detect_platform()
        assert p.pkg_manager == "brew"
        mock_handle.assert_called_once()

    @patch("devstrap.platform._handle_missing_homebrew", return_value=None)
    @patch("devstrap.platform.shutil.which", return_value=None)
    @patch("devstrap.platform.platform_system", return_value="Darwin")
    def test_macos_no_brew_declined(self, mock_sys, mock_which, mock_handle):
        p = detect_platform()
        assert p.pkg_manager is None


class TestPlatformInstallCmd:
    def test_brew_install_cmd(self):
        p = Platform(os_name="Darwin", pkg_manager="brew")
        assert p.install_cmd("git") == ["brew", "install", "git"]

    def test_apt_install_cmd(self):
        p = Platform(os_name="Linux", pkg_manager="apt")
        assert p.install_cmd("git") == ["sudo", "apt-get", "install", "-y", "git"]

    def test_dnf_install_cmd(self):
        p = Platform(os_name="Linux", pkg_manager="dnf")
        assert p.install_cmd("git") == ["sudo", "dnf", "install", "-y", "git"]

    def test_pacman_install_cmd(self):
        p = Platform(os_name="Linux", pkg_manager="pacman")
        assert p.install_cmd("git") == ["sudo", "pacman", "-S", "--noconfirm", "git"]

    def test_no_pkg_manager_raises(self):
        p = Platform(os_name="Linux", pkg_manager=None)
        with pytest.raises(RuntimeError, match="No package manager"):
            p.install_cmd("git")
