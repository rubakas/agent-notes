"""Test role_registry module."""

import pytest
import yaml
from pathlib import Path

from agent_notes.role_registry import (
    load_role_registry,
    Role,
    RoleRegistry,
    default_registry
)


class TestRole:
    """Test Role class."""
    
    def test_role_creation(self):
        """Test Role dataclass creation."""
        role = Role(
            name="worker",
            label="Worker",
            description="Does work",
            typical_class="sonnet",
            color="blue"
        )
        
        assert role.name == "worker"
        assert role.label == "Worker"
        assert role.description == "Does work"
        assert role.typical_class == "sonnet"
        assert role.color == "blue"
    
    def test_role_frozen(self):
        """Test that Role is frozen."""
        role = Role(
            name="worker",
            label="Worker", 
            description="Does work",
            typical_class="sonnet"
        )
        
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            role.name = "new-name"


class TestRoleRegistry:
    """Test RoleRegistry class."""
    
    def test_registry_operations(self):
        """Test basic registry operations."""
        role1 = Role(
            name="orchestrator",
            label="Orchestrator",
            description="Plans tasks",
            typical_class="opus",
            color="purple"
        )
        
        role2 = Role(
            name="worker",
            label="Worker",
            description="Does work",
            typical_class="sonnet",
            color="blue"
        )
        
        registry = RoleRegistry([role1, role2])
        
        # Test all() - returns sorted by name
        roles = registry.all()
        assert len(roles) == 2
        assert roles[0].name == "orchestrator"
        assert roles[1].name == "worker"
        
        # Test get()
        assert registry.get("orchestrator") == role1
        assert registry.get("worker") == role2
        
        # Test get() with unknown role
        with pytest.raises(KeyError, match="Role 'unknown' not found"):
            registry.get("unknown")
        
        # Test names()
        assert registry.names() == ["orchestrator", "worker"]


class TestLoadRoleRegistry:
    """Test load_role_registry function."""
    
    def test_load_default_registry(self):
        """Test loading the default registry returns 4 roles."""
        registry = load_role_registry()
        
        # Should have 4 roles
        assert len(registry.all()) == 4
        names = registry.names()
        assert "orchestrator" in names
        assert "reasoner" in names 
        assert "worker" in names
        assert "scout" in names
    
    def test_get_specific_roles(self):
        """Test getting specific roles from default registry."""
        registry = load_role_registry()
        
        # Test worker role
        worker = registry.get("worker")
        assert worker.label == "Worker"
        assert worker.typical_class == "sonnet"
        assert worker.color == "blue"
        
        # Test orchestrator role
        orchestrator = registry.get("orchestrator")
        assert orchestrator.label == "Orchestrator"
        assert orchestrator.typical_class == "opus"
        assert orchestrator.color == "purple"
        
        # Test scout role
        scout = registry.get("scout")
        assert scout.typical_class == "haiku"
        assert scout.color == "cyan"
        
        # Test reasoner role
        reasoner = registry.get("reasoner")
        assert reasoner.typical_class == "opus"
        assert reasoner.color == "red"
    
    def test_get_unknown_role_raises_error(self):
        """Test that getting unknown role raises KeyError."""
        registry = load_role_registry()
        
        with pytest.raises(KeyError, match="Role 'unknown' not found"):
            registry.get("unknown")
    
    def test_names_sorted(self):
        """Test that names() returns sorted list."""
        registry = load_role_registry()
        names = registry.names()
        
        # Should be sorted alphabetically
        assert names == sorted(names)
        expected = ["orchestrator", "reasoner", "scout", "worker"]
        assert names == expected
    
    def test_load_custom_directory(self, tmp_path):
        """Test loading from custom directory."""
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        
        # Create test role YAML
        role_data = {
            "name": "test-role",
            "label": "Test Role",
            "description": "A test role",
            "typical_class": "opus",
            "color": "green"
        }
        
        yaml_file = roles_dir / "test-role.yaml"
        yaml_file.write_text(yaml.dump(role_data))
        
        registry = load_role_registry(roles_dir)
        assert len(registry.all()) == 1
        
        role = registry.get("test-role")
        assert role.name == "test-role"
        assert role.label == "Test Role"
        assert role.typical_class == "opus"
        assert role.color == "green"
    
    def test_missing_directory_error(self, tmp_path):
        """Test error when roles directory doesn't exist."""
        nonexistent_dir = tmp_path / "nonexistent"
        
        with pytest.raises(ValueError, match="Roles directory not found"):
            load_role_registry(nonexistent_dir)
    
    def test_missing_typical_class_error(self, tmp_path):
        """Test error when typical_class field is missing."""
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        
        # YAML missing 'typical_class' field
        incomplete_role = {
            "name": "test-role",
            "label": "Test Role",
            "description": "A test role"
            # missing 'typical_class'
        }
        
        yaml_file = roles_dir / "incomplete.yaml"
        yaml_file.write_text(yaml.dump(incomplete_role))
        
        with pytest.raises(ValueError, match="Missing field 'typical_class' in incomplete.yaml"):
            load_role_registry(roles_dir)
    
    def test_malformed_yaml_error(self, tmp_path):
        """Test error when YAML file is malformed."""
        roles_dir = tmp_path / "roles"
        roles_dir.mkdir()
        
        # Create malformed YAML
        yaml_file = roles_dir / "bad.yaml"
        yaml_file.write_text("invalid: yaml: content: [\n")
        
        with pytest.raises(ValueError, match="Invalid YAML in bad.yaml"):
            load_role_registry(roles_dir)


class TestDefaultRegistry:
    """Test default_registry function."""
    
    def test_default_registry_cached(self):
        """Test that default_registry returns cached instance."""
        registry1 = default_registry()
        registry2 = default_registry()
        
        # Should be the same instance due to caching
        assert registry1 is registry2