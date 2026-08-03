import agent_notes.commands.wizard as wiz


def test_accept_all_yes_skips_per_role_prompts(monkeypatch):
    # Gate returns "yes"; per-role model radios must NOT be called.
    monkeypatch.setattr(wiz, "_can_interactive", lambda: True)
    calls = {"gate": 0, "per_role": 0}

    def fake_gate(*a, **k):
        calls["gate"] += 1
        return "yes"

    def fake_radio(*a, **k):
        calls["per_role"] += 1
        raise AssertionError("per-role radio should not run when accept-all=yes")

    # _select_gate_accept_all is the new helper; per-role uses _radio_select
    monkeypatch.setattr(wiz, "_select_accept_all_models", lambda **k: True)
    monkeypatch.setattr(wiz, "_radio_select", fake_radio)

    role_models, role_efforts = wiz._select_models_per_role({"claude"}, step=2, total=9, version="x")

    # claude skips orchestrator; the other roles get their computed defaults, no prompts
    assert "claude" in role_models
    assert "orchestrator" not in role_models["claude"]
    assert len(role_models["claude"]) >= 1  # defaults populated without prompting


def test_accept_all_no_falls_through_to_per_role(monkeypatch):
    monkeypatch.setattr(wiz, "_can_interactive", lambda: True)
    monkeypatch.setattr(wiz, "_select_accept_all_models", lambda **k: False)
    picked = {}

    def fake_radio(title, options, default=0, **k):
        # user accepts each highlighted default
        return options[default][1]

    monkeypatch.setattr(wiz, "_radio_select", fake_radio)
    role_models, _ = wiz._select_models_per_role({"claude"}, step=2, total=9, version="x")
    assert "claude" in role_models and len(role_models["claude"]) >= 1


def test_accept_all_yes_matches_per_role_defaults(monkeypatch):
    # The models chosen by accept-all=yes must EQUAL the models chosen by
    # accept-all=no + accepting every highlighted default. (DRY / no drift.)
    monkeypatch.setattr(wiz, "_can_interactive", lambda: True)
    monkeypatch.setattr(wiz, "_radio_select", lambda title, options, default=0, **k: options[default][1])

    monkeypatch.setattr(wiz, "_select_accept_all_models", lambda **k: True)
    yes_models, yes_efforts = wiz._select_models_per_role({"claude"}, step=2, total=9, version="x")

    monkeypatch.setattr(wiz, "_select_accept_all_models", lambda **k: False)
    no_models, no_efforts = wiz._select_models_per_role({"claude"}, step=2, total=9, version="x")

    assert yes_models == no_models
    assert yes_efforts == no_efforts
