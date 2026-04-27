"""Tests for process skills loaded from the real skill registry."""
import pytest
from agent_notes.registries.skill_registry import load_skill_registry
from agent_notes.config import SKILLS_DIR


PROCESS_SKILLS = [
    "plan-first",
    "test-driven",
    "debugging-protocol",
    "brainstorming",
    "code-review",
]


class TestProcessSkillsExist:
    """Each process skill must be present and well-formed in the real registry."""

    def setup_method(self):
        self.registry = load_skill_registry(SKILLS_DIR)

    def test_plan_first_exists(self):
        skill = self.registry.get("plan-first")
        assert skill is not None

    def test_test_driven_exists(self):
        skill = self.registry.get("test-driven")
        assert skill is not None

    def test_debugging_protocol_exists(self):
        skill = self.registry.get("debugging-protocol")
        assert skill is not None

    def test_brainstorming_exists(self):
        skill = self.registry.get("brainstorming")
        assert skill is not None

    def test_code_review_exists(self):
        skill = self.registry.get("code-review")
        assert skill is not None


class TestProcessSkillsGroup:
    """Each process skill must carry group == 'process'."""

    def setup_method(self):
        self.registry = load_skill_registry(SKILLS_DIR)

    @pytest.mark.parametrize("skill_name", PROCESS_SKILLS)
    def test_skill_has_process_group(self, skill_name):
        skill = self.registry.get(skill_name)
        assert skill.group == "process", (
            f"Expected {skill_name} to have group='process', got {skill.group!r}"
        )


class TestProcessSkillsDescription:
    """Each process skill must have a non-empty description."""

    def setup_method(self):
        self.registry = load_skill_registry(SKILLS_DIR)

    @pytest.mark.parametrize("skill_name", PROCESS_SKILLS)
    def test_skill_has_non_empty_description(self, skill_name):
        skill = self.registry.get(skill_name)
        assert skill.description and skill.description.strip(), (
            f"Expected {skill_name} to have a non-empty description"
        )


class TestByGroupContainsAllProcessSkills:
    """by_group()['process'] must contain all 5 process skills."""

    def setup_method(self):
        self.registry = load_skill_registry(SKILLS_DIR)

    def test_process_group_exists(self):
        groups = self.registry.by_group()
        assert "process" in groups

    def test_process_group_contains_all_five_skills(self):
        groups = self.registry.by_group()
        process_names = {s.name for s in groups["process"]}
        for skill_name in PROCESS_SKILLS:
            assert skill_name in process_names, (
                f"Expected '{skill_name}' in process group, got: {sorted(process_names)}"
            )


class TestExistingSkillGroupsStillPresent:
    """Pre-existing skill groups must survive the 1.2.0 addition."""

    def setup_method(self):
        self.registry = load_skill_registry(SKILLS_DIR)

    def test_rails_group_has_at_least_one_skill(self):
        groups = self.registry.by_group()
        assert "rails" in groups
        assert len(groups["rails"]) >= 1

    def test_docker_group_has_at_least_one_skill(self):
        groups = self.registry.by_group()
        assert "docker" in groups
        assert len(groups["docker"]) >= 1

    def test_git_group_has_at_least_one_skill(self):
        groups = self.registry.by_group()
        assert "git" in groups
        assert len(groups["git"]) >= 1

    def test_no_uncategorized_group(self):
        """All shipped skills must carry an explicit group — no stragglers."""
        groups = self.registry.by_group()
        assert "uncategorized" not in groups, (
            f"Found uncategorized skills: "
            f"{[s.name for s in groups.get('uncategorized', [])]}"
        )
