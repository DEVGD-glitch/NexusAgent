"""
Tests for nexus.orchestrator.skill_lifecycle.
"""

import pytest
from nexus.orchestrator.skill_lifecycle import (
    SkillStage,
    SkillCategory,
    SkillStatus,
    SkillDefinition,
    SkillLifecycleManager,
)


class TestSkillStage:
    """Test cases for SkillStage enum."""

    def test_all_stages(self):
        """All skill stages should exist."""
        assert SkillStage.DISCOVERY.value == "discovery"
        assert SkillStage.DESIGN.value == "design"
        assert SkillStage.IMPLEMENT.value == "implement"
        assert SkillStage.VALIDATE.value == "validate"
        assert SkillStage.DEPLOY.value == "deploy"


class TestSkillCategory:
    """Test cases for SkillCategory enum."""

    def test_all_categories(self):
        """All skill categories should exist."""
        assert SkillCategory.CODING.value == "coding"
        assert SkillCategory.RESEARCH.value == "research"
        assert SkillCategory.ANALYSIS.value == "analysis"
        assert SkillCategory.ORCHESTRATION.value == "orchestration"
        assert SkillCategory.SECURITY.value == "security"
        assert SkillCategory.MEMORY.value == "memory"
        assert SkillCategory.WEB.value == "web"
        assert SkillCategory.FILE.value == "file"
        assert SkillCategory.UTILITY.value == "utility"


class TestSkillStatus:
    """Test cases for SkillStatus enum."""

    def test_all_statuses(self):
        """All skill statuses should exist."""
        assert SkillStatus.DISCOVERED.value == "discovered"
        assert SkillStatus.DRAFT.value == "draft"
        assert SkillStatus.TESTING.value == "testing"
        assert SkillStatus.ACTIVE.value == "active"
        assert SkillStatus.DEPRECATED.value == "deprecated"
        assert SkillStatus.FAILED.value == "failed"


class TestSkillDefinition:
    """Test cases for SkillDefinition dataclass."""

    def test_default_creation(self):
        """SkillDefinition with defaults."""
        skill = SkillDefinition(name="Test Skill", description="A test skill")
        assert skill.name == "Test Skill"
        assert skill.description == "A test skill"
        assert skill.skill_id is not None
        assert skill.status == SkillStatus.DRAFT
        assert skill.stage == SkillStage.DISCOVERY
        assert skill.version == 1

    def test_to_dict(self):
        """Convert to dict."""
        skill = SkillDefinition(name="Test", description="Test desc")
        d = skill.to_dict()
        assert "skill_id" in d
        assert "name" in d
        assert "stage" in d
        assert d["stage"] == "discovery"


class TestSkillLifecycleManager:
    """Test cases for SkillLifecycleManager."""

    @pytest.fixture
    def manager(self):
        return SkillLifecycleManager()

    def test_init(self, manager):
        """Manager initialization."""
        assert manager is not None
        assert manager._skills == {}
        assert manager.min_success_rate == 0.7
        assert manager.auto_deploy is False

    @pytest.mark.asyncio
    async def test_discover_skill_async(self, manager):
        """Discover skill is async."""
        skill = await manager.discover_skill(
            task_pattern="test pattern",
            frequency=1,
        )
        assert skill.skill_id is not None
        assert "test" in skill.name.lower()

    def test_custom_parameters(self):
        """Custom initialization parameters."""
        manager = SkillLifecycleManager(
            min_usage_for_discovery=5,
            min_success_rate=0.8,
            auto_deploy=True
        )
        assert manager.min_usage_for_discovery == 5
        assert manager.min_success_rate == 0.8
        assert manager.auto_deploy is True