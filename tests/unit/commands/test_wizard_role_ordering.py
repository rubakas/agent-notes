"""Tests for canonical role ordering in the wizard: orchestrator → reasoner →
worker → scout, driven by the declarative `order:` field in roles/*.yaml.

Covers the sort key and the post-install Configuration section
(_render_configuration); the review's role ordering is tested in
test_review_role_models.py."""
from agent_notes.domain.role import Role, DEFAULT_ROLE_ORDER


def _make_role(name, order=DEFAULT_ROLE_ORDER):
    return Role(name=name, label=name.capitalize(), description="", order=order)


class TestRoleSortKey:
    def test_sorts_by_declared_order(self):
        from agent_notes.commands.wizard import _role_sort_key
        roles = [_make_role("scout", 4), _make_role("orchestrator", 1),
                 _make_role("worker", 3), _make_role("reasoner", 2)]
        assert [r.name for r in sorted(roles, key=_role_sort_key)] == \
            ["orchestrator", "reasoner", "worker", "scout"]

    def test_unordered_roles_sort_last_alphabetically(self):
        from agent_notes.commands.wizard import _role_sort_key
        roles = [_make_role("zeta"), _make_role("alpha"), _make_role("scout", 4)]
        assert [r.name for r in sorted(roles, key=_role_sort_key)] == \
            ["scout", "alpha", "zeta"]

    def test_none_role_sorts_last_by_name(self):
        """Unknown role names (role=None lookups) must not crash and sort last."""
        from agent_notes.commands.wizard import _role_sort_key
        assert _role_sort_key(None, "mystery") == (DEFAULT_ROLE_ORDER, "mystery")
        assert _role_sort_key(_make_role("scout", 4)) < _role_sort_key(None, "aaa")


class TestConfigurationSectionOrdering:
    def test_configuration_rows_follow_canonical_role_order(self, capsys):
        from agent_notes.commands.wizard.execute import _render_configuration

        role_models = {"claude": {
            "scout": "claude-haiku-4-5",
            "worker": "claude-sonnet-5",
            "reasoner": "claude-opus-4-8",
        }}
        role_efforts = {"claude": {"reasoner": "max"}}
        _render_configuration(role_models, role_efforts)

        out = capsys.readouterr().out
        positions = [out.index(label) for label in ("Reasoner", "Worker", "Scout")]
        assert positions == sorted(positions), f"configuration rows out of order:\n{out}"

    def test_configuration_shows_label_effort_and_hint(self, capsys):
        """Rows reuse _format_role_model_display (picked effort wins over
        typical_effort) and the section ends with the config-command hint."""
        from agent_notes.commands.wizard.execute import _render_configuration

        _render_configuration(
            {"claude": {"reasoner": "claude-opus-4-8"}},
            {"claude": {"reasoner": "max"}},
        )
        out = capsys.readouterr().out
        assert "Configuration" in out
        assert "Claude Opus 4.8 · max" in out
        assert "agent-notes config role-model" in out
        assert "agent-notes config role-effort" in out

    def test_configuration_skipped_when_no_role_models(self, capsys):
        from agent_notes.commands.wizard.execute import _render_configuration

        _render_configuration({}, {})
        _render_configuration({"copilot": {}}, None)
        assert capsys.readouterr().out == ""
