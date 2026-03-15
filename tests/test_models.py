import pytest

from devstrap.models import InstallSpec, ScriptEntry, ToolConfig, load_manifest


class TestScriptEntry:
    def test_from_dict_with_script(self):
        entry = ScriptEntry.from_dict({"script": "echo hello"})
        assert entry.script == "echo hello"
        assert entry.script_file is None

    def test_from_dict_with_script_file(self):
        entry = ScriptEntry.from_dict({"script_file": "scripts/install.sh"})
        assert entry.script is None
        assert entry.script_file == "scripts/install.sh"

    def test_from_dict_both_raises(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            ScriptEntry.from_dict({"script": "echo", "script_file": "install.sh"})

    def test_from_dict_neither_raises(self):
        with pytest.raises(ValueError, match="must have.*script.*script_file"):
            ScriptEntry.from_dict({})


class TestInstallSpec:
    def test_from_dict_pkg_managers_only(self):
        spec = InstallSpec.from_dict({"brew": "git", "apt": "git"})
        assert spec.package_managers == {"brew": "git", "apt": "git"}
        assert spec.script is None
        assert spec.script_file is None
        assert spec.alternatives is None

    def test_from_dict_with_script(self):
        spec = InstallSpec.from_dict({"brew": "navi", "script": "curl ... | sh"})
        assert spec.package_managers == {"brew": "navi"}
        assert spec.script == "curl ... | sh"

    def test_from_dict_with_multiline_script(self):
        spec = InstallSpec.from_dict({"script": "line1\nline2\nline3"})
        assert spec.script == "line1\nline2\nline3"

    def test_from_dict_with_script_file(self):
        spec = InstallSpec.from_dict({"script_file": "scripts/install.sh"})
        assert spec.script_file == "scripts/install.sh"

    def test_from_dict_with_alternatives(self):
        spec = InstallSpec.from_dict(
            {
                "brew": "uv",
                "alternatives": [
                    {"script": "curl ... | sh"},
                    {"script": "wget ... | sh"},
                ],
            }
        )
        assert spec.package_managers == {"brew": "uv"}
        assert len(spec.alternatives) == 2
        assert spec.alternatives[0].script == "curl ... | sh"
        assert spec.alternatives[1].script == "wget ... | sh"

    def test_from_dict_script_and_script_file_raises(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            InstallSpec.from_dict({"script": "echo", "script_file": "install.sh"})

    def test_from_dict_script_and_alternatives_raises(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            InstallSpec.from_dict(
                {
                    "script": "echo",
                    "alternatives": [{"script": "echo"}],
                }
            )

    def test_from_dict_script_file_and_alternatives_raises(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            InstallSpec.from_dict(
                {
                    "script_file": "install.sh",
                    "alternatives": [{"script": "echo"}],
                }
            )


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
        assert tool.install.package_managers == {"brew": "git", "apt": "git"}

    def test_from_dict_with_script(self):
        data = {
            "name": "navi",
            "description": "Cheatsheet tool",
            "check": "navi --version",
            "install": {
                "brew": "navi",
                "script": "curl -sL https://example.com | bash",
            },
        }
        tool = ToolConfig.from_dict(data)
        assert tool.install.script == "curl -sL https://example.com | bash"

    def test_from_dict_with_alternatives(self):
        data = {
            "name": "uv",
            "description": "Python package manager",
            "check": "uv --version",
            "install": {
                "brew": "uv",
                "alternatives": [
                    {"script": "curl -LsSf https://example.com | sh"},
                    {"script": "wget -qO- https://example.com | sh"},
                ],
            },
        }
        tool = ToolConfig.from_dict(data)
        assert len(tool.install.alternatives) == 2

    def test_from_dict_with_deps(self):
        data = {
            "name": "zsh-autosuggestions",
            "description": "Autosuggestions",
            "check": "test -d ~/.oh-my-zsh/custom/plugins/zsh-autosuggestions",
            "install": {"script": "git clone https://example.com"},
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
        assert len(tools) >= 12
        names = [t.name for t in tools]
        assert "git" in names
        assert "neovim" in names
        assert "zsh-autosuggestions" in names
        assert "zsh-syntax-highlighting" in names
