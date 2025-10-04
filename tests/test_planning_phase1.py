"""Tests for Planning Agent Phase 1: Foundation & Data Structures."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agents.config import PlanningAgentSettings, load_planning_settings
from agents.plan_validator import ValidationResult, validate_plan_json, load_plan_schema
from agents.logging_utils import (
    persist_plan_json,
    load_last_plan_json,
    init_metrics_csv,
    append_metrics,
    calculate_completion_rate,
)


class TestPlanningAgentSettings:
    """Test configuration loading."""

    def test_default_settings(self, monkeypatch):
        """Test default settings when no env vars are set."""
        # Clear relevant env vars
        for key in ["USE_RAG_PLANNING_AGENT", "PLANNING_AGENT_MODE", 
                    "PLANNING_MAX_CURATED_EXAMPLES", "PLANNING_MAX_QUOTE_LENGTH"]:
            monkeypatch.delenv(key, raising=False)
        
        settings = load_planning_settings()
        assert settings.enabled is False
        assert settings.mode == "two-requests"
        assert settings.max_examples == 12
        assert settings.max_quote_length == 400
        assert settings.schema_version == "1.0"

    def test_env_override(self, monkeypatch):
        """Test that environment variables override defaults."""
        monkeypatch.setenv("USE_RAG_PLANNING_AGENT", "1")
        monkeypatch.setenv("PLANNING_AGENT_MODE", "single-request")
        monkeypatch.setenv("PLANNING_MAX_CURATED_EXAMPLES", "8")
        monkeypatch.setenv("PLANNING_MAX_QUOTE_LENGTH", "300")
        
        settings = load_planning_settings()
        assert settings.enabled is True
        assert settings.mode == "single-request"
        assert settings.max_examples == 8
        assert settings.max_quote_length == 300

    def test_invalid_mode_fallback(self, monkeypatch):
        """Test that invalid mode falls back to default."""
        monkeypatch.setenv("PLANNING_AGENT_MODE", "invalid-mode")
        
        settings = load_planning_settings()
        assert settings.mode == "two-requests"

    def test_out_of_range_values(self, monkeypatch):
        """Test that out-of-range values fall back to defaults."""
        monkeypatch.setenv("PLANNING_MAX_CURATED_EXAMPLES", "0")  # Below minimum
        monkeypatch.setenv("PLANNING_MAX_QUOTE_LENGTH", "50")  # Below minimum
        
        settings = load_planning_settings()
        assert settings.max_examples == 12  # Default
        assert settings.max_quote_length == 400  # Default

    def test_settings_immutable(self):
        """Test that settings are immutable."""
        settings = load_planning_settings()
        with pytest.raises(AttributeError):
            settings.enabled = True  # type: ignore[misc]


class TestPlanSchema:
    """Test Plan JSON schema loading and validation."""

    def test_schema_loads(self):
        """Test that schema can be loaded."""
        schema = load_plan_schema()
        assert isinstance(schema, dict)
        assert "$schema" in schema
        assert "properties" in schema
        assert "required" in schema

    def test_schema_has_required_fields(self):
        """Test that schema defines required fields."""
        schema = load_plan_schema()
        required = schema.get("required", [])
        assert "query" in required
        assert "curated_examples" in required
        assert "schema_guidance" in required

    def test_schema_has_all_properties(self):
        """Test that schema has expected properties."""
        schema = load_plan_schema()
        props = schema.get("properties", {})
        expected = [
            "schema_version", "query", "metadata_filter", "curated_examples",
            "coverage", "extracted_params", "missing_params", "conflicts",
            "schema_guidance", "citations", "tool_calls", "status", "attempt",
            "plan_completion_rate", "stage2_feedback"
        ]
        for field in expected:
            assert field in props, f"Missing property: {field}"


class TestPlanValidator:
    """Test Plan JSON validator."""

    @pytest.fixture
    def fixtures_dir(self):
        """Return path to fixtures directory."""
        return Path(__file__).parent / "fixtures" / "plan_jsons"

    @pytest.fixture
    def valid_plan(self, fixtures_dir):
        """Load valid plan fixture."""
        with (fixtures_dir / "valid_plan_v1.json").open(encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def invalid_missing_required(self, fixtures_dir):
        """Load invalid plan with missing required fields."""
        with (fixtures_dir / "invalid_missing_required.json").open(encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def invalid_quote_too_long(self, fixtures_dir):
        """Load invalid plan with quote too long."""
        with (fixtures_dir / "invalid_quote_too_long.json").open(encoding="utf-8") as f:
            return json.load(f)

    def test_valid_plan_passes(self, valid_plan):
        """Test that a valid plan passes validation."""
        result = validate_plan_json(valid_plan)
        assert result.valid is True
        # May have warnings but no errors
        errors = [issue for issue in result.issues if issue.severity == "error"]
        assert len(errors) == 0

    def test_missing_required_fields(self, invalid_missing_required):
        """Test that missing required fields are caught."""
        result = validate_plan_json(invalid_missing_required)
        assert result.valid is False
        assert len(result.issues) > 0
        # Should have error for missing 'query' and 'schema_guidance'
        error_codes = [issue.code for issue in result.issues if issue.severity == "error"]
        assert any("missing" in code or "required" in code for code in error_codes)

    def test_quote_too_long(self, invalid_quote_too_long):
        """Test that overly long quotes are caught."""
        result = validate_plan_json(invalid_quote_too_long)
        assert result.valid is False
        error_codes = [issue.code for issue in result.issues]
        assert "quote-too-long" in error_codes

    def test_too_many_examples(self, valid_plan):
        """Test that exceeding max examples is caught."""
        # Create a plan with too many examples
        plan = dict(valid_plan)
        plan["curated_examples"] = [
            {
                "filename": f"test{i}.json",
                "rank": i + 1,
                "spans": [{"quote": "test"}]
            }
            for i in range(15)  # More than default max of 12
        ]
        
        result = validate_plan_json(plan)
        assert result.valid is False
        error_codes = [issue.code for issue in result.issues]
        assert "too-many-examples" in error_codes

    def test_validation_result_serialization(self, valid_plan):
        """Test that ValidationResult can be serialized."""
        result = validate_plan_json(valid_plan)
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert "valid" in result_dict
        assert "issues" in result_dict
        assert isinstance(result_dict["issues"], list)

    def test_issue_string_representation(self, invalid_missing_required):
        """Test that ValidationIssue has readable string representation."""
        result = validate_plan_json(invalid_missing_required)
        if result.issues:
            issue_str = str(result.issues[0])
            assert isinstance(issue_str, str)
            assert len(issue_str) > 0


class TestLoggingUtils:
    """Test logging utilities."""

    @pytest.fixture
    def sample_plan(self):
        """Return a sample plan for testing."""
        return {
            "schema_version": "1.0",
            "query": "test query",
            "curated_examples": [],
            "schema_guidance": "test",
            "status": "completed",
        }

    @pytest.fixture
    def cleanup_logs(self):
        """Clean up test logs after test."""
        yield
        # Cleanup
        logs_dir = Path("logs/last_run")
        if logs_dir.exists():
            for file in logs_dir.glob("*.json"):
                try:
                    file.unlink()
                except Exception:
                    pass

    def test_persist_and_load_plan(self, sample_plan, cleanup_logs):
        """Test persisting and loading plan JSON."""
        path = persist_plan_json(sample_plan, attempt=1)
        assert path.exists()
        
        loaded = load_last_plan_json()
        assert loaded is not None
        assert loaded["query"] == sample_plan["query"]
        assert "persisted_at" in loaded
        assert loaded["attempt"] == 1

    def test_plan_rotation(self, sample_plan, cleanup_logs):
        """Test that plan files are rotated."""
        # Save multiple times
        persist_plan_json(sample_plan, attempt=1)
        persist_plan_json({"query": "second", "curated_examples": [], "schema_guidance": "test"}, attempt=2)
        
        # Check that .1 version exists
        rotated = Path("logs/last_run/planning_plan.1.json")
        assert rotated.exists()

    def test_init_metrics_csv(self):
        """Test metrics CSV initialization."""
        # Clean up if exists
        metrics_path = Path("metrics/plan_runs.csv")
        if metrics_path.exists():
            metrics_path.unlink()
        
        init_metrics_csv()
        assert metrics_path.exists()
        
        # Check headers
        with metrics_path.open("r") as f:
            header = f.readline().strip()
            assert "timestamp" in header
            assert "status" in header
            assert "completion_rate" in header

    def test_append_metrics(self):
        """Test appending metrics."""
        metrics_path = Path("metrics/plan_runs.csv")
        
        # Ensure clean state
        if metrics_path.exists():
            metrics_path.unlink()
        
        append_metrics(
            query="test query",
            status="completed",
            completion_rate=0.85,
            stage2_passed=True,
            retry_count=0,
            mode="two-requests",
            notes="test run"
        )
        
        assert metrics_path.exists()
        
        # Read and verify
        with metrics_path.open("r") as f:
            lines = f.readlines()
            assert len(lines) >= 2  # Header + at least one entry
            assert "completed" in lines[1]
            assert "0.85" in lines[1]

    def test_calculate_completion_rate(self):
        """Test completion rate calculation."""
        plan = {
            "extracted_params": [
                {"name": "StepAlgorithm", "value": 1, "source": "test"},
                {"name": "TimeMax", "value": 2.0, "source": "test"},
            ],
            "missing_params": ["RhopOutMax"],
        }
        
        required = {"StepAlgorithm", "TimeMax", "RhopOutMax"}
        rate = calculate_completion_rate(plan, required)
        
        # 2 out of 3 covered
        assert rate == 0.67

    def test_calculate_completion_rate_empty(self):
        """Test completion rate with no required fields."""
        rate = calculate_completion_rate({}, set())
        assert rate == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
