"""
Unit tests for the GraphBuilder module.

These tests use mocking to avoid requiring a live Neo4j instance,
making them fast and suitable for CI/CD pipelines.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Generator

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


@pytest.fixture
def mock_neo4j_driver() -> Generator[Mock, None, None]:
    """Fixture that provides a mocked Neo4j driver."""
    with patch("src.graph_builder.GraphDatabase") as mock_gdb:
        # Also patch the driver pool to prevent singleton issues
        with patch("src.graph_builder._DriverPool._instance", None):
            mock_driver = Mock()
            mock_session = Mock()
            mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
            mock_driver.session.return_value.__exit__ = Mock(return_value=False)
            mock_gdb.driver.return_value = mock_driver
            yield mock_driver


@pytest.fixture
def graph_builder(mock_neo4j_driver: Mock):
    """Fixture that provides a GraphBuilder with mocked dependencies."""
    from src.graph_builder import GraphBuilder
    # Use use_pool=False to avoid singleton issues in tests
    return GraphBuilder(use_pool=False)


class TestGraphBuilderInit:
    """Tests for GraphBuilder initialization."""
    
    def test_creates_driver_with_correct_credentials(self, mock_neo4j_driver: Mock):
        """Verify driver is created with settings from config."""
        from src.graph_builder import GraphBuilder
        
        with patch("src.graph_builder.GraphDatabase") as mock_gdb:
            with patch("src.graph_builder._DriverPool._instance", None):
                mock_gdb.driver.return_value = mock_neo4j_driver
                _ = GraphBuilder(use_pool=False)
                
                mock_gdb.driver.assert_called_once()


class TestGraphBuilderOperations:
    """Tests for GraphBuilder CRUD operations."""
    
    def test_add_clause_executes_merge_query(self, graph_builder, mock_neo4j_driver: Mock):
        """Verify add_clause runs the correct Cypher query."""
        mock_session = MagicMock()
        mock_neo4j_driver.session.return_value.__enter__.return_value = mock_session
        
        graph_builder.add_clause(
            clause_id="test-1",
            text="Sample clause text",
            topic="Indemnification"
        )
        
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        assert "MERGE" in call_args[0][0]
        assert call_args.kwargs["id"] == "test-1"
    
    def test_add_clause_rejects_empty_id(self, graph_builder):
        """Verify add_clause rejects empty clause ID."""
        from src.exceptions import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            graph_builder.add_clause(clause_id="", text="Some text", topic="Test")
        
        assert "clause_id" in str(exc_info.value).lower() or exc_info.value.field == "clause_id"
    
    def test_add_entity_executes_merge_query(self, graph_builder, mock_neo4j_driver: Mock):
        """Verify add_entity runs the correct Cypher query."""
        mock_session = MagicMock()
        mock_neo4j_driver.session.return_value.__enter__.return_value = mock_session
        
        graph_builder.add_entity(name="Acme Corp", entity_type="Party")
        
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        assert "MERGE" in call_args[0][0]
        assert call_args.kwargs["name"] == "Acme Corp"
    
    def test_add_entity_rejects_empty_name(self, graph_builder):
        """Verify add_entity rejects empty name."""
        from src.exceptions import ValidationError
        
        with pytest.raises(ValidationError):
            graph_builder.add_entity(name="", entity_type="Party")
    
    def test_add_risk_executes_merge_query(self, graph_builder, mock_neo4j_driver: Mock):
        """Verify add_risk runs the correct Cypher query."""
        mock_session = MagicMock()
        mock_neo4j_driver.session.return_value.__enter__.return_value = mock_session
        
        graph_builder.add_risk(
            risk_id="risk-1",
            severity="critical",
            description="Test risk",
            clause_id="clause-1",
            recommendation="Fix it"
        )
        
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        assert "MERGE" in call_args[0][0]
        assert "Risk" in call_args[0][0]
    
    def test_add_risk_rejects_invalid_severity(self, graph_builder):
        """Verify add_risk rejects invalid severity levels."""
        from src.exceptions import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            graph_builder.add_risk(
                risk_id="risk-1",
                severity="invalid",
                description="Test",
                clause_id="clause-1"
            )
        
        assert "severity" in str(exc_info.value).lower()
    
    def test_create_relationship_with_properties(self, graph_builder, mock_neo4j_driver: Mock):
        """Verify relationships are created with properties."""
        mock_session = MagicMock()
        mock_neo4j_driver.session.return_value.__enter__.return_value = mock_session
        
        graph_builder.create_relationship(
            source_label="Clause",
            source_key="id",
            source_val="1",
            target_label="Clause",
            target_key="id",
            target_val="2",
            rel_type="CONTRADICTS",
            properties={"reason": "Test reason"}
        )
        
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        assert "CONTRADICTS" in call_args[0][0]
        assert "reason" in call_args.kwargs
    
    def test_create_relationship_rejects_invalid_rel_type(self, graph_builder):
        """Verify create_relationship rejects invalid relationship types."""
        from src.exceptions import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            graph_builder.create_relationship(
                source_label="Clause",
                source_key="id",
                source_val="1",
                target_label="Clause",
                target_key="id",
                target_val="2",
                rel_type="INVALID_REL_TYPE",
            )
        
        assert "relationship type" in str(exc_info.value).lower()
    
    def test_create_relationship_rejects_invalid_label(self, graph_builder):
        """Verify create_relationship rejects invalid node labels."""
        from src.exceptions import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            graph_builder.create_relationship(
                source_label="InvalidLabel",
                source_key="id",
                source_val="1",
                target_label="Clause",
                target_key="id",
                target_val="2",
                rel_type="CONTRADICTS",
            )
        
        assert "label" in str(exc_info.value).lower()
    
    def test_get_contradictions_returns_list(self, graph_builder, mock_neo4j_driver: Mock):
        """Verify get_contradictions returns properly formatted data."""
        mock_session = MagicMock()
        mock_record = Mock()
        mock_record.data.return_value = {
            "clause1_id": "1",
            "clause1_text": "First clause",
            "clause1_topic": "Indemnification",
            "clause2_id": "2",
            "clause2_text": "Second clause",
            "clause2_topic": "Liability",
            "contradiction_reason": "Conflicting terms"
        }
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([mock_record]))
        mock_session.run.return_value = mock_result
        mock_neo4j_driver.session.return_value.__enter__.return_value = mock_session
        
        result = graph_builder.get_contradictions()
        
        assert len(result) == 1
        assert result[0]["clause1_id"] == "1"
        assert result[0]["clause2_id"] == "2"
        assert result[0]["clause1_topic"] == "Indemnification"
    
    def test_get_risks_returns_list(self, graph_builder, mock_neo4j_driver: Mock):
        """Verify get_risks returns properly formatted data."""
        mock_session = MagicMock()
        mock_record = Mock()
        mock_record.data.return_value = {
            "risk_id": "risk-1",
            "severity": "critical",
            "description": "Test risk",
            "recommendation": "Fix it",
            "clause_id": "1",
            "clause_topic": "Indemnification"
        }
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([mock_record]))
        mock_session.run.return_value = mock_result
        mock_neo4j_driver.session.return_value.__enter__.return_value = mock_session
        
        result = graph_builder.get_risks()
        
        assert len(result) == 1
        assert result[0]["severity"] == "critical"
        assert result[0]["clause_id"] == "1"
    
    def test_close_closes_driver(self, graph_builder, mock_neo4j_driver: Mock):
        """Verify close() properly closes the driver connection."""
        graph_builder.close()
        mock_neo4j_driver.close.assert_called_once()
    
    def test_context_manager_closes_driver(self, mock_neo4j_driver: Mock):
        """Verify context manager properly closes the driver."""
        from src.graph_builder import GraphBuilder
        
        with patch("src.graph_builder.GraphDatabase") as mock_gdb:
            with patch("src.graph_builder._DriverPool._instance", None):
                mock_gdb.driver.return_value = mock_neo4j_driver
                
                with GraphBuilder(use_pool=False) as gb:
                    pass
                
                mock_neo4j_driver.close.assert_called_once()


class TestGraphBuilderEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_create_relationship_without_properties(self, graph_builder, mock_neo4j_driver: Mock):
        """Verify relationships work without properties."""
        mock_session = MagicMock()
        mock_neo4j_driver.session.return_value.__enter__.return_value = mock_session
        
        graph_builder.create_relationship(
            source_label="Clause",
            source_key="id",
            source_val="1",
            target_label="Entity",
            target_key="name",
            target_val="Developer",
            rel_type="OBLIGATES",
            properties=None
        )
        
        mock_session.run.assert_called_once()
    
    def test_get_contradictions_empty_result(self, graph_builder, mock_neo4j_driver: Mock):
        """Verify empty result is handled correctly."""
        mock_session = MagicMock()
        mock_result = Mock()
        mock_result.__iter__ = Mock(return_value=iter([]))
        mock_session.run.return_value = mock_result
        mock_neo4j_driver.session.return_value.__enter__.return_value = mock_session
        
        result = graph_builder.get_contradictions()
        
        assert result == []
    
    def test_is_closed_property(self, mock_neo4j_driver: Mock):
        """Verify is_closed property reflects driver state."""
        from src.graph_builder import GraphBuilder
        
        with patch("src.graph_builder.GraphDatabase") as mock_gdb:
            with patch("src.graph_builder._DriverPool._instance", None):
                mock_gdb.driver.return_value = mock_neo4j_driver
                
                gb = GraphBuilder(use_pool=False)
                assert not gb.is_closed
                
                gb.close()
                assert gb.is_closed


class TestValidateIdentifier:
    """Tests for the validate_identifier function."""
    
    def test_valid_identifiers(self):
        """Verify valid identifiers pass validation."""
        from src.graph_builder import validate_identifier
        
        valid_ids = [
            "clause_1",
            "entity-123",
            "Risk_Node",
            "simple",
            "with-dashes-and_underscores",
        ]
        
        for identifier in valid_ids:
            # Should not raise
            validate_identifier(identifier, "test_field")
    
    def test_invalid_identifiers(self):
        """Verify invalid identifiers are rejected."""
        from src.graph_builder import validate_identifier
        from src.exceptions import ValidationError
        
        invalid_ids = [
            "has space",
            "has;semicolon",
            "has'quote",
            'has"double',
            "has{brace",
            "",
            "   ",
        ]
        
        for identifier in invalid_ids:
            with pytest.raises(ValidationError):
                validate_identifier(identifier, "test_field")
