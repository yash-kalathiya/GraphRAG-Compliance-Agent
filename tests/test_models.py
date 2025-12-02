"""
Unit tests for Pydantic models.
"""

import pytest
from datetime import datetime

pytestmark = pytest.mark.unit


class TestClauseModel:
    """Tests for the Clause model."""
    
    def test_clause_creation(self):
        """Verify Clause can be created with required fields."""
        from src.models import Clause
        
        clause = Clause(
            id="test-1",
            topic="Indemnification",
            text="Sample clause text"
        )
        
        assert clause.id == "test-1"
        assert clause.topic == "Indemnification"
        assert clause.text == "Sample clause text"
    
    def test_clause_optional_fields(self):
        """Verify optional fields default to None."""
        from src.models import Clause
        
        clause = Clause(id="1", topic="Test", text="Text")
        
        assert clause.section_number is None
        assert clause.page_number is None
    
    def test_clause_is_immutable(self):
        """Verify Clause is frozen (immutable)."""
        from src.models import Clause
        from pydantic import ValidationError
        
        clause = Clause(id="1", topic="Test", text="Text")
        
        with pytest.raises(ValidationError):
            clause.id = "new-id"


class TestEntityModel:
    """Tests for the Entity model."""
    
    def test_entity_creation(self):
        """Verify Entity can be created."""
        from src.models import Entity, EntityType
        
        entity = Entity(
            name="Acme Corp",
            entity_type=EntityType.ORGANIZATION
        )
        
        assert entity.name == "Acme Corp"
        assert entity.entity_type == EntityType.ORGANIZATION


class TestRiskModel:
    """Tests for the Risk model."""
    
    def test_risk_creation(self):
        """Verify Risk can be created."""
        from src.models import Risk, RiskSeverity
        
        risk = Risk(
            id="risk-1",
            severity=RiskSeverity.CRITICAL,
            description="Contradicting clauses found"
        )
        
        assert risk.severity == RiskSeverity.CRITICAL
        assert risk.clause_ids == []
    
    def test_risk_with_clause_ids(self):
        """Verify Risk can have associated clause IDs."""
        from src.models import Risk, RiskSeverity
        
        risk = Risk(
            id="risk-1",
            severity=RiskSeverity.HIGH,
            description="Test",
            clause_ids=["1", "2"]
        )
        
        assert "1" in risk.clause_ids
        assert "2" in risk.clause_ids


class TestContractAnalysis:
    """Tests for the ContractAnalysis model."""
    
    def test_contract_analysis_creation(self):
        """Verify ContractAnalysis can be created."""
        from src.models import ContractAnalysis
        
        analysis = ContractAnalysis(contract_id="contract-123")
        
        assert analysis.contract_id == "contract-123"
        assert analysis.clauses == []
        assert isinstance(analysis.analyzed_at, datetime)
    
    def test_critical_risk_count_property(self):
        """Verify critical_risk_count computed correctly."""
        from src.models import ContractAnalysis, Risk, RiskSeverity
        
        analysis = ContractAnalysis(
            contract_id="test",
            risks=[
                Risk(id="1", severity=RiskSeverity.CRITICAL, description="Critical"),
                Risk(id="2", severity=RiskSeverity.HIGH, description="High"),
                Risk(id="3", severity=RiskSeverity.CRITICAL, description="Critical 2"),
            ]
        )
        
        assert analysis.critical_risk_count == 2
    
    def test_has_contradictions_property(self):
        """Verify has_contradictions computed correctly."""
        from src.models import ContractAnalysis, Relationship, RelationshipType
        
        analysis = ContractAnalysis(
            contract_id="test",
            relationships=[
                Relationship(
                    source_id="1",
                    target_id="2",
                    relationship_type=RelationshipType.CONTRADICTS
                )
            ]
        )
        
        assert analysis.has_contradictions is True


class TestEnums:
    """Tests for enum classes."""
    
    def test_risk_severity_values(self):
        """Verify RiskSeverity has expected values."""
        from src.models import RiskSeverity
        
        assert RiskSeverity.LOW.value == "low"
        assert RiskSeverity.MEDIUM.value == "medium"
        assert RiskSeverity.HIGH.value == "high"
        assert RiskSeverity.CRITICAL.value == "critical"
    
    def test_relationship_type_values(self):
        """Verify RelationshipType has expected values."""
        from src.models import RelationshipType
        
        assert RelationshipType.CONTRADICTS.value == "CONTRADICTS"
        assert RelationshipType.REFERS_TO.value == "REFERS_TO"
