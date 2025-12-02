"""
Domain models for the GraphRAG Legal Auditor.

This module defines Pydantic models for type-safe data handling
throughout the compliance analysis pipeline.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RiskSeverity(str, Enum):
    """Enumeration of risk severity levels."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RelationshipType(str, Enum):
    """Types of relationships between graph nodes."""
    
    CONTRADICTS = "CONTRADICTS"
    REFERS_TO = "REFERS_TO"
    OBLIGATES = "OBLIGATES"
    MODIFIES = "MODIFIES"
    SUPERSEDES = "SUPERSEDES"


class EntityType(str, Enum):
    """Types of entities extracted from contracts."""
    
    PARTY = "Party"
    ORGANIZATION = "Organization"
    PERSON = "Person"
    JURISDICTION = "Jurisdiction"
    DATE = "Date"
    MONETARY_VALUE = "MonetaryValue"


class Clause(BaseModel):
    """
    Represents a clause extracted from a legal contract.
    
    Attributes:
        id: Unique identifier for the clause.
        topic: The subject matter of the clause (e.g., "Indemnification").
        text: The full text content of the clause.
        section_number: Optional section numbering from the original document.
        page_number: Optional page reference in the source document.
    """
    
    id: str = Field(..., description="Unique clause identifier")
    topic: str = Field(..., description="Subject matter of the clause")
    text: str = Field(..., description="Full text content")
    section_number: Optional[str] = Field(None, description="Section number in document")
    page_number: Optional[int] = Field(None, description="Page number in source PDF")
    
    class Config:
        frozen = True


class Entity(BaseModel):
    """
    Represents an entity mentioned in a contract.
    
    Attributes:
        name: The name of the entity.
        entity_type: Classification of the entity.
        description: Optional description or context.
    """
    
    name: str = Field(..., description="Entity name")
    entity_type: EntityType = Field(..., description="Type of entity")
    description: Optional[str] = Field(None, description="Additional context")
    
    class Config:
        frozen = True


class Risk(BaseModel):
    """
    Represents an identified compliance risk.
    
    Attributes:
        id: Unique identifier for the risk.
        severity: The severity level of the risk.
        description: Detailed description of the risk.
        clause_ids: List of clause IDs associated with this risk.
        recommendation: Suggested remediation action.
    """
    
    id: str = Field(..., description="Unique risk identifier")
    severity: RiskSeverity = Field(..., description="Risk severity level")
    description: str = Field(..., description="Risk description")
    clause_ids: list[str] = Field(default_factory=list, description="Related clauses")
    recommendation: Optional[str] = Field(None, description="Remediation suggestion")


class Relationship(BaseModel):
    """
    Represents a relationship between two graph nodes.
    
    Attributes:
        source_id: ID of the source node.
        target_id: ID of the target node.
        relationship_type: The type of relationship.
        properties: Additional properties on the relationship.
    """
    
    source_id: str = Field(..., description="Source node identifier")
    target_id: str = Field(..., description="Target node identifier")
    relationship_type: RelationshipType = Field(..., description="Type of relationship")
    properties: dict = Field(default_factory=dict, description="Relationship properties")


class ContractAnalysis(BaseModel):
    """
    Complete analysis result for a contract.
    
    Attributes:
        contract_id: Unique identifier for the analyzed contract.
        clauses: List of extracted clauses.
        entities: List of identified entities.
        relationships: List of relationships between nodes.
        risks: List of identified risks.
        analyzed_at: Timestamp of analysis.
        summary: Executive summary of findings.
    """
    
    contract_id: str = Field(..., description="Contract identifier")
    clauses: list[Clause] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    summary: Optional[str] = Field(None, description="Executive summary")
    
    @property
    def critical_risk_count(self) -> int:
        """Count of critical severity risks."""
        return sum(1 for r in self.risks if r.severity == RiskSeverity.CRITICAL)
    
    @property
    def has_contradictions(self) -> bool:
        """Check if any contradictions were found."""
        return any(
            r.relationship_type == RelationshipType.CONTRADICTS 
            for r in self.relationships
        )
