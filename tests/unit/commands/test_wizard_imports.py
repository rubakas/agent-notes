"""Verify the wizard package re-exports all public symbols correctly."""
import importlib

import pytest


class TestWizardPackageExports:
    """Main entry points are importable from the package top level."""

    def test_interactive_install_importable(self):
        from agent_notes.commands.wizard import interactive_install
        assert callable(interactive_install)

    def test_internal_interactive_install_importable(self):
        from agent_notes.commands.wizard import _interactive_install
        assert callable(_interactive_install)

    def test_execute_functions_importable(self):
        from agent_notes.commands.wizard import (
            install_skills_filtered,
            install_agents_filtered,
            install_config_filtered,
            _execute_install,
        )
        assert callable(install_skills_filtered)
        assert callable(install_agents_filtered)
        assert callable(install_config_filtered)
        assert callable(_execute_install)

    def test_common_helpers_importable_from_package(self):
        from agent_notes.commands.wizard import _get_skill_groups, _count_rules
        assert callable(_get_skill_groups)
        assert callable(_count_rules)


class TestWizardSubmodulesImportable:
    """Each submodule is independently importable without error."""

    @pytest.mark.parametrize("submodule", [
        "agent_notes.commands.wizard",
        "agent_notes.commands.wizard._common",
        "agent_notes.commands.wizard.execute",
        "agent_notes.commands.wizard.orchestrator",
    ])
    def test_submodule_importable(self, submodule):
        mod = importlib.import_module(submodule)
        assert mod is not None

    def test_execute_module_exports_execute_install(self):
        from agent_notes.commands.wizard.execute import _execute_install
        assert callable(_execute_install)

    def test_orchestrator_module_exports_interactive_install(self):
        from agent_notes.commands.wizard.orchestrator import interactive_install
        assert callable(interactive_install)

    def test_common_module_exports_role_ansi_map(self):
        from agent_notes.commands.wizard._common import _ROLE_ANSI
        assert isinstance(_ROLE_ANSI, dict)
        assert len(_ROLE_ANSI) > 0

    def test_common_module_exports_get_skill_groups(self):
        from agent_notes.commands.wizard._common import _get_skill_groups
        assert callable(_get_skill_groups)

    def test_common_module_exports_count_rules(self):
        from agent_notes.commands.wizard._common import _count_rules
        assert callable(_count_rules)


class TestWizardNoCircularImports:
    """Loading wizard submodules in any order must not raise ImportError."""

    def test_no_circular_imports_on_fresh_import(self):
        """All wizard submodules are importable in sequence without circular-import failure."""
        modules = [
            "agent_notes.commands.wizard",
            "agent_notes.commands.wizard._common",
            "agent_notes.commands.wizard.execute",
            "agent_notes.commands.wizard.orchestrator",
        ]
        for mod_name in modules:
            mod = importlib.import_module(mod_name)
            assert mod is not None, f"{mod_name} returned None"


class TestWizardPackageAllList:
    """The __all__ list in the wizard package includes all documented public names."""

    def test_all_includes_interactive_install(self):
        import agent_notes.commands.wizard as wiz
        assert hasattr(wiz, "__all__")
        assert "interactive_install" in wiz.__all__

    def test_all_includes_execute_install(self):
        import agent_notes.commands.wizard as wiz
        assert "_execute_install" in wiz.__all__

    def test_all_names_are_resolvable(self):
        """Every name listed in __all__ must be accessible on the package."""
        import agent_notes.commands.wizard as wiz
        for name in wiz.__all__:
            assert hasattr(wiz, name), (
                f"agent_notes.commands.wizard.__all__ lists '{name}' "
                f"but it is not an attribute of the package"
            )
