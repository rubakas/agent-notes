"""Parametrized tests for every agent file in dist/codex/agents/."""
import sys
import pytest
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from agent_notes.config import DIST_DIR

_CODEX_AGENTS_DIR = DIST_DIR / "codex" / "agents"

_VALID_EFFORT_VALUES = {"minimal", "low", "medium", "high", "xhigh"}
_VALID_SANDBOX_MODES = {"read-only", "workspace-write", "danger-full-access"}


def _openai_provider_efforts():
    """Every value `config role-effort --cli codex` will accept and store."""
    from agent_notes.registries.provider_registry import load_provider_registry

    return sorted(load_provider_registry().get("openai").efforts)


_OPENAI_PROVIDER_EFFORTS = _openai_provider_efforts()


def _agent_files():
    if not _CODEX_AGENTS_DIR.is_dir():
        return []
    return sorted(_CODEX_AGENTS_DIR.glob("*.toml"))


AGENT_FILES = _agent_files()

if not AGENT_FILES:
    raise RuntimeError(
        f"test_agents.py: no codex agent files found under {_CODEX_AGENTS_DIR}. "
        f"The session-scoped built_dist fixture should have populated it. "
        f"Run `python3 -m agent_notes build` manually if running outside pytest."
    )


@pytest.fixture(scope="module", autouse=True)
def require_built_dist(built_dist):
    """Ensure the build has run before collecting agent files."""
    pass


# --- lead.toml must NOT exist ---

def test_lead_toml_not_present():
    """lead agent is excluded from codex (codex_exclude: true)."""
    assert not (_CODEX_AGENTS_DIR / "lead.toml").exists(), (
        "lead.toml must not exist — lead is codex_exclude: true"
    )


# --- Parametrized per-file tests ---

@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_file_non_empty(agent_file):
    assert agent_file.stat().st_size > 0, f"{agent_file.name} is empty"


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_file_is_valid_toml(agent_file):
    raw = agent_file.read_bytes()
    try:
        tomllib.loads(raw.decode())
    except Exception as exc:
        pytest.fail(f"{agent_file.name} is not valid TOML: {exc}")


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_has_name(agent_file):
    data = tomllib.loads(agent_file.read_bytes().decode())
    assert data.get("name", "").strip(), f"{agent_file.name} missing non-empty 'name'"


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_has_description(agent_file):
    data = tomllib.loads(agent_file.read_bytes().decode())
    assert data.get("description", "").strip(), f"{agent_file.name} missing non-empty 'description'"


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_has_developer_instructions(agent_file):
    data = tomllib.loads(agent_file.read_bytes().decode())
    assert data.get("developer_instructions", "").strip(), (
        f"{agent_file.name} missing non-empty 'developer_instructions'"
    )


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_model_contains_gpt_if_present(agent_file):
    data = tomllib.loads(agent_file.read_bytes().decode())
    model = data.get("model")
    if model is not None:
        assert "gpt" in model.lower(), (
            f"{agent_file.name}: model '{model}' does not contain 'gpt' — "
            f"codex only supports openai models"
        )


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_model_reasoning_effort_valid_if_present(agent_file):
    data = tomllib.loads(agent_file.read_bytes().decode())
    effort = data.get("model_reasoning_effort")
    if effort is not None:
        assert effort in _VALID_EFFORT_VALUES, (
            f"{agent_file.name}: model_reasoning_effort '{effort}' not in {_VALID_EFFORT_VALUES}"
        )


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_sandbox_mode_valid_if_present(agent_file):
    data = tomllib.loads(agent_file.read_bytes().decode())
    sandbox = data.get("sandbox_mode")
    if sandbox is not None:
        assert sandbox in _VALID_SANDBOX_MODES, (
            f"{agent_file.name}: sandbox_mode '{sandbox}' not in {_VALID_SANDBOX_MODES}"
        )


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_developer_instructions_no_memory_section(agent_file):
    data = tomllib.loads(agent_file.read_bytes().decode())
    instructions = data.get("developer_instructions", "")
    for line in instructions.split("\n"):
        stripped = line.strip()
        assert not stripped.startswith("## Memory"), (
            f"{agent_file.name}: developer_instructions contains a '## Memory' section "
            f"(should have been stripped by post_process)"
        )


@pytest.mark.parametrize("agent_file", AGENT_FILES, ids=[f.name for f in AGENT_FILES])
def test_agent_developer_instructions_no_cost_reporting_section(agent_file):
    data = tomllib.loads(agent_file.read_bytes().decode())
    instructions = data.get("developer_instructions", "")
    for line in instructions.split("\n"):
        stripped = line.strip()
        assert not stripped.startswith("## Cost reporting"), (
            f"{agent_file.name}: developer_instructions contains a '## Cost reporting' section "
            f"(should have been stripped by post_process)"
        )


# --- Render-path gate ---

class TestEffortRenderPath:
    """The parametrized checks above read already-built files in dist/, which a
    user pin never touches at test time — so they are structurally incapable of
    catching a pin that renders a value Codex CLI rejects.

    `agent-notes config role-effort --cli codex worker <value>` validates only
    against the openai PROVIDER vocabulary, which accepts `none` (and `max`)
    because the OpenAI API does. Codex CLI's `model_reasoning_effort` accepts
    neither. This gate therefore runs the real render for every value the
    command will accept.
    """

    @staticmethod
    def _agent_config():
        from agent_notes.services.rendering import load_agents_config

        return load_agents_config()["coder"]

    @staticmethod
    def _render_effort(pinned_effort):
        from agent_notes.domain.state import BackendState, ScopeState
        from agent_notes.registries.cli_registry import load_registry
        from agent_notes.services.rendering import _resolve_effort, _resolve_model_str

        backend = load_registry().get("codex")
        agent_config = TestEffortRenderPath._agent_config()
        scope_state = ScopeState(
            clis={"codex": BackendState(role_efforts={"worker": pinned_effort})}
        )

        model_str, model_registry = _resolve_model_str(
            "coder", agent_config, backend, scope_state, None, {}
        )
        return _resolve_effort(
            "coder", agent_config, backend, scope_state, {}, model_str, model_registry
        ), agent_config

    @pytest.mark.parametrize("pinned_effort", _OPENAI_PROVIDER_EFFORTS)
    def test_pinned_effort_renders_a_codex_valid_value(self, pinned_effort):
        from agent_notes.data.templates.frontmatter import codex as codex_template

        resolved_effort, agent_config = self._render_effort(pinned_effort)
        _filename, content = codex_template.emit_file(
            {
                "agent_name": "coder",
                "agent_config": agent_config,
                "model_str": "gpt-5.6-terra",
                "resolved_effort": resolved_effort,
                "backend_name": "codex",
                "backend": None,
            },
            "body",
        )
        emitted = tomllib.loads(content)["model_reasoning_effort"]
        assert emitted in _VALID_EFFORT_VALUES, (
            f"role-effort pin '{pinned_effort}' rendered model_reasoning_effort "
            f"'{emitted}', which Codex CLI rejects (accepts: {_VALID_EFFORT_VALUES})"
        )
