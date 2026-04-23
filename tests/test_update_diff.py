"""Test update_diff module v2."""
import pytest
from agent_notes.update_diff import diff_states, diff_scope_states, render_diff_report, filter_diff, ComponentDiff, StateDiff
from agent_notes.state import State, ScopeState, BackendState, InstalledItem


def create_backend_state(agents=None, skills=None, rules=None, commands=None, config=None, settings=None, role_models=None):
    """Helper to create BackendState with v2 structure."""
    backend = BackendState()
    
    if role_models:
        backend.role_models = role_models
    
    # Add components to installed dict
    if agents:
        backend.installed["agents"] = agents
    if skills:
        backend.installed["skills"] = skills  
    if rules:
        backend.installed["rules"] = rules
    if commands:
        backend.installed["commands"] = commands
    if config:
        backend.installed["config"] = config
    if settings:
        backend.installed["settings"] = settings
        
    return backend


def create_global_state(source_commit="abc123", clis=None):
    """Helper to create State with global install."""
    scope_state = ScopeState(
        installed_at="2026-04-22T13:05:00Z",
        updated_at="2026-04-22T13:05:00Z",
        mode="symlink",
        clis=clis or {}
    )
    return State(
        source_commit=source_commit,
        global_install=scope_state
    )


class TestDiffStates:
    """Test diff_states function."""
    
    def test_diff_none_old_state_marks_everything_added(self):
        """Should mark everything as added when old state is None."""
        # Create a new state with some content
        new_state = create_global_state(
            
            source_commit="abc123",
            clis={
                "claude": create_backend_state(
                    agents={"coder.md": InstalledItem("sha1", "/target/coder.md", "symlink")},
                    skills={"rails": InstalledItem("sha2", "/target/rails", "symlink")}
                )
            }
        )
        
        diff = diff_states(None, new_state)
        
        assert diff.old_version is None
        assert diff.new_version == "1.0.2"
        assert diff.old_commit is None
        assert diff.new_commit == "abc123"
        assert diff.added_backends == ["claude"]
        assert diff.removed_backends == []
        
        # Find agents component
        agents_comp = next((c for c in diff.components if c.component == "agents"), None)
        assert agents_comp is not None
        assert agents_comp.added == ["coder.md"]
        assert agents_comp.removed == []
        assert agents_comp.modified == []
        assert agents_comp.unchanged == []
        
        # Find skills component
        skills_comp = next((c for c in diff.components if c.component == "skills"), None)
        assert skills_comp is not None
        assert skills_comp.added == ["rails"]
    
    def test_diff_equal_states_no_changes(self):
        """Should show no changes when states are equal."""
        state = create_global_state(
            
            source_commit="abc123",
            clis={
                "claude": create_backend_state(
                    agents={"coder.md": InstalledItem("sha1", "/target/coder.md", "symlink")}
                )
            }
        )
        
        diff = diff_states(state, state)
        
        assert diff.old_version == "1.0.2"
        assert diff.new_version == "1.0.2"
        assert diff.old_commit == "abc123"
        assert diff.new_commit == "abc123"
        assert diff.added_backends == []
        assert diff.removed_backends == []
        assert diff.has_changes() == False
        assert diff.total_changes() == 0
        
        # Should still show components for completeness
        agents_comp = next((c for c in diff.components if c.component == "agents"), None)
        assert agents_comp is not None
        assert agents_comp.added == []
        assert agents_comp.removed == []
        assert agents_comp.modified == []
        assert agents_comp.unchanged == ["coder.md"]
    
    def test_diff_added_agent(self):
        """Should detect added agent."""
        old_state = create_global_state(
            
            source_commit="abc123",
            clis={
                "claude": create_backend_state(
                    agents={"coder.md": InstalledItem("sha1", "/target/coder.md", "symlink")}
                )
            }
        )
        
        new_state = create_global_state(
            
            source_commit="abc123",
            clis={
                "claude": create_backend_state(
                    agents={
                        "coder.md": InstalledItem("sha1", "/target/coder.md", "symlink"),
                        "reviewer.md": InstalledItem("sha2", "/target/reviewer.md", "symlink")
                    }
                )
            }
        )
        
        diff = diff_states(old_state, new_state)
        
        assert diff.added_backends == []
        assert diff.removed_backends == []
        assert diff.has_changes() == True
        
        agents_comp = next((c for c in diff.components if c.component == "agents"), None)
        assert agents_comp is not None
        assert agents_comp.added == ["reviewer.md"]
        assert agents_comp.removed == []
        assert agents_comp.modified == []
        assert agents_comp.unchanged == ["coder.md"]
    
    def test_diff_removed_agent(self):
        """Should detect removed agent."""
        old_state = create_global_state(
            
            source_commit="abc123",
            clis={
                "claude": create_backend_state(
                    agents={
                        "coder.md": InstalledItem("sha1", "/target/coder.md", "symlink"),
                        "reviewer.md": InstalledItem("sha2", "/target/reviewer.md", "symlink")
                    }
                )
            }
        )
        
        new_state = create_global_state(
            
            source_commit="abc123",
            clis={
                "claude": create_backend_state(
                    agents={"coder.md": InstalledItem("sha1", "/target/coder.md", "symlink")}
                )
            }
        )
        
        diff = diff_states(old_state, new_state)
        
        assert diff.added_backends == []
        assert diff.removed_backends == []
        assert diff.has_changes() == True
        
        agents_comp = next((c for c in diff.components if c.component == "agents"), None)
        assert agents_comp is not None
        assert agents_comp.added == []
        assert agents_comp.removed == ["reviewer.md"]
        assert agents_comp.modified == []
        assert agents_comp.unchanged == ["coder.md"]
    
    def test_diff_modified_agent_sha(self):
        """Should detect agent with changed sha."""
        old_state = create_global_state(
            
            source_commit="abc123",
            clis={
                "claude": create_backend_state(
                    agents={"coder.md": InstalledItem("sha1", "/target/coder.md", "symlink")}
                )
            }
        )
        
        new_state = create_global_state(
              
            source_commit="abc123",
            clis={
                "claude": create_backend_state(
                    agents={"coder.md": InstalledItem("sha2", "/target/coder.md", "symlink")}  # different sha
                )
            }
        )
        
        diff = diff_states(old_state, new_state)
        
        assert diff.added_backends == []
        assert diff.removed_backends == []
        assert diff.has_changes() == True
        
        agents_comp = next((c for c in diff.components if c.component == "agents"), None)
        assert agents_comp is not None
        assert agents_comp.added == []
        assert agents_comp.removed == []
        assert agents_comp.modified == ["coder.md"]
        assert agents_comp.unchanged == []
    
    def test_diff_unchanged_items_not_in_modified(self):
        """Should not mark unchanged items as modified."""
        state = create_global_state(
            
            source_commit="abc123",
            clis={
                "claude": create_backend_state(
                    agents={"coder.md": InstalledItem("same_sha", "/target/coder.md", "symlink")}
                )
            }
        )
        
        diff = diff_states(state, state)
        
        agents_comp = next((c for c in diff.components if c.component == "agents"), None)
        assert agents_comp is not None
        assert agents_comp.modified == []
        assert agents_comp.unchanged == ["coder.md"]
    
    def test_diff_new_backend(self):
        """Should detect new backend entirely."""
        old_state = create_global_state(
            
            source_commit="abc123",
            clis={
                "claude": create_backend_state(
                    agents={"coder.md": InstalledItem("sha1", "/target/coder.md", "symlink")}
                )
            }
        )
        
        new_state = create_global_state(
            
            source_commit="abc123", 
            clis={
                "claude": create_backend_state(
                    agents={"coder.md": InstalledItem("sha1", "/target/coder.md", "symlink")}
                ),
                "opencode": create_backend_state(
                    agents={"lead.md": InstalledItem("sha2", "/target/lead.md", "symlink")}
                )
            }
        )
        
        diff = diff_states(old_state, new_state)
        
        assert diff.added_backends == ["opencode"]
        assert diff.removed_backends == []
        assert diff.has_changes() == True
        
        # Should have components for both backends
        claude_comp = next((c for c in diff.components if c.backend == "claude" and c.component == "agents"), None)
        assert claude_comp is not None
        assert claude_comp.unchanged == ["coder.md"]
        
        opencode_comp = next((c for c in diff.components if c.backend == "opencode" and c.component == "agents"), None)
        assert opencode_comp is not None
        assert opencode_comp.added == ["lead.md"]
    
    def test_diff_removed_backend(self):
        """Should detect removed backend."""
        old_state = create_global_state(
            
            source_commit="abc123",
            clis={
                "claude": create_backend_state(
                    agents={"coder.md": InstalledItem("sha1", "/target/coder.md", "symlink")}
                ),
                "opencode": create_backend_state(
                    agents={"lead.md": InstalledItem("sha2", "/target/lead.md", "symlink")}
                )
            }
        )
        
        new_state = create_global_state(
            
            source_commit="abc123",
            clis={
                "claude": create_backend_state(
                    agents={"coder.md": InstalledItem("sha1", "/target/coder.md", "symlink")}
                )
            }
        )
        
        diff = diff_states(old_state, new_state)
        
        assert diff.added_backends == []
        assert diff.removed_backends == ["opencode"]
        assert diff.has_changes() == True


class TestDiffScopeStates:
    """Test diff_scope_states function directly."""
    
    def test_diff_scope_states_basic(self):
        """Should diff two scope states correctly."""
        old_scope = ScopeState(
            mode="symlink",
            clis={
                "claude": create_backend_state(
                    agents={"coder.md": InstalledItem("sha1", "/target/coder.md", "symlink")}
                )
            }
        )
        
        new_scope = ScopeState(
            mode="symlink",
            clis={
                "claude": create_backend_state(
                    agents={
                        "coder.md": InstalledItem("sha1", "/target/coder.md", "symlink"),
                        "reviewer.md": InstalledItem("sha2", "/target/reviewer.md", "symlink")
                    }
                )
            }
        )
        
        diff = diff_scope_states(old_scope, new_scope)
        
        assert diff.added_backends == []
        assert diff.removed_backends == []
        assert diff.has_changes() == True
        
        agents_comp = next((c for c in diff.components if c.component == "agents"), None)
        assert agents_comp is not None
        assert agents_comp.added == ["reviewer.md"]
        assert agents_comp.unchanged == ["coder.md"]


class TestFilterDiff:
    """Test filter_diff function."""
    
    def test_filter_keeps_only_agents(self):
        """Should keep only agent components when filtering."""
        diff = StateDiff(
            old_version="1.0.0",
            new_version="1.1.0",
            old_commit="abc",
            new_commit="def",
            added_backends=[],
            removed_backends=[],
            components=[
                ComponentDiff("claude", "agents", added=["coder.md"]),
                ComponentDiff("claude", "skills", added=["rails"]),
                ComponentDiff("claude", "rules", added=["style.md"])
            ]
        )
        
        filtered = filter_diff(diff, only=["agents"])
        
        assert len(filtered.components) == 1
        assert filtered.components[0].component == "agents"
        assert filtered.components[0].added == ["coder.md"]
    
    def test_filter_none_returns_unchanged(self):
        """Should return unchanged diff when only=None."""
        diff = StateDiff(
            old_version="1.0.0",
            new_version="1.1.0",
            old_commit="abc", 
            new_commit="def",
            added_backends=[],
            removed_backends=[],
            components=[
                ComponentDiff("claude", "agents", added=["coder.md"]),
                ComponentDiff("claude", "skills", added=["rails"])
            ]
        )
        
        filtered = filter_diff(diff, only=None)
        
        assert filtered is diff  # Should return same object
        assert len(filtered.components) == 2


class TestRenderDiffReport:
    """Test render_diff_report function."""
    
    def test_render_no_changes(self):
        """Should render properly when no changes."""
        diff = StateDiff(
            old_version="1.0.0",
            new_version="1.1.0",
            old_commit="abc123",
            new_commit="abc123",
            added_backends=[],
            removed_backends=[],
            components=[]
        )
        
        report = render_diff_report(diff, use_color=False)
        
        assert "No changes" in report
        # Note: the render might not include version when no changes
    
    def test_render_with_changes(self):
        """Should render changes properly."""
        diff = StateDiff(
            old_version="1.0.0",
            new_version="1.1.0",
            old_commit="abc123", 
            new_commit="def456",
            added_backends=["opencode"],
            removed_backends=[],
            components=[
                ComponentDiff("claude", "agents", added=["coder.md"], modified=["reviewer.md"], unchanged=["lead.md"]),
                ComponentDiff("opencode", "agents", added=["explorer.md"])
            ]
        )
        
        report = render_diff_report(diff, use_color=False)
        
        assert "abc123 -> def456" in report
        assert "+ coder.md" in report
        assert "+ reviewer.md" in report or "~ reviewer.md" in report  # Could be either format
        assert "+ explorer.md" in report
        assert "opencode" in report
    
    def test_render_no_color(self):
        """Should render without color codes."""
        diff = StateDiff(
            old_version="1.0.0",
            new_version="1.1.0",
            old_commit="abc123",
            new_commit="def456", 
            added_backends=[],
            removed_backends=[],
            components=[
                ComponentDiff("claude", "agents", added=["coder.md"])
            ]
        )
        
        report = render_diff_report(diff, use_color=False)
        
        # Should not contain ANSI color codes
        assert "\033[" not in report
        assert "+ coder.md" in report
    
    def test_render_initial_install(self):
        """Should render initial install scenario properly.""" 
        diff = StateDiff(
            old_version=None,
            new_version="1.1.0",
            old_commit=None,
            new_commit="abc123",
            added_backends=["claude"],
            removed_backends=[],
            components=[
                ComponentDiff("claude", "agents", added=["coder.md", "lead.md"])
            ]
        )
        
        report = render_diff_report(diff, use_color=False)
        
        assert "initial install" in report.lower()
        assert "claude" in report
        assert "+ coder.md" in report
        assert "+ lead.md" in report


class TestStateDiffMethods:
    """Test StateDiff helper methods."""
    
    def test_state_diff_total_changes(self):
        """Should count total changes correctly."""
        diff = StateDiff(
            old_version="1.0.0",
            new_version="1.1.0",
            old_commit="abc",
            new_commit="def",
            added_backends=[],
            removed_backends=[],
            components=[
                ComponentDiff("claude", "agents", added=["a.md"], removed=["b.md"], modified=["c.md"]),  # 3 changes
                ComponentDiff("claude", "skills", added=["skill1"])  # 1 change
            ]
        )
        
        assert diff.total_changes() == 4
    
    def test_component_diff_has_changes(self):
        """Should detect changes in component diffs."""
        comp_with_changes = ComponentDiff("claude", "agents", added=["coder.md"])
        comp_without_changes = ComponentDiff("claude", "agents", unchanged=["coder.md"])
        
        assert comp_with_changes.has_changes() == True
        assert comp_without_changes.has_changes() == False
    
    def test_component_diff_change_count(self):
        """Should count changes in component diffs."""
        comp = ComponentDiff("claude", "agents", added=["a.md"], removed=["b.md"], modified=["c.md"], unchanged=["d.md"])
        
        assert comp.change_count() == 3  # added + removed + modified (unchanged doesn't count)