"""Output-order coverage for `agent-notes list`.

`list models` prints one section per provider, each in that provider's own rank
order — `rank` is per-provider data, so a single flat list would make the numbers
read as one sequence they are not. Nothing asserted this before, so a change of
ordering was silent.
"""

import re

from agent_notes.commands.list import list_models, list_roles
from agent_notes.registries.model_registry import load_model_registry
from agent_notes.registries.role_registry import load_role_registry


def _provider_of(model):
    return next(iter(model.aliases))


def _sections(out: str) -> dict:
    """{provider: [model ids, in printed order]} parsed from the printed table."""
    known = {m.id for m in load_model_registry().all()}
    sections: dict = {}
    current = None
    for line in out.splitlines():
        header = re.match(r"\s{2}(\S+) \(\d+\):", line)
        if header:
            current = header.group(1)
            sections[current] = []
            continue
        row = re.match(r"\s+\d+\s+(\S+)", line)
        if row and current is not None and row.group(1) in known:
            sections[current].append(row.group(1))
    return sections


class TestListModels:
    def test_models_are_grouped_by_provider(self, capsys):
        list_models()
        sections = _sections(capsys.readouterr().out)

        expected = {}
        for model in load_model_registry().all():
            expected.setdefault(_provider_of(model), set()).add(model.id)

        assert set(sections) == set(expected)
        for provider, ids in expected.items():
            assert set(sections[provider]) == ids, f"{provider} section lists foreign models"

    def test_each_provider_prints_in_its_own_rank_order(self, capsys):
        list_models()
        sections = _sections(capsys.readouterr().out)

        by_id = {m.id: m for m in load_model_registry().all()}
        for provider, printed in sections.items():
            ranks = [by_id[mid].rank for mid in printed]
            assert ranks == sorted(ranks), f"{provider} is not in rank order"
            # A flat id sort would satisfy "sorted" only by accident — pin the
            # exact sequence so reverting to `sorted(models, key=id)` fails here.
            assert printed != sorted(printed), (
                f"{provider} is in id order, not rank order"
            )

    def test_anthropic_rank_order_is_frontier_first(self, capsys):
        list_models()
        sections = _sections(capsys.readouterr().out)

        assert sections["anthropic"][:4] == [
            "claude-fable-5-1", "claude-opus-5", "claude-fable-5", "claude-opus-4-8",
        ]

    def test_providers_print_in_name_order(self, capsys):
        list_models()
        sections = _sections(capsys.readouterr().out)

        assert list(sections) == sorted(sections)

    def test_every_catalog_model_is_listed_once(self, capsys):
        list_models()
        printed = [mid for ids in _sections(capsys.readouterr().out).values() for mid in ids]

        assert sorted(printed) == sorted(m.id for m in load_model_registry().all())

    def test_columns_are_rank_id_intelligence_coding_price(self, capsys):
        list_models()
        out = capsys.readouterr().out

        header = next(line for line in out.splitlines() if "rank" in line)
        columns = [c.strip() for c in re.split(r"\s{2,}", header.strip())]
        assert columns == ["rank", "model", "int", "coding", "$/M in"]

    def test_missing_metrics_render_an_em_dash(self, capsys):
        models = load_model_registry().all()
        unrated = [m for m in models if m.coding_index is None]
        no_intelligence = [m for m in models if m.intelligence_index is None
                           and m.coding_index is not None]
        assert unrated and no_intelligence, "fixture assumption: catalog has gaps in both metrics"

        list_models()
        out = capsys.readouterr().out

        for model in unrated[:1] + no_intelligence[:1]:
            row = next(line for line in out.splitlines()
                       if re.match(rf"\s+\d+\s+{re.escape(model.id)}\s", line))
            assert "—" in row
            assert "0.0" not in row.split()[2:4]

    def test_header_counts_the_catalog(self, capsys):
        list_models()
        out = capsys.readouterr().out

        assert f"Models ({len(load_model_registry().all())}):" in out


class TestListRoles:
    def test_each_role_shows_the_budget_that_drives_selection(self, capsys):
        list_roles()
        out = capsys.readouterr().out

        for role in load_role_registry().all():
            expected = "unbounded" if role.budget is None else f"${role.budget:g}/M in"
            assert f"(budget: {expected})" in out, f"role {role.name} missing its budget"
