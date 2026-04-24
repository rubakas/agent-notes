"""Test build module."""
import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

import agent_notes.build as build
import agent_notes.config as config


class TestGenerateAgentFiles:
    """Test generate_agent_files function."""
    
    def test_generates_both_formats(self, tmp_path, monkeypatch, sample_agents_yaml, sample_agent_content):
        """Should generate both Claude and OpenCode format files."""
        from agent_notes.cli_backend import CLIBackend, CLIRegistry
        from pathlib import Path
        
        # Setup temporary directories
        source_agents_dir = tmp_path / "source" / "agents"
        source_agents_dir.mkdir(parents=True)

        dist_dir = tmp_path / "dist"
        dist_claude_dir = dist_dir / "claude"
        dist_opencode_dir = dist_dir / "opencode"

        # Create source agent file
        (source_agents_dir / "test-agent.md").write_text(sample_agent_content)

        # Mock paths and registry
        monkeypatch.setattr('agent_notes.config.AGENTS_DIR', source_agents_dir)
        monkeypatch.setattr('agent_notes.installer.DIST_DIR', dist_dir)
        
        # Create mock backends
        claude = CLIBackend(
            name="claude", label="Claude Code", 
            global_home=Path("~/.claude").expanduser(), local_dir=".claude",
            layout={"agents": "agents/"}, features={"agents": True, "frontmatter": "claude"},
            global_template=None
        )
        opencode = CLIBackend(
            name="opencode", label="OpenCode",
            global_home=Path("~/.config/opencode").expanduser(), local_dir=".opencode", 
            layout={"agents": "agents/"}, features={"agents": True, "frontmatter": "opencode"},
            global_template=None, strip_memory_section=True
        )
        registry = CLIRegistry([claude, opencode])
        
        # Mock installer function to return our test paths
        def mock_dist_source_for(backend, component):
            if component == "agents":
                return dist_dir / backend.name / "agents"
            return None
        
        with patch('agent_notes.cli_backend.load_registry', return_value=registry):
            with patch('agent_notes.installer.dist_source_for', side_effect=mock_dist_source_for):
                # Parse config
                config_data = yaml.safe_load(sample_agents_yaml)
                agents_config = config_data['agents']
                tiers = config_data['tiers']

                # Generate files
                generated = build.generate_agent_files(agents_config, tiers)

                # Check files were created
                claude_file = dist_claude_dir / 'agents' / 'test-agent.md'
                opencode_file = dist_opencode_dir / 'agents' / 'test-agent.md'

                assert claude_file.exists()
                assert opencode_file.exists()

                # Check content has frontmatter
                claude_content = claude_file.read_text()
                opencode_content = opencode_file.read_text()

                assert claude_content.startswith('---')
                assert 'name: test-agent' in claude_content
                assert 'model:' in claude_content
                
                assert opencode_content.startswith('---')
                assert 'description:' in opencode_content
                assert 'mode:' in opencode_content
                assert 'model:' in opencode_content

                # Check that Memory section was stripped from OpenCode
                assert '## Memory' in claude_content
                assert '## Memory' not in opencode_content

                # Should return list of generated files
                assert len(generated) == 2
                assert claude_file in generated
                assert opencode_file in generated
        
        # Check Claude content
        claude_content = claude_file.read_text()
        assert 'name: test-agent' in claude_content
        assert 'model: sonnet' in claude_content
        assert 'tools: Read, Write' in claude_content
        assert 'memory: user' in claude_content
        assert '## Memory' in claude_content  # Should keep memory section
        
        # Check OpenCode content
        opencode_content = opencode_file.read_text()
        assert 'description: Test agent description' in opencode_content
        assert 'mode: primary' in opencode_content
        assert 'model: github-copilot/claude-sonnet-4' in opencode_content
        assert 'edit: allow' in opencode_content
        assert 'bash: allow' in opencode_content
        assert 'color: blue' in opencode_content  # Color must be emitted in OpenCode frontmatter
        assert '## Memory' not in opencode_content  # Should strip memory section
    
    def test_warns_on_missing_source_file(self, tmp_path, monkeypatch, capsys):
        """Should warn when source file is missing."""
        source_agents_dir = tmp_path / "source" / "agents"
        source_agents_dir.mkdir(parents=True)
        
        monkeypatch.setattr('agent_notes.config.AGENTS_DIR', source_agents_dir)
        
        agents_config = {
            'missing-agent': {
                'description': 'Missing agent',
                'role': 'worker',
                'mode': 'primary',
                'color': 'blue',
                'effort': 'medium'
            }
        }
        tiers = {'sonnet': {'claude': 'sonnet', 'opencode': 'github-copilot/claude-sonnet-4'}}
        
        generated = build.generate_agent_files(agents_config, tiers)
        
        captured = capsys.readouterr()
        assert "Warning: Missing source file" in captured.out
        assert "missing-agent.md" in captured.out
        assert generated == []


class TestGenerateAgentFilesWithState:
    """Test generate_agent_files with state-driven model resolution."""
    
    def test_uses_state_role_models(self, tmp_path, monkeypatch, sample_agent_content):
        """Should use state role_models when available."""
        from agent_notes.cli_backend import CLIBackend, CLIRegistry
        from agent_notes.state import State, ScopeState, BackendState
        from agent_notes.model_registry import Model, ModelRegistry
        from pathlib import Path
        
        # Setup source structure
        source_agents_dir = tmp_path / "source" / "agents"
        source_agents_dir.mkdir(parents=True)
        (source_agents_dir / "worker-agent.md").write_text(sample_agent_content)
        
        dist_dir = tmp_path / "dist"
        
        # Mock paths
        monkeypatch.setattr('agent_notes.config.AGENTS_DIR', source_agents_dir)
        monkeypatch.setattr('agent_notes.installer.DIST_DIR', dist_dir)
        
        # Create mock backends with accepted_providers
        claude = CLIBackend(
            name="claude", label="Claude Code",
            global_home=Path("~/.claude").expanduser(), local_dir=".claude",
            layout={"agents": "agents/"}, features={"agents": True, "frontmatter": "claude"},
            global_template=None,
            accepted_providers=("anthropic",)
        )
        opencode = CLIBackend(
            name="opencode", label="OpenCode",
            global_home=Path("~/.config/opencode").expanduser(), local_dir=".opencode",
            layout={"agents": "agents/"}, features={"agents": True, "frontmatter": "opencode"},
            global_template=None, strip_memory_section=True,
            accepted_providers=("github-copilot",)
        )
        registry = CLIRegistry([claude, opencode])
        
        # Create mock model registry
        test_model = Model(
            id="claude-opus-4-7",
            label="Claude Opus 4.7",
            family="claude",
            model_class="opus",
            aliases={
                "anthropic": "claude-opus-4-7",
                "github-copilot": "github-copilot/claude-opus-4.7"
            }
        )
        model_registry = ModelRegistry([test_model])
        
        # Create state with role_models
        state = State(
            source_path="/fake/path",
            source_commit="abc123",
            global_install=ScopeState(
                installed_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
                mode="symlink",
                clis={
                    "claude": BackendState(
                        role_models={"worker": "claude-opus-4-7"}
                    ),
                    "opencode": BackendState(
                        role_models={"worker": "claude-opus-4-7"}
                    )
                }
            )
        )
        
        # Agent config with role field
        agents_config = {
            'worker-agent': {
                'description': 'Worker agent',
                'role': 'worker',   # NEW: role field
                'mode': 'primary',
                'color': 'blue',
                'effort': 'medium',
                'claude': {},
                'opencode': {}
            }
        }
        
        # Tiers (fallback - should NOT be used for this agent)
        tiers = {
            'sonnet': {
                'claude': 'sonnet',
                'opencode': 'github-copilot/claude-sonnet-4'
            }
        }
        
        def mock_dist_source_for(backend, component):
            if component == "agents":
                return dist_dir / backend.name / "agents"
            return None
        
        with patch('agent_notes.cli_backend.load_registry', return_value=registry):
            with patch('agent_notes.installer.dist_source_for', side_effect=mock_dist_source_for):
                with patch('agent_notes.model_registry.load_model_registry', return_value=model_registry):
                    # Generate with state
                    generated = build.generate_agent_files(
                        agents_config, tiers, 
                        state=state, scope='global'
                    )
        
        # Check files were created
        claude_file = dist_dir / 'claude' / 'agents' / 'worker-agent.md'
        opencode_file = dist_dir / 'opencode' / 'agents' / 'worker-agent.md'
        
        assert claude_file.exists()
        assert opencode_file.exists()
        
        # Check that state-resolved models were used (NOT the tiers models)
        claude_content = claude_file.read_text()
        opencode_content = opencode_file.read_text()
        
        # Should use opus model from state, not sonnet from tier
        assert 'model: claude-opus-4-7' in claude_content
        assert 'model: github-copilot/claude-opus-4.7' in opencode_content
        
        # Should NOT contain sonnet (the tier model)
        assert 'model: sonnet' not in claude_content
        assert 'model: github-copilot/claude-sonnet-4' not in opencode_content
    
    def test_falls_back_to_tiers_without_state(self, tmp_path, monkeypatch, sample_agent_content):
        """Should fall back to tiers when state=None."""
        from agent_notes.cli_backend import CLIBackend, CLIRegistry
        from pathlib import Path
        
        # Setup source structure
        source_agents_dir = tmp_path / "source" / "agents"
        source_agents_dir.mkdir(parents=True)
        (source_agents_dir / "test-agent.md").write_text(sample_agent_content)
        
        dist_dir = tmp_path / "dist"
        
        # Mock paths
        monkeypatch.setattr('agent_notes.config.AGENTS_DIR', source_agents_dir)
        monkeypatch.setattr('agent_notes.installer.DIST_DIR', dist_dir)
        
        # Create mock backends
        claude = CLIBackend(
            name="claude", label="Claude Code",
            global_home=Path("~/.claude").expanduser(), local_dir=".claude",
            layout={"agents": "agents/"}, features={"agents": True, "frontmatter": "claude"},
            global_template=None
        )
        registry = CLIRegistry([claude])
        
        # Agent config with role field
        agents_config = {
            'test-agent': {
                'description': 'Test agent',
                'role': 'scout',
                'tier': 'haiku',  # Fallback tier when state-driven fails
                'mode': 'primary',
                'color': 'blue',
                'effort': 'low',
                'claude': {}
            }
        }
        
        tiers = {
            'haiku': {
                'claude': 'claude-haiku-3-5'
            }
        }
        
        def mock_dist_source_for(backend, component):
            if component == "agents":
                return dist_dir / backend.name / "agents"
            return None
        
        with patch('agent_notes.cli_backend.load_registry', return_value=registry):
            with patch('agent_notes.installer.dist_source_for', side_effect=mock_dist_source_for):
                # Generate WITHOUT state (None)
                generated = build.generate_agent_files(
                    agents_config, tiers, 
                    state=None  # No state
                )
        
        # Check file was created with tier model
        claude_file = dist_dir / 'claude' / 'agents' / 'test-agent.md'
        assert claude_file.exists()
        
        claude_content = claude_file.read_text()
        assert 'model: claude-haiku-3-5' in claude_content
    
    def test_falls_back_when_role_not_in_state(self, tmp_path, monkeypatch, sample_agent_content):
        """Should fall back to tiers when role not in state.role_models."""
        from agent_notes.cli_backend import CLIBackend, CLIRegistry
        from agent_notes.state import State, ScopeState, BackendState
        from pathlib import Path
        
        # Setup source structure
        source_agents_dir = tmp_path / "source" / "agents"
        source_agents_dir.mkdir(parents=True)
        (source_agents_dir / "test-agent.md").write_text(sample_agent_content)
        
        dist_dir = tmp_path / "dist"
        
        # Mock paths
        monkeypatch.setattr('agent_notes.config.AGENTS_DIR', source_agents_dir)
        monkeypatch.setattr('agent_notes.installer.DIST_DIR', dist_dir)
        
        # Create mock backend
        claude = CLIBackend(
            name="claude", label="Claude Code",
            global_home=Path("~/.claude").expanduser(), local_dir=".claude",
            layout={"agents": "agents/"}, features={"agents": True, "frontmatter": "claude"},
            global_template=None
        )
        registry = CLIRegistry([claude])
        
        # Create state WITHOUT the 'researcher' role
        state = State(
            source_path="/fake/path",
            source_commit="abc123",
            global_install=ScopeState(
                installed_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
                mode="symlink",
                clis={
                    "claude": BackendState(
                        role_models={"worker": "claude-opus-4-7"}  # Only 'worker' role
                    )
                }
            )
        )
        
        # Agent config with role='researcher' (NOT in state)
        agents_config = {
            'test-agent': {
                'description': 'Test agent',
                'role': 'researcher',  # This role is NOT in state.role_models
                'tier': 'sonnet',  # Fallback tier when role not found in state
                'mode': 'primary',
                'color': 'blue',
                'effort': 'medium',
                'claude': {}
            }
        }
        
        tiers = {
            'sonnet': {
                'claude': 'claude-sonnet-3-5'
            }
        }
        
        def mock_dist_source_for(backend, component):
            if component == "agents":
                return dist_dir / backend.name / "agents"
            return None
        
        with patch('agent_notes.cli_backend.load_registry', return_value=registry):
            with patch('agent_notes.installer.dist_source_for', side_effect=mock_dist_source_for):
                # Generate with state (but role not found in state)
                generated = build.generate_agent_files(
                    agents_config, tiers,
                    state=state, scope='global'
                )
        
        # Check file was created with TIER model (fallback)
        claude_file = dist_dir / 'claude' / 'agents' / 'test-agent.md'
        assert claude_file.exists()
        
        claude_content = claude_file.read_text()
        # Should use tier model since role not in state
        assert 'model: claude-sonnet-3-5' in claude_content

    def test_role_class_fallback_when_no_state_and_no_tier(
        self, tmp_path, monkeypatch, sample_agent_content
    ):
        """Regression: fresh build from shipped YAMLs must work with no state
        and no legacy 'tier' field, by matching role.typical_class to a model
        whose class matches and which has an alias for the backend's providers.

        This exercises the "agent-notes build on a clean checkout" scenario —
        the one where the whole promise of 'zero Python changes to add a new
        CLI/model/role' gets tested end-to-end.
        """
        from agent_notes.cli_backend import CLIBackend, CLIRegistry
        from agent_notes.domain.model import Model
        from agent_notes.registries.model_registry import ModelRegistry
        from agent_notes.domain.role import Role
        from agent_notes.registries.role_registry import RoleRegistry
        from pathlib import Path

        # Source agent markdown
        source_agents_dir = tmp_path / "source" / "agents"
        source_agents_dir.mkdir(parents=True)
        (source_agents_dir / "test-agent.md").write_text(sample_agent_content)
        dist_dir = tmp_path / "dist"
        monkeypatch.setattr('agent_notes.config.AGENTS_DIR', source_agents_dir)
        monkeypatch.setattr('agent_notes.installer.DIST_DIR', dist_dir)

        # Backend that accepts anthropic provider
        claude = CLIBackend(
            name="claude", label="Claude Code",
            global_home=Path("~/.claude").expanduser(), local_dir=".claude",
            layout={"agents": "agents/"},
            features={"agents": True, "frontmatter": "claude"},
            global_template=None,
            accepted_providers=("anthropic",),
        )
        registry = CLIRegistry([claude])

        # Role registry with a 'worker' role that prefers sonnet class
        role_registry = RoleRegistry([
            Role(
                name="worker", label="Worker",
                description="Implements code",
                typical_class="sonnet",
                color="blue",
            ),
        ])

        # Model registry with a sonnet model that has an anthropic alias
        model_registry = ModelRegistry([
            Model(
                id="claude-sonnet-4", label="Claude Sonnet 4",
                family="claude", model_class="sonnet",
                aliases={"anthropic": "sonnet"},
            ),
        ])

        # Agent config declares ONLY role, no tier (this is the v1.1 shape)
        agents_config = {
            'test-agent': {
                'description': 'Test agent',
                'role': 'worker',
                'mode': 'primary',
                'color': 'blue',
                'effort': 'medium',
                'claude': {},
            }
        }

        def mock_dist_source_for(backend, component):
            if component == "agents":
                return dist_dir / backend.name / "agents"
            return None

        with patch('agent_notes.cli_backend.load_registry', return_value=registry), \
             patch('agent_notes.registries.model_registry.load_model_registry',
                   return_value=model_registry), \
             patch('agent_notes.registries.role_registry.load_role_registry',
                   return_value=role_registry), \
             patch('agent_notes.installer.dist_source_for', side_effect=mock_dist_source_for):
            build.generate_agent_files(
                agents_config, tiers={},  # empty tiers: this path must not be taken
                state=None,  # no state: the headline scenario
            )

        claude_file = dist_dir / 'claude' / 'agents' / 'test-agent.md'
        assert claude_file.exists(), "role-class fallback should still produce output"
        content = claude_file.read_text()
        # The model alias for the anthropic provider should be rendered.
        assert 'model: sonnet' in content, (
            f"expected role-class fallback to pick sonnet alias, got:\n{content}"
        )


class TestCopyGlobalFiles:
    """Test copy_global_files function."""
    
    def test_copies_all_global_files(self, tmp_path, monkeypatch):
        """Should copy all global files to correct locations."""
        # Setup source files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        
        (source_dir / "global-claude.md").write_text("Claude config content")
        (source_dir / "global-opencode.md").write_text("OpenCode config content")
        (source_dir / "global-copilot.md").write_text("Copilot config content")
        
        source_rules_dir = source_dir / "rules"
        source_rules_dir.mkdir()
        (source_rules_dir / "rule1.md").write_text("Rule 1")
        (source_rules_dir / "rule2.md").write_text("Rule 2")
        
        # Setup dest directories
        dist_claude_dir = tmp_path / "dist" / "cli" / "claude"
        dist_opencode_dir = tmp_path / "dist" / "cli" / "opencode"
        dist_github_dir = tmp_path / "dist" / "cli" / "github"
        dist_rules_dir = tmp_path / "dist" / "rules"
        
        # Mock paths
        monkeypatch.setattr('agent_notes.config.GLOBAL_CLAUDE_MD', source_dir / "global-claude.md")
        monkeypatch.setattr('agent_notes.config.GLOBAL_OPENCODE_MD', source_dir / "global-opencode.md")
        monkeypatch.setattr('agent_notes.config.GLOBAL_COPILOT_MD', source_dir / "global-copilot.md")
        monkeypatch.setattr('agent_notes.config.RULES_DIR', source_rules_dir)
        monkeypatch.setattr('agent_notes.config.DIST_CLAUDE_DIR', dist_claude_dir)
        monkeypatch.setattr('agent_notes.config.DIST_OPENCODE_DIR', dist_opencode_dir)
        monkeypatch.setattr('agent_notes.config.DIST_GITHUB_DIR', dist_github_dir)
        monkeypatch.setattr('agent_notes.config.DIST_RULES_DIR', dist_rules_dir)
        
        # Copy files
        copied = build.copy_global_files()
        
        # Check files were created
        claude_global = dist_claude_dir / 'CLAUDE.md'
        agents_global = dist_opencode_dir / 'AGENTS.md'
        copilot_global = dist_github_dir / 'copilot-instructions.md'
        rule1_file = dist_rules_dir / 'rule1.md'
        rule2_file = dist_rules_dir / 'rule2.md'
        
        assert claude_global.exists()
        assert agents_global.exists()
        assert copilot_global.exists()
        assert rule1_file.exists()
        assert rule2_file.exists()
        
        # Check content
        assert claude_global.read_text() == "Claude config content"
        assert agents_global.read_text() == "OpenCode config content"
        assert copilot_global.read_text() == "Copilot config content"
        assert rule1_file.read_text() == "Rule 1"
        assert rule2_file.read_text() == "Rule 2"
        
        # Check all files are in returned list
        assert len(copied) == 5
        assert claude_global in copied
        assert agents_global in copied
        assert copilot_global in copied
        assert rule1_file in copied
        assert rule2_file in copied


class TestCountLines:
    """Test count_lines function."""
    
    def test_counts_lines_correctly(self, tmp_path):
        """Should count lines in file correctly."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("line 1\nline 2\nline 3")
        
        count = build.count_lines(test_file)
        assert count == 3
    
    def test_handles_missing_file(self, tmp_path):
        """Should return 0 for missing file."""
        missing_file = tmp_path / "missing.txt"
        
        count = build.count_lines(missing_file)
        assert count == 0


class TestBuild:
    """Test build function."""
    
    def test_full_build_process(self, tmp_path, monkeypatch, capsys, sample_agents_yaml, sample_agent_content):
        """Should perform full build process."""
        from agent_notes.cli_backend import CLIBackend, CLIRegistry
        from unittest.mock import patch
        from pathlib import Path
        
        # Setup source structure
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        agents_yaml = source_dir / "agents.yaml"
        agents_yaml.write_text(sample_agents_yaml)

        source_agents_dir = source_dir / "agents"
        source_agents_dir.mkdir()
        (source_agents_dir / "test-agent.md").write_text(sample_agent_content)

        (source_dir / "global-claude.md").write_text("Claude content")
        (source_dir / "global-opencode.md").write_text("OpenCode content")
        (source_dir / "global-copilot.md").write_text("Copilot content")

        # Setup dist structure
        dist_dir = tmp_path / "dist"
        
        # Mock ROOT and paths
        monkeypatch.setattr(config, 'ROOT', tmp_path)
        monkeypatch.setattr('agent_notes.config.ROOT', tmp_path)
        monkeypatch.setattr('agent_notes.config.AGENTS_YAML', agents_yaml)
        monkeypatch.setattr('agent_notes.config.AGENTS_DIR', source_agents_dir)
        monkeypatch.setattr('agent_notes.config.GLOBAL_CLAUDE_MD', source_dir / "global-claude.md")
        monkeypatch.setattr('agent_notes.config.GLOBAL_OPENCODE_MD', source_dir / "global-opencode.md")
        monkeypatch.setattr('agent_notes.config.GLOBAL_COPILOT_MD', source_dir / "global-copilot.md")
        monkeypatch.setattr('agent_notes.config.RULES_DIR', source_dir / "rules")  # Non-existent
        monkeypatch.setattr('agent_notes.config.SCRIPTS_DIR', source_dir / "scripts")  # Non-existent
        monkeypatch.setattr('agent_notes.config.DIST_DIR', dist_dir)
        monkeypatch.setattr('agent_notes.installer.DIST_DIR', dist_dir)
        
        # Mock the old dist directories for the copy_global_files function
        monkeypatch.setattr('agent_notes.config.DIST_CLAUDE_DIR', dist_dir / "claude")
        monkeypatch.setattr('agent_notes.config.DIST_OPENCODE_DIR', dist_dir / "opencode")
        monkeypatch.setattr('agent_notes.config.DIST_GITHUB_DIR', dist_dir / "github")
        monkeypatch.setattr('agent_notes.config.DIST_RULES_DIR', dist_dir / "rules")
        monkeypatch.setattr('agent_notes.config.DIST_SCRIPTS_DIR', dist_dir / "scripts")

        # Mock find_skill_dirs to return empty list for test
        monkeypatch.setattr('agent_notes.config.find_skill_dirs', lambda: [])
        
        # Create mock backends for registry
        claude = CLIBackend(
            name="claude", label="Claude Code", 
            global_home=Path("~/.claude").expanduser(), local_dir=".claude",
            layout={"agents": "agents/"}, features={"agents": True, "frontmatter": "claude"},
            global_template=None
        )
        opencode = CLIBackend(
            name="opencode", label="OpenCode",
            global_home=Path("~/.config/opencode").expanduser(), local_dir=".opencode", 
            layout={"agents": "agents/"}, features={"agents": True, "frontmatter": "opencode"},
            global_template=None, strip_memory_section=True
        )
        registry = CLIRegistry([claude, opencode])
        
        # Mock installer function to return our test paths
        def mock_dist_source_for(backend, component):
            if component == "agents":
                return dist_dir / backend.name / "agents"
            return None
        
        with patch('agent_notes.cli_backend.load_registry', return_value=registry):
            with patch('agent_notes.installer.dist_source_for', side_effect=mock_dist_source_for):
                # Run build
                build.build()

            captured = capsys.readouterr()

            # Should have generated agent files
            claude_agent = dist_dir / "claude" / "agents" / "test-agent.md"
            opencode_agent = dist_dir / "opencode" / "agents" / "test-agent.md"
            
            assert claude_agent.exists()
            assert opencode_agent.exists()

            # Should have copied global files
            claude_global = dist_dir / "claude" / "CLAUDE.md"
            opencode_global = dist_dir / "opencode" / "AGENTS.md"
            github_global = dist_dir / "github" / "copilot-instructions.md"
            
            assert claude_global.exists()
            assert opencode_global.exists()
            assert github_global.exists()

            # Should print progress messages
            assert "Generating agent files..." in captured.out
            assert "Copying global files..." in captured.out
            assert "Generated" in captured.out
            
            # Should report file count and lines
            assert "files:" in captured.out
        
        # Check files were created
        assert (dist_dir / "claude" / "agents" / "test-agent.md").exists()
        assert (dist_dir / "opencode" / "agents" / "test-agent.md").exists()
        assert (dist_dir / "claude" / "CLAUDE.md").exists()
        assert (dist_dir / "opencode" / "AGENTS.md").exists()
        assert (dist_dir / "github" / "copilot-instructions.md").exists()
    
    def test_handles_missing_agents_yaml(self, tmp_path, monkeypatch, capsys):
        """Should handle missing agents.yaml gracefully."""
        agents_yaml = tmp_path / "nonexistent" / "agents.yaml"
        
        monkeypatch.setattr('agent_notes.config.AGENTS_YAML', agents_yaml)
        
        build.build()
        
        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "Configuration file not found" in captured.out