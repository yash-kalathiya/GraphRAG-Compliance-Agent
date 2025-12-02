"""
GraphRAG Legal Auditor - Core Module

A production-grade GraphRAG system for legal contract compliance analysis.

This package provides:
    - GraphBuilder: Neo4j knowledge graph management with connection pooling
    - Workflow: LangGraph-based compliance analysis pipeline
    - Models: Pydantic domain models for type-safe operations
    - Exceptions: Custom exception hierarchy for error handling

Example:
    >>> from src import GraphBuilder, app, create_initial_state
    >>> 
    >>> # Analyze a contract
    >>> state = create_initial_state(contract_text)
    >>> result = app.invoke(state)
    >>> print(result["compliance_report"])
"""

from src.graph_builder import GraphBuilder, validate_identifier
from src.workflow import (
    app,
    AgentState,
    AgentStateDict,
    ContractExtractor,
    MockExtractor,
    create_workflow,
    create_initial_state,
    set_extractor,
)
from src.models import (
    Clause,
    Entity,
    Risk,
    Relationship,
    ContractAnalysis,
    RiskSeverity,
    RelationshipType,
    EntityType,
)
from src.exceptions import (
    GraphRAGException,
    DatabaseConnectionError,
    GraphBuildError,
    ComplianceCheckError,
    ExtractionError,
    ValidationError,
)

__version__ = "1.0.0"
__author__ = "GraphRAG Team"

__all__ = [
    # Core classes
    "GraphBuilder",
    "validate_identifier",
    # Workflow
    "app",
    "AgentState",
    "AgentStateDict",
    "ContractExtractor",
    "MockExtractor",
    "create_workflow",
    "create_initial_state",
    "set_extractor",
    # Models
    "Clause",
    "Entity",
    "Risk",
    "Relationship",
    "ContractAnalysis",
    "RiskSeverity",
    "RelationshipType",
    "EntityType",
    # Exceptions
    "GraphRAGException",
    "DatabaseConnectionError",
    "GraphBuildError",
    "ComplianceCheckError",
    "ExtractionError",
    "ValidationError",
]
