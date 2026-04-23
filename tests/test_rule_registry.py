"""Tests for rule registry."""

import pytest
from pathlib import Path
from agent_notes.registries.rule_registry import load_rule_registry, _extract_title_from_md


class TestRuleRegistry:
    def test_load_rules_from_directory(self, tmp_path):
        """Should load rules from rules directory."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        
        # Create rule with heading
        (rules_dir / "code-quality.md").write_text("""# Code Quality Rules

Follow these code quality guidelines...""")
        
        # Create rule without heading
        (rules_dir / "safety.md").write_text("""Always validate user input.
Never trust external data.""")
        
        registry = load_rule_registry(rules_dir)
        
        assert len(registry.all()) == 2
        assert sorted(registry.names()) == ["code-quality", "safety"]
        
        quality_rule = registry.get("code-quality")
        assert quality_rule.name == "code-quality"
        assert quality_rule.title == "Code Quality Rules"
        assert quality_rule.path == rules_dir / "code-quality.md"
        
        safety_rule = registry.get("safety")
        assert safety_rule.name == "safety"
        assert safety_rule.title == "safety"  # fallback to filename
        assert safety_rule.path == rules_dir / "safety.md"
    
    def test_empty_directory(self, tmp_path):
        """Should handle empty rules directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        registry = load_rule_registry(empty_dir)
        assert len(registry.all()) == 0
    
    def test_missing_directory(self, tmp_path):
        """Should handle missing rules directory."""
        missing_dir = tmp_path / "nonexistent"
        
        registry = load_rule_registry(missing_dir)
        assert len(registry.all()) == 0
    
    def test_ignores_non_md_files(self, tmp_path):
        """Should ignore non-.md files."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        
        # Valid rule
        (rules_dir / "valid-rule.md").write_text("# Valid Rule")
        
        # Invalid files
        (rules_dir / "not-a-rule.txt").write_text("Not a markdown file")
        (rules_dir / "config.yaml").write_text("config: value")
        
        registry = load_rule_registry(rules_dir)
        
        assert len(registry.all()) == 1
        assert registry.all()[0].name == "valid-rule"
    
    def test_sorted_by_name(self, tmp_path):
        """Should return rules sorted by name."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        
        # Create in non-alphabetical order
        (rules_dir / "zebra.md").write_text("# Zebra")
        (rules_dir / "alpha.md").write_text("# Alpha")  
        (rules_dir / "beta.md").write_text("# Beta")
        
        registry = load_rule_registry(rules_dir)
        
        assert [rule.name for rule in registry.all()] == ["alpha", "beta", "zebra"]
    
    def test_get_unknown_rule_raises_keyerror(self, tmp_path):
        """Should raise KeyError for unknown rule."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        registry = load_rule_registry(empty_dir)
        
        with pytest.raises(KeyError, match="Rule 'unknown' not found"):
            registry.get("unknown")


class TestExtractTitleFromMd:
    def test_extract_heading(self, tmp_path):
        """Should extract first # heading."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""Some intro text

# Main Heading

Some content after heading.""")
        
        title = _extract_title_from_md(md_file)
        assert title == "Main Heading"
    
    def test_extract_first_heading_only(self, tmp_path):
        """Should extract only the first heading."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""# First Heading

Some content

# Second Heading

More content""")
        
        title = _extract_title_from_md(md_file)
        assert title == "First Heading"
    
    def test_no_heading_returns_filename(self, tmp_path):
        """Should return filename when no heading found."""
        md_file = tmp_path / "test-rule.md"
        md_file.write_text("""Just some content
without any headings.""")
        
        title = _extract_title_from_md(md_file)
        assert title == "test-rule"
    
    def test_missing_file_returns_filename(self, tmp_path):
        """Should return filename stem when file doesn't exist."""
        missing_file = tmp_path / "missing-rule.md"
        
        title = _extract_title_from_md(missing_file)
        assert title == "missing-rule"
    
    def test_heading_with_extra_spaces(self, tmp_path):
        """Should handle headings with extra whitespace."""
        md_file = tmp_path / "test.md"
        md_file.write_text("""
#    Heading with Spaces   

Content follows.""")
        
        title = _extract_title_from_md(md_file)
        assert title == "Heading with Spaces"