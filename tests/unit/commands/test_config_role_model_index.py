"""Unit tests for `config role-model` accepting a 1-based list index.

The numbered list the CLI prints must be the same list the install wizard shows,
otherwise an index means two different things in the two places.
"""

import io
import json
import re
import pytest
from unittest.mock import patch

import agent_notes.commands.wizard as wiz
from agent_notes.commands.config import compatible_models_for, role_model
from agent_notes.registries.cli_registry import load_registry


def _state_dict(clis=("claude",)):
    return {
        "source_path": "/tmp/test",
        "source_commit": "abc123",
        "global": {
            "installed_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "mode": "symlink",
            "clis": {
                name: {"role_models": {"orchestrator": "claude-sonnet-4-6"}, "installed": {}}
                for name in clis
            },
        },
        "local": {},
        "memory": {"backend": "local", "path": ""},
    }


@pytest.fixture()
def state_file(tmp_path):
    sf = tmp_path / "state.json"
    sf.write_text(json.dumps(_state_dict()))
    return sf


def _patch_state_file(sf):
    from agent_notes.services import state_store
    return patch.object(state_store, "state_file", return_value=sf)


def _claude_models():
    return compatible_models_for(load_registry().get("claude"))


class TestIndexResolution:
    def test_index_resolves_to_matching_model(self, state_file):
        expected = _claude_models()[2].id
        captured = {}

        with _patch_state_file(state_file), \
             patch("agent_notes.commands.config._apply_and_regenerate",
                   side_effect=lambda state, before: captured.update(state=state)):
            role_model("orchestrator", "3", cli_filter="claude")

        assert captured["state"].global_install.clis["claude"].role_models["orchestrator"] == expected

    def test_index_resolution_is_echoed_before_the_diff(self, state_file, capsys):
        expected = _claude_models()[0].id

        with _patch_state_file(state_file), \
             patch("agent_notes.commands.config._apply_and_regenerate"):
            role_model("orchestrator", "1", cli_filter="claude")

        assert f"1 -> {expected}" in capsys.readouterr().out

    def test_non_integer_value_is_still_treated_as_a_model_id(self, state_file):
        captured = {}

        with _patch_state_file(state_file), \
             patch("agent_notes.commands.config._apply_and_regenerate",
                   side_effect=lambda state, before: captured.update(state=state)):
            role_model("orchestrator", "claude-sonnet-4-6", cli_filter="claude")

        assert captured["state"].global_install.clis["claude"].role_models["orchestrator"] == "claude-sonnet-4-6"

    def test_out_of_range_index_exits_1_naming_the_range(self, state_file, capsys):
        count = len(_claude_models())

        with _patch_state_file(state_file), \
             patch("agent_notes.commands.config._apply_and_regenerate") as apply_mock, \
             pytest.raises(SystemExit) as exc:
            role_model("orchestrator", str(count + 1), cli_filter="claude")

        assert exc.value.code == 1
        assert f"1-{count}" in capsys.readouterr().out
        apply_mock.assert_not_called()

    def test_zero_index_exits_1(self, state_file):
        with _patch_state_file(state_file), pytest.raises(SystemExit) as exc:
            role_model("orchestrator", "0", cli_filter="claude")

        assert exc.value.code == 1

    def test_index_with_multiple_target_clis_exits_1(self, tmp_path, capsys):
        sf = tmp_path / "state.json"
        sf.write_text(json.dumps(_state_dict(clis=("claude", "opencode"))))

        with _patch_state_file(sf), \
             patch("agent_notes.commands.config._apply_and_regenerate") as apply_mock, \
             pytest.raises(SystemExit) as exc:
            role_model("orchestrator", "1")

        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "claude" in out and "opencode" in out and "--cli" in out
        apply_mock.assert_not_called()


class TestListMode:
    def test_omitting_the_value_prints_the_numbered_list_and_writes_nothing(self, state_file, capsys):
        original = state_file.read_text()

        with _patch_state_file(state_file), \
             patch("agent_notes.commands.config._apply_and_regenerate") as apply_mock:
            role_model("orchestrator", cli_filter="claude")

        out = capsys.readouterr().out
        for index, model in enumerate(_claude_models(), 1):
            assert f"{index:>2}  {model.id}" in out
        apply_mock.assert_not_called()
        assert state_file.read_text() == original


class TestRankedColumns:
    def test_list_shows_rank_order_with_coding_index_and_input_price(self, state_file, capsys):
        with _patch_state_file(state_file), \
             patch("agent_notes.commands.config._apply_and_regenerate"):
            role_model("orchestrator", cli_filter="claude")

        out = capsys.readouterr().out
        assert "$/M in" in out, "price column must say it is the INPUT price"

        models = _claude_models()
        rated = [m for m in models if m.coding_index is not None]
        assert [m.coding_index for m in rated] == sorted(
            (m.coding_index for m in rated), reverse=True
        ), "list must read frontier-first"
        assert all(m.coding_index is not None for m in models[:len(rated)]), \
            "unrated models must sort last"

        best = models[0]
        assert f"{best.id}" in out and f"{best.coding_index:.1f}" in out
        assert f"{best.price_in:.2f}" in out

    def test_intelligence_column_is_shown_next_to_coding(self, state_file, capsys):
        with _patch_state_file(state_file), \
             patch("agent_notes.commands.config._apply_and_regenerate"):
            role_model("orchestrator", cli_filter="claude")

        out = capsys.readouterr().out
        header = next(line for line in out.splitlines() if "coding" in line)
        columns = [c.strip() for c in re.split(r"\s{2,}", header.strip())]
        assert columns == ["#", "model", "int", "coding", "$/M in"]

        rated = next(m for m in _claude_models() if m.intelligence_index is not None)
        row = next(line for line in out.splitlines() if f" {rated.id} " in line)
        assert f"{rated.intelligence_index:.1f}" in row

    def test_models_without_an_intelligence_score_render_a_dash(self, state_file, capsys):
        from agent_notes.commands.config import model_columns

        gap = [m for m in _claude_models()
               if m.intelligence_index is None and m.coding_index is not None]
        assert gap, "fixture assumption: some rated models have no intelligence index"

        with _patch_state_file(state_file), \
             patch("agent_notes.commands.config._apply_and_regenerate"):
            role_model("orchestrator", cli_filter="claude")

        out = capsys.readouterr().out
        assert model_columns(gap[0]) in out
        assert "0.0" not in model_columns(gap[0])

    def test_unrated_models_render_a_dash(self, state_file, capsys):
        from agent_notes.commands.config import model_columns

        unrated = [m for m in _claude_models() if m.coding_index is None]
        assert unrated, "fixture assumption: the claude catalog has unrated models"

        with _patch_state_file(state_file), \
             patch("agent_notes.commands.config._apply_and_regenerate"):
            role_model("orchestrator", cli_filter="claude")

        out = capsys.readouterr().out
        assert model_columns(unrated[0]) in out
        assert "—" in model_columns(unrated[0])


class TestWizardAndCliShareTheSameList:
    def test_wizard_options_match_the_numbered_cli_list(self, monkeypatch):
        seen = {}

        def fake_radio(title, options, default=0, **kwargs):
            seen.setdefault("options", options)
            return options[default][1]

        monkeypatch.setattr(wiz, "_can_interactive", lambda: True)
        monkeypatch.setattr(wiz, "_select_accept_all_models", lambda **k: False)
        monkeypatch.setattr(wiz, "_radio_select", fake_radio)

        with patch("sys.stdout", io.StringIO()):
            wiz._select_models_per_role({"claude"}, step=2, total=9, version="x")

        wizard_ids = [model_id for _label, model_id in seen["options"]]
        assert wizard_ids == [m.id for m in _claude_models()]


class TestMultiProviderOrdering:
    """opencode accepts anthropic AND openai, so it is the only backend where a
    per-provider ordering is distinguishable from a global one. Asserting against
    claude alone cannot fail: its list is single-provider and already sorted."""

    def _opencode_models(self):
        return compatible_models_for(load_registry().get("opencode"))

    def test_merged_list_is_globally_frontier_first(self):
        models = self._opencode_models()
        rated = [m for m in models if m.coding_index is not None]

        assert len(models) > len(rated), "fixture assumption: catalog has unrated models"
        assert [m.coding_index for m in rated] == sorted(
            (m.coding_index for m in rated), reverse=True
        ), "merged multi-provider list must be sorted by capability, not by provider block"
        assert all(m.coding_index is not None for m in models[:len(rated)]), \
            "unrated models must sort last"

    def test_providers_interleave_rather_than_forming_blocks(self):
        families = [m.family for m in self._opencode_models() if m.coding_index is not None]
        distinct_runs = sum(1 for a, b in zip(families, families[1:]) if a != b) + 1

        assert set(families) == {"claude", "gpt"}, "fixture assumption: both providers rated"
        assert distinct_runs > 2, (
            f"rated models form {distinct_runs} provider run(s) — the two per-provider "
            f"seed rankings were concatenated instead of merged: {families}"
        )

    def test_printed_list_matches_the_merged_order(self, tmp_path, capsys):
        sf = tmp_path / "state.json"
        sf.write_text(json.dumps(_state_dict(clis=("opencode",))))

        with _patch_state_file(sf), \
             patch("agent_notes.commands.config._apply_and_regenerate") as apply_mock:
            role_model("orchestrator", cli_filter="opencode")

        out = capsys.readouterr().out
        printed = [m.group(1) for m in
                   (re.match(r"\s+\d+\s+(\S+)", line) for line in out.splitlines())
                   if m]
        assert printed == [m.id for m in self._opencode_models()]
        apply_mock.assert_not_called()
