"""Tests for skill registry."""

import pytest
from pathlib import Path
from agent_notes.registries.skill_registry import load_skill_registry, _parse_skill_frontmatter


class TestSkillRegistry:
    def test_load_skills_from_directory(self, tmp_path):
        """Should load skills from skills directory."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        
        # Create skill 1
        skill1_dir = skills_dir / "rails-models"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text("Database model helpers")
        
        # Create skill 2 with frontmatter
        skill2_dir = skills_dir / "docker-compose"
        skill2_dir.mkdir()
        (skill2_dir / "SKILL.md").write_text("""---
group: devops
description: Docker compose utilities
---

Docker compose helpers and utilities.""")
        
        registry = load_skill_registry(skills_dir)
        
        assert len(registry.all()) == 2
        assert sorted(registry.names()) == ["docker-compose", "rails-models"]
        
        rails_skill = registry.get("rails-models")
        assert rails_skill.name == "rails-models"
        assert rails_skill.description == "Database model helpers"
        assert rails_skill.group is None
        assert rails_skill.path == skill1_dir
        
        docker_skill = registry.get("docker-compose")
        assert docker_skill.name == "docker-compose"
        assert docker_skill.description == "Docker compose utilities"
        assert docker_skill.group == "devops"
    
    def test_by_group(self, tmp_path):
        """Should group skills by their group field."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        
        # DevOps skills
        for name in ["docker", "kubernetes"]:
            skill_dir = skills_dir / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"""---
group: devops
---
{name} utilities""")
        
        # Rails skills
        for name in ["rails-models", "rails-controllers"]:
            skill_dir = skills_dir / name
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"""---
group: rails
---
{name} utilities""")
        
        # Ungrouped skill
        skill_dir = skills_dir / "generic"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("Generic utility")
        
        registry = load_skill_registry(skills_dir)
        groups = registry.by_group()
        
        assert "devops" in groups
        assert len(groups["devops"]) == 2
        assert sorted([s.name for s in groups["devops"]]) == ["docker", "kubernetes"]
        
        assert "rails" in groups
        assert len(groups["rails"]) == 2
        assert sorted([s.name for s in groups["rails"]]) == ["rails-controllers", "rails-models"]
        
        assert "uncategorized" in groups
        assert len(groups["uncategorized"]) == 1
        assert groups["uncategorized"][0].name == "generic"
    
    def test_empty_directory(self, tmp_path):
        """Should handle empty skills directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        registry = load_skill_registry(empty_dir)
        assert len(registry.all()) == 0
    
    def test_missing_directory(self, tmp_path):
        """Should handle missing skills directory."""
        missing_dir = tmp_path / "nonexistent"
        
        registry = load_skill_registry(missing_dir)
        assert len(registry.all()) == 0
    
    def test_directory_without_skill_md(self, tmp_path):
        """Should ignore directories without SKILL.md."""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        
        # Valid skill
        skill1_dir = skills_dir / "valid"
        skill1_dir.mkdir()
        (skill1_dir / "SKILL.md").write_text("Valid skill")
        
        # Directory without SKILL.md
        skill2_dir = skills_dir / "invalid"
        skill2_dir.mkdir()
        (skill2_dir / "other.txt").write_text("Not a skill")
        
        registry = load_skill_registry(skills_dir)
        
        assert len(registry.all()) == 1
        assert registry.all()[0].name == "valid"
    
    def test_get_unknown_skill_raises_keyerror(self, tmp_path):
        """Should raise KeyError for unknown skill."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        registry = load_skill_registry(empty_dir)
        
        with pytest.raises(KeyError, match="Skill 'unknown' not found"):
            registry.get("unknown")


class TestParsSkillFrontmatter:
    def test_parse_with_frontmatter(self, tmp_path):
        """Should parse YAML frontmatter correctly."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("""---
group: devops
description: Docker utilities
---

# Docker Skill

This is a Docker skill with frontmatter.""")
        
        description, group = _parse_skill_frontmatter(skill_md)
        assert description == "Docker utilities"
        assert group == "devops"
    
    def test_parse_without_frontmatter(self, tmp_path):
        """Should use first line as description when no frontmatter."""
        skill_md = tmp_path / "SKILL.md" 
        skill_md.write_text("""# Docker Skill

This is a Docker skill without frontmatter.
Second line should be ignored.""")
        
        description, group = _parse_skill_frontmatter(skill_md)
        assert description == "# Docker Skill"
        assert group is None
    
    def test_parse_frontmatter_without_description(self, tmp_path):
        """Should use first content line when frontmatter lacks description."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("""---
group: devops
---

First content line
Second content line""")
        
        description, group = _parse_skill_frontmatter(skill_md)
        assert description == "First content line"
        assert group == "devops"
    
    def test_parse_missing_file(self, tmp_path):
        """Should handle missing SKILL.md file."""
        missing_file = tmp_path / "nonexistent" / "SKILL.md"
        
        description, group = _parse_skill_frontmatter(missing_file)
        assert description == "nonexistent"  # parent dir name
        assert group is None