import pytest

from devstrap.models import ToolConfig, load_manifest


class TestToolConfig:
    def test_from_dict_full(self):
        data = {
            "name": "git",
            "description": "Version control",
            "check": "git --version",
            "install": {"brew": "git", "apt": "git"},
        }
        tool = ToolConfig.from_dict(data)
        assert tool.name == "git"
        assert tool.description == "Version control"
        assert tool.check == "git --version"
        assert tool.install == {"brew": "git", "apt": "git"}

    def test_from_dict_with_scripts(self):
        data = {
            "name": "navi",
            "description": "Cheatsheet tool",
            "check": "navi --version",
            "install": {
                "brew": "navi",
                "scripts": ["curl -sL https://example.com | bash"],
            },
        }
        tool = ToolConfig.from_dict(data)
        assert tool.install["scripts"] == ["curl -sL https://example.com | bash"]

    def test_from_dict_with_deps(self):
        data = {
            "name": "zsh-autosuggestions",
            "description": "Autosuggestions",
            "check": "test -d ~/.oh-my-zsh/custom/plugins/zsh-autosuggestions",
            "install": {"scripts": ["git clone https://example.com"]},
            "deps": ["oh-my-zsh"],
        }
        tool = ToolConfig.from_dict(data)
        assert tool.deps == ["oh-my-zsh"]

    def test_from_dict_no_deps_defaults_empty(self):
        data = {
            "name": "git",
            "description": "Version control",
            "check": "git --version",
            "install": {"brew": "git"},
        }
        tool = ToolConfig.from_dict(data)
        assert tool.deps == []

    def test_from_dict_missing_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            ToolConfig.from_dict({"description": "x", "check": "x", "install": {}})

    def test_from_dict_missing_install_raises(self):
        with pytest.raises(ValueError, match="install"):
            ToolConfig.from_dict({"name": "x", "description": "x", "check": "x"})


class TestLoadManifest:
    def test_load_from_yaml_string(self, tmp_path):
        yaml_content = """
tools:
  - name: git
    description: Version control
    check: git --version
    install:
      brew: git
      apt: git
  - name: tmux
    description: Terminal multiplexer
    check: tmux -V
    install:
      brew: tmux
"""
        manifest_file = tmp_path / "tools.yaml"
        manifest_file.write_text(yaml_content)
        tools = load_manifest(manifest_file)
        assert len(tools) == 2
        assert tools[0].name == "git"
        assert tools[1].name == "tmux"

    def test_load_invalid_yaml(self, tmp_path):
        manifest_file = tmp_path / "tools.yaml"
        manifest_file.write_text("not: [valid: yaml: {")
        with pytest.raises(Exception):
            load_manifest(manifest_file)

    def test_load_missing_tools_key(self, tmp_path):
        manifest_file = tmp_path / "tools.yaml"
        manifest_file.write_text("something_else: true\n")
        with pytest.raises(ValueError, match="tools"):
            load_manifest(manifest_file)

    def test_load_bundled_manifest(self):
        """The bundled tools.yaml should load without errors."""
        tools = load_manifest()
        assert len(tools) >= 10
        names = [t.name for t in tools]
        assert "git" in names
        assert "neovim" in names
