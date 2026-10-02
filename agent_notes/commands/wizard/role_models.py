"""Per-role model and effort choices, shared by the install review and config.

★ is select_model_for_role's own pick, and effort options pass the same three
checks as `config role-effort`, so a screen never offers a choice that a build
would silently drop (spec 005 FR-008, FR-009).
"""
from __future__ import annotations

import contextlib
import io
from typing import Optional

from ...services.tui.screen import DIM, YELLOW, pad
from ...services.tui.widgets import PickItem, ReviewForm, Row, cycle_text

PICKER_HEADER = f"{'':<24}    {'int':>5}  {'coding':>6}  {'$/M in':>8}"
PICKER_LEGEND = "★ recommended   * provisional"


class Catalog:
    """Model data for one session, read once — the catalog loader parses
    seed.json and rules.yaml on every call."""

    def __init__(self, registry=None):
        if registry is None:
            from ...registries.model_registry import load_model_registry
            registry = load_model_registry()
        self.registry = registry
        self._compatible: dict[str, list] = {}

    def compatible(self, backend) -> list:
        from ..config import compatible_models_for
        if backend.name not in self._compatible:
            self._compatible[backend.name] = compatible_models_for(backend, self.registry)
        return self._compatible[backend.name]

    def get(self, model_id: str):
        """The model, or None when the id is not in the catalog."""
        try:
            return self.registry.get(model_id)
        except KeyError:
            return None


def roles_for(backend) -> list:
    from ...registries.role_registry import load_role_registry
    from ._common import _role_sort_key
    roles = sorted(load_role_registry().all(), key=_role_sort_key)
    # Claude Code picks its lead model itself (`/model`); an orchestrator pin
    # would render nowhere there.
    return [role for role in roles
            if not (backend.name == "claude" and role.name == "orchestrator")]


def budget_text(role) -> str:
    return "unbounded" if role.budget is None else f"${role.budget:g}/M in"


def starred_model(catalog, backend, role):
    """The resolver's own pick (★), or None when no rated model fits the budget."""
    from ...services.model_resolver import select_model_for_role
    # It warns on stderr when it widens to a deprecated model; that warning
    # must not land on a full-screen view.
    with contextlib.redirect_stderr(io.StringIO()):
        model, _resolved = select_model_for_role(catalog.compatible(backend), role, backend)
    return model


def initial_model(catalog, backend, role):
    """The pre-selected model: ★, else the first compatible model. None only
    when the CLI has no compatible model at all."""
    from . import _default_model_for_role
    compatible = catalog.compatible(backend)
    if not compatible:
        return None
    with contextlib.redirect_stderr(io.StringIO()):
        return _default_model_for_role(role, compatible, backend)


def _provider(backend, model):
    from . import _effort_provider_for_model
    from ...registries.provider_registry import default_provider_registry
    name = _effort_provider_for_model(backend, model)
    if name is None:
        return None
    try:
        return default_provider_registry().get(name)
    except KeyError:
        return None


def effort_options(backend, model) -> list[str]:
    """The efforts a role may use with *model* on *backend*: the model accepts
    one at all, the provider's vocabulary, then the CLI's subset — the three
    checks `config role-effort` applies (`_check_effort_valid`)."""
    if model is None or not model.capabilities.get("effort_support", True):
        return []
    provider = _provider(backend, model)
    if provider is None:
        return []
    return [effort for effort in provider.efforts
            if not backend.efforts or effort in backend.efforts]


def default_effort(backend, model, role) -> Optional[str]:
    from . import _effort_default_choice
    options = effort_options(backend, model)
    if not options:
        return None
    choice = _effort_default_choice(role, _provider(backend, model))
    return choice if choice in options else options[0]


def recommended_choices(catalog, backend) -> tuple[dict[str, str], dict[str, str]]:
    """(role → model id, role → effort) to start from; both empty when the CLI
    has no compatible model."""
    models: dict[str, str] = {}
    efforts: dict[str, str] = {}
    for role in roles_for(backend):
        model = initial_model(catalog, backend, role)
        if model is None:
            break
        models[role.name] = model.id
        effort = default_effort(backend, model, role)
        if effort:
            efforts[role.name] = effort
    return models, efforts


def set_model(catalog, backend, role, model_id, models, efforts) -> None:
    """Pick *model_id* for *role*; keep the effort only if the new model allows it."""
    models[role.name] = model_id
    model = catalog.get(model_id)
    options = effort_options(backend, model)
    if not options:
        efforts.pop(role.name, None)
    elif efforts.get(role.name) not in options:
        efforts[role.name] = default_effort(backend, model, role)


def reset_role(catalog, backend, role, models, efforts) -> None:
    """Back to the recommended model and its default effort."""
    model = initial_model(catalog, backend, role)
    if model is None:
        return
    models[role.name] = model.id
    effort = default_effort(backend, model, role)
    if effort:
        efforts[role.name] = effort
    else:
        efforts.pop(role.name, None)


def model_items(catalog, backend, role) -> list[PickItem]:
    """Every compatible model, in catalog order, marked for *role*."""
    from ..config import model_metrics
    star = starred_model(catalog, backend, role)
    items = []
    for model in catalog.compatible(backend):
        tags = []
        if model.deprecated:
            tags.append("deprecated")
        if role.budget is not None and model.price_in is not None and model.price_in > role.budget:
            tags.append("over budget")
        mark = "★" if star is not None and model.id == star.id else " "
        items.append(PickItem(model.id, f"{model.id:<24} {mark}  {model_metrics(model)}",
                              tag=" · ".join(tags), dim=model.deprecated))
    return items


def role_line(role, models, efforts) -> str:
    """One role on the review screen: name, model, effort."""
    return (f"{pad(role.name, 10)} {pad(models.get(role.name, '—'), 20)} "
            f"{efforts.get(role.name) or '—'}")


def edit_models(ui, catalog, backend, models, efforts) -> None:
    """The role table for one CLI: ←→ effort, ⏎ model list, r recommended."""
    style = ui.style
    roles = [role for role in roles_for(backend) if role.name in models]

    def pick_model(role) -> None:
        chosen = ui.pick(f"{role.label} · {backend.label} · budget {budget_text(role)}",
                         model_items(catalog, backend, role), current=models.get(role.name),
                         header=PICKER_HEADER, legend=PICKER_LEGEND)
        if chosen:
            set_model(catalog, backend, role, chosen, models, efforts)

    def row_for(role) -> Row:
        model = catalog.get(models[role.name])
        star = starred_model(catalog, backend, role)
        options = [(effort, effort) for effort in effort_options(backend, model)]

        def lines() -> list[str]:
            mark = style("★", YELLOW) if star is not None and star.id == models[role.name] else " "
            effort = efforts.get(role.name)
            effort_text = cycle_text(effort) if effort else style("—", DIM)
            price = (f"{model.price_in:>6.2f}"
                     if model is not None and model.price_in is not None else "     —")
            return [f"{pad(models[role.name], 22)} {mark}  {pad(effort_text, 12)} {price}"]

        def line_edit() -> None:
            pick_model(role)
            choices = effort_options(backend, catalog.get(models[role.name]))
            if choices:
                effort = ui.pick(f"{role.label} · effort", [PickItem(e, e) for e in choices],
                                 current=efforts.get(role.name))
                if effort:
                    efforts[role.name] = effort

        return Row(role.name, role.label, lines, options=options,
                   get=lambda: efforts.get(role.name),
                   set=lambda value: efforts.__setitem__(role.name, value),
                   edit=lambda: pick_model(role), line_edit=line_edit)

    form = ReviewForm(f"Models · {backend.label}", lambda: [row_for(role) for role in roles],
                      hints="↑↓ role   ←→ effort   ⏎ change model   r recommended   esc done",
                      escape_closes=True, default_label="finish", style=style)

    def reset() -> None:
        role = next(role for role in roles if role.name == form.focused.key)
        reset_role(catalog, backend, role, models, efforts)

    form.commands["r"] = reset
    ui.form(form)
