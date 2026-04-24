"""Test expand_includes function."""
import pytest
from pathlib import Path

from agent_notes.services.rendering import expand_includes


class TestExpandIncludes:
    """Test expand_includes function."""
    
    def test_single_include_directive(self, tmp_path):
        """Single include directive should be substituted with file content."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()
        
        # Create a shared file
        (shared_dir / "foo.md").write_text("This is foo content")
        
        text = "Before\n<!-- include: foo -->\nAfter"
        result = expand_includes(text, shared_dir)
        
        assert result == "Before\nThis is foo content\nAfter"
    
    def test_multiple_include_directives(self, tmp_path):
        """Multiple include directives should all be substituted."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()
        
        # Create shared files
        (shared_dir / "header.md").write_text("# Header Content")
        (shared_dir / "footer.md").write_text("Footer text")
        
        text = "Start\n<!-- include: header -->\nMiddle\n<!-- include: footer -->\nEnd"
        result = expand_includes(text, shared_dir)
        
        assert result == "Start\n# Header Content\nMiddle\nFooter text\nEnd"
    
    def test_no_include_directives(self, tmp_path):
        """Text with no include directives should be unchanged."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()
        
        text = "This is just regular text\nwith no includes"
        result = expand_includes(text, shared_dir)
        
        assert result == text
    
    def test_shared_dir_not_exists(self, tmp_path):
        """If shared_dir doesn't exist, text should be unchanged."""
        shared_dir = tmp_path / "nonexistent"
        
        text = "Text with\n<!-- include: foo -->\ndirective"
        result = expand_includes(text, shared_dir)
        
        assert result == text
    
    def test_missing_include_file_raises_error(self, tmp_path):
        """Include directive for missing file should raise ValueError."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()
        
        text = "Text with\n<!-- include: missing -->\ndirective"
        
        with pytest.raises(ValueError, match=r"Unknown include: missing \(file not found: .*/missing\.md\)"):
            expand_includes(text, shared_dir)
    
    def test_include_with_surrounding_whitespace(self, tmp_path):
        """Include directive with whitespace should still be matched."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()
        
        (shared_dir / "test.md").write_text("Test content")
        
        text = "Before\n   <!-- include: test -->   \nAfter"
        result = expand_includes(text, shared_dir)
        
        assert result == "Before\nTest content\nAfter"
    
    def test_include_in_code_fence_still_processed(self, tmp_path):
        """Include directive inside code fence should still be processed (v1 simplicity)."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()
        
        (shared_dir / "example.md").write_text("Example code")
        
        text = "```\n<!-- include: example -->\n```"
        result = expand_includes(text, shared_dir)
        
        assert result == "```\nExample code\n```"
    
    def test_typo_in_directive_not_matched(self, tmp_path):
        """Typo in directive (like 'includes' plural) should not be matched."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()
        
        (shared_dir / "foo.md").write_text("Foo content")
        
        text = "Before\n<!-- includes: foo -->\nAfter"
        result = expand_includes(text, shared_dir)
        
        # Should be unchanged since directive has typo
        assert result == text
    
    def test_strips_trailing_newline(self, tmp_path):
        """Included content should have trailing newline stripped to avoid double blanks."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()
        
        # Create file with trailing newline
        (shared_dir / "content.md").write_text("Content with newline\n")
        
        text = "Before\n<!-- include: content -->\nAfter"
        result = expand_includes(text, shared_dir)
        
        assert result == "Before\nContent with newline\nAfter"
    
    def test_valid_include_name_patterns(self, tmp_path):
        """Valid include names should work (letters, numbers, underscore, dash)."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()
        
        # Test various valid name patterns
        (shared_dir / "simple.md").write_text("simple")
        (shared_dir / "with-dash.md").write_text("with-dash")
        (shared_dir / "with_underscore.md").write_text("with_underscore") 
        (shared_dir / "123numbers.md").write_text("123numbers")
        (shared_dir / "mix3d-n4m3s_123.md").write_text("mixed")
        
        text = """<!-- include: simple -->
<!-- include: with-dash -->
<!-- include: with_underscore -->
<!-- include: 123numbers -->
<!-- include: mix3d-n4m3s_123 -->"""
        
        result = expand_includes(text, shared_dir)
        expected = "simple\nwith-dash\nwith_underscore\n123numbers\nmixed"
        
        assert result == expected