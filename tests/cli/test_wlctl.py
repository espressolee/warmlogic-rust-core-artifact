# ==========================================================
# Tests: wlctl.py (CLI entry point)
# ==========================================================
"""Tests for main CLI entry point."""

import pytest
from unittest.mock import patch, MagicMock

from warm_logic_core.cli.wlctl import create_parser, main


class TestCreateParser:
    """Tests for create_parser function."""

    def test_creates_parser(self):
        """Test parser creation."""
        parser = create_parser()
        assert parser is not None
        assert parser.prog == "wlctl"

    def test_has_version_option(self):
        """Test version option exists."""
        parser = create_parser()
        # Check version action exists
        assert any(
            action.option_strings and "--version" in action.option_strings
            for action in parser._actions
        )

    def test_has_json_option(self):
        """Test --json option exists."""
        parser = create_parser()
        assert any(
            action.option_strings and "--json" in action.option_strings
            for action in parser._actions
        )

    def test_has_verbose_option(self):
        """Test --verbose option exists."""
        parser = create_parser()
        assert any(
            action.option_strings
            and ("--verbose" in action.option_strings or "-v" in action.option_strings)
            for action in parser._actions
        )

    def test_has_subcommands(self):
        """Test subcommands are registered."""
        parser = create_parser()
        # Check subparsers exist
        subparsers = None
        for action in parser._actions:
            if hasattr(action, "_parser_class"):
                subparsers = action
                break
        assert subparsers is not None


class TestMain:
    """Tests for main function."""

    def test_no_command_shows_help(self, capsys):
        """Test no command shows help."""
        result = main([])
        assert result == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower() or "wlctl" in captured.out.lower()

    def test_invalid_command_returns_error(self):
        """Test invalid command returns error."""
        with pytest.raises(SystemExit) as exc_info:
            main(["nonexistent-command"])
        assert exc_info.value.code == 2  # argparse error code

    def test_keyboard_interrupt_returns_130(self):
        """Test keyboard interrupt returns 130."""
        with patch("warm_logic_core.cli.wlctl.create_parser") as mock_parser:
            mock = MagicMock()
            mock.parse_args.return_value = MagicMock(command="status", json=False)
            mock.parse_args.return_value.func = MagicMock(side_effect=KeyboardInterrupt)
            mock_parser.return_value = mock

            result = main(["status"])
            assert result == 130


class TestStatusCommand:
    """Tests for status command."""

    def test_status_command_exists(self):
        """Test status command is registered."""
        parser = create_parser()
        args = parser.parse_args(["status"])
        assert args.command == "status"

    def test_status_with_component(self):
        """Test status with component flag."""
        parser = create_parser()
        args = parser.parse_args(["status", "-c", "kernel"])
        assert args.component == "kernel"

    def test_status_with_detailed(self):
        """Test status with detailed flag."""
        parser = create_parser()
        args = parser.parse_args(["status", "--detailed"])
        assert args.detailed is True


class TestConfigCommand:
    """Tests for config command."""

    def test_config_command_exists(self):
        """Test config command is registered."""
        parser = create_parser()
        args = parser.parse_args(["config", "validate"])
        assert args.command == "config"
        assert args.config_command == "validate"

    def test_config_validate_with_files(self):
        """Test config validate with files."""
        parser = create_parser()
        args = parser.parse_args(["config", "validate", "file1.json", "file2.yaml"])
        assert args.files == ["file1.json", "file2.yaml"]

    def test_config_diff(self):
        """Test config diff command."""
        parser = create_parser()
        args = parser.parse_args(["config", "diff", "a.json", "b.json"])
        assert args.file1 == "a.json"
        assert args.file2 == "b.json"

    def test_config_export(self):
        """Test config export command."""
        parser = create_parser()
        args = parser.parse_args(["config", "export", "-o", "out.json", "-f", "json"])
        assert args.output == "out.json"
        assert args.format == "json"

    def test_config_show(self):
        """Test config show command."""
        parser = create_parser()
        args = parser.parse_args(["config", "show", "governance.policy"])
        assert args.key == "governance.policy"


class TestSchemaCommand:
    """Tests for schema command."""

    def test_schema_list(self):
        """Test schema list command."""
        parser = create_parser()
        args = parser.parse_args(["schema", "list"])
        assert args.command == "schema"
        assert args.schema_command == "list"

    def test_schema_show(self):
        """Test schema show command."""
        parser = create_parser()
        args = parser.parse_args(["schema", "show", "os_state"])
        assert args.name == "os_state"

    def test_schema_validate(self):
        """Test schema validate command."""
        parser = create_parser()
        args = parser.parse_args(["schema", "validate", "os_state", "data.json"])
        assert args.schema_name == "os_state"
        assert args.file == "data.json"


class TestPluginCommand:
    """Tests for plugin command."""

    def test_plugin_list(self):
        """Test plugin list command."""
        parser = create_parser()
        args = parser.parse_args(["plugin", "list"])
        assert args.command == "plugin"
        assert args.plugin_command == "list"

    def test_plugin_list_all(self):
        """Test plugin list with --all."""
        parser = create_parser()
        args = parser.parse_args(["plugin", "list", "--all"])
        assert args.all is True

    def test_plugin_info(self):
        """Test plugin info command."""
        parser = create_parser()
        args = parser.parse_args(["plugin", "info", "my-plugin"])
        assert args.name == "my-plugin"

    def test_plugin_enable(self):
        """Test plugin enable command."""
        parser = create_parser()
        args = parser.parse_args(["plugin", "enable", "my-plugin"])
        assert args.name == "my-plugin"

    def test_plugin_disable(self):
        """Test plugin disable command."""
        parser = create_parser()
        args = parser.parse_args(["plugin", "disable", "my-plugin"])
        assert args.name == "my-plugin"

    def test_plugin_load(self):
        """Test plugin load command."""
        parser = create_parser()
        args = parser.parse_args(["plugin", "load", "pkg:Plugin", "-v", "2.0.0"])
        assert args.name == "pkg:Plugin"
        assert args.version == "2.0.0"

    def test_plugin_unload(self):
        """Test plugin unload command."""
        parser = create_parser()
        args = parser.parse_args(["plugin", "unload", "my-plugin"])
        assert args.name == "my-plugin"


class TestWatchCommand:
    """Tests for watch command."""

    def test_watch_command_exists(self):
        """Test watch command is registered."""
        parser = create_parser()
        args = parser.parse_args(["watch"])
        assert args.command == "watch"

    def test_watch_with_interval(self):
        """Test watch with interval."""
        parser = create_parser()
        args = parser.parse_args(["watch", "-n", "5.0"])
        assert args.interval == 5.0

    def test_watch_with_count(self):
        """Test watch with count."""
        parser = create_parser()
        args = parser.parse_args(["watch", "-c", "10"])
        assert args.count == 10


class TestHealthCommand:
    """Tests for health command."""

    def test_health_command_exists(self):
        """Test health command is registered."""
        parser = create_parser()
        args = parser.parse_args(["health"])
        assert args.command == "health"

    def test_health_with_quick(self):
        """Test health with --quick."""
        parser = create_parser()
        args = parser.parse_args(["health", "--quick"])
        assert args.quick is True

    def test_health_with_fix(self):
        """Test health with --fix."""
        parser = create_parser()
        args = parser.parse_args(["health", "--fix"])
        assert args.fix is True
