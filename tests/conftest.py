"""
Pytest fixtures shared across all test modules.
"""

import pytest
from typing import Dict, Any


@pytest.fixture
def sample_contract_text() -> str:
    """Sample contract text with known contradictions."""
    return """
    CONTRACT FOR SOFTWARE DEVELOPMENT SERVICES

    1. INDEMNIFICATION
    The Developer agrees to indemnify, defend, and hold harmless the Client 
    from and against any and all claims, liabilities, damages, losses, and 
    expenses. This indemnification obligation shall be unlimited in scope.

    2. LIMITATION OF LIABILITY
    The total aggregate liability of the Developer shall be strictly limited 
    to the total amount of fees paid. This cap applies to all claims, 
    including those for indemnification.

    3. CONFIDENTIALITY
    Both parties agree to keep all proprietary information confidential.
    """


@pytest.fixture
def empty_agent_state() -> Dict[str, Any]:
    """Empty initial agent state."""
    return {
        "raw_text": "",
        "extracted_clauses": [],
        "extracted_entities": [],
        "extracted_relationships": [],
        "compliance_report": ""
    }


@pytest.fixture
def populated_agent_state(sample_contract_text: str) -> Dict[str, Any]:
    """Agent state with sample contract loaded."""
    return {
        "raw_text": sample_contract_text,
        "extracted_clauses": [],
        "extracted_entities": [],
        "extracted_relationships": [],
        "compliance_report": ""
    }
