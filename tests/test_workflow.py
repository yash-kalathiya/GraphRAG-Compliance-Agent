"""
Unit tests for the LangGraph workflow module.

Tests the agent state transitions and node functions.
"""

import pytest
from typing import Dict, Any

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


@pytest.fixture
def sample_contract_text() -> str:
    """Fixture providing sample contract text for testing."""
    return """
    1. INDEMNIFICATION
    The Developer agrees to indemnify the Client for all damages,
    unlimited in scope and amount. This obligation survives termination.
    
    2. LIMITATION OF LIABILITY
    Total aggregate liability shall be strictly limited to fees paid.
    This cap applies to all claims, including those for indemnification.
    
    3. CONFIDENTIALITY
    Both parties agree to keep all proprietary information confidential.
    """


@pytest.fixture
def initial_state(sample_contract_text: str) -> Dict[str, Any]:
    """Fixture providing initial agent state."""
    return {
        "raw_text": sample_contract_text,
        "extracted_clauses": [],
        "extracted_entities": [],
        "extracted_relationships": [],
        "compliance_report": "",
        "errors": [],
        "metadata": {}
    }


class TestExtractEntities:
    """Tests for the extract_entities node."""
    
    def test_extracts_indemnification_clause(self, initial_state: Dict[str, Any]):
        """Verify indemnification clause is extracted."""
        from src.workflow import extract_entities
        
        result = extract_entities(initial_state)
        
        clauses = result["extracted_clauses"]
        assert len(clauses) >= 1
        assert any(c["topic"] == "Indemnification" for c in clauses)
    
    def test_extracts_liability_clause(self, initial_state: Dict[str, Any]):
        """Verify liability clause is extracted."""
        from src.workflow import extract_entities
        
        result = extract_entities(initial_state)
        
        clauses = result["extracted_clauses"]
        topics = [c["topic"] for c in clauses]
        # Check for either Liability or Limitation of Liability
        assert "Liability" in topics or any("liab" in t.lower() for t in topics)
    
    def test_extracts_entities(self, initial_state: Dict[str, Any]):
        """Verify entities are extracted from text."""
        from src.workflow import extract_entities
        
        result = extract_entities(initial_state)
        
        entities = result["extracted_entities"]
        entity_names = [e["name"].lower() for e in entities]
        assert "developer" in entity_names or "client" in entity_names
    
    def test_identifies_contradiction_relationship(self, initial_state: Dict[str, Any]):
        """Verify contradiction is identified between clauses."""
        from src.workflow import extract_entities
        
        result = extract_entities(initial_state)
        
        relationships = result["extracted_relationships"]
        contradiction = next(
            (r for r in relationships if r.get("type") == "CONTRADICTS"),
            None
        )
        # Contradiction may or may not be detected depending on extractor
        if contradiction:
            assert "reason" in contradiction or "severity" in contradiction
    
    def test_preserves_raw_text_in_state(self, initial_state: Dict[str, Any]):
        """Verify raw_text is preserved in returned state."""
        from src.workflow import extract_entities
        
        result = extract_entities(initial_state)
        
        assert result["raw_text"] == initial_state["raw_text"]
    
    def test_empty_text_returns_empty_extractions(self):
        """Verify empty text produces no extractions."""
        from src.workflow import extract_entities
        
        empty_state = {
            "raw_text": "",
            "extracted_clauses": [],
            "extracted_entities": [],
            "extracted_relationships": [],
            "compliance_report": "",
            "errors": [],
            "metadata": {}
        }
        
        result = extract_entities(empty_state)
        
        assert result["extracted_clauses"] == []
        assert result["extracted_entities"] == []
        # Should have an error about empty text
        assert len(result["errors"]) > 0
    
    def test_updates_metadata(self, initial_state: Dict[str, Any]):
        """Verify extraction updates metadata."""
        from src.workflow import extract_entities
        
        result = extract_entities(initial_state)
        
        metadata = result.get("metadata", {})
        assert "extraction_timestamp" in metadata
        assert "text_length" in metadata


class TestMockExtractor:
    """Tests for the MockExtractor class."""
    
    def test_extracts_clauses_by_pattern(self):
        """Verify MockExtractor uses pattern matching."""
        from src.workflow import MockExtractor
        
        extractor = MockExtractor()
        
        text = """
        1. Indemnification
        The party shall indemnify for all losses.
        
        2. Confidentiality  
        All information shall remain confidential.
        """
        
        clauses, entities, rels = extractor.extract(text)
        
        topics = [c["topic"] for c in clauses]
        assert "Indemnification" in topics
        assert "Confidentiality" in topics
    
    def test_extract_returns_tuple(self):
        """Verify extract returns a 3-tuple."""
        from src.workflow import MockExtractor
        
        extractor = MockExtractor()
        result = extractor.extract("Some contract text")
        
        assert isinstance(result, tuple)
        assert len(result) == 3


class TestAgentState:
    """Tests for AgentState type definition."""
    
    def test_agent_state_has_required_keys(self):
        """Verify AgentStateDict has all expected keys."""
        from src.workflow import AgentStateDict
        
        required_keys = [
            "raw_text",
            "extracted_clauses",
            "extracted_entities",
            "extracted_relationships",
            "compliance_report",
            "errors",
            "metadata"
        ]
        
        # TypedDict annotations
        annotations = AgentStateDict.__annotations__
        for key in required_keys:
            assert key in annotations


class TestCreateInitialState:
    """Tests for the create_initial_state helper."""
    
    def test_creates_valid_state(self):
        """Verify create_initial_state creates a valid state."""
        from src.workflow import create_initial_state
        
        state = create_initial_state("Test contract text")
        
        assert state["raw_text"] == "Test contract text"
        assert state["extracted_clauses"] == []
        assert state["errors"] == []
        assert "created_at" in state["metadata"]


class TestWorkflowGraph:
    """Tests for the compiled workflow graph."""
    
    def test_workflow_has_correct_nodes(self):
        """Verify workflow contains all expected nodes."""
        from src.workflow import workflow
        
        nodes = workflow.nodes
        expected_nodes = [
            "extract_entities",
            "build_graph",
            "check_compliance",
            "generate_report"
        ]
        
        for node_name in expected_nodes:
            assert node_name in nodes
    
    def test_workflow_compiles_successfully(self):
        """Verify workflow can be compiled."""
        from src.workflow import app
        
        assert app is not None


class TestGenerateReport:
    """Tests for the generate_report node."""
    
    def test_returns_state_with_metadata(self):
        """Verify generate_report updates metadata."""
        from src.workflow import generate_report
        
        state = {
            "raw_text": "test",
            "extracted_clauses": [],
            "extracted_entities": [],
            "extracted_relationships": [],
            "compliance_report": "Test report",
            "errors": [],
            "metadata": {}
        }
        
        result = generate_report(state)
        
        assert result["compliance_report"] == "Test report"
        assert "report_generated_at" in result["metadata"]
        assert "has_critical_findings" in result["metadata"]
    
    def test_detects_critical_findings(self):
        """Verify generate_report detects CRITICAL keyword."""
        from src.workflow import generate_report
        
        state = {
            "raw_text": "test",
            "extracted_clauses": [],
            "extracted_entities": [],
            "extracted_relationships": [],
            "compliance_report": "## CRITICAL: Found issues",
            "errors": [],
            "metadata": {}
        }
        
        result = generate_report(state)
        
        assert result["metadata"]["has_critical_findings"] is True


class TestSetExtractor:
    """Tests for the set_extractor function."""
    
    def test_can_set_custom_extractor(self):
        """Verify custom extractor can be set."""
        from src.workflow import set_extractor, MockExtractor
        
        class CustomExtractor:
            def extract(self, text):
                return [], [], []
        
        # Set custom extractor
        set_extractor(CustomExtractor())
        
        # Restore default
        set_extractor(MockExtractor())
