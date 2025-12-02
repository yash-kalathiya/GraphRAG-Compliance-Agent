"""
LangGraph Workflow for Legal Contract Compliance Analysis.

This module defines a multi-node state machine that orchestrates the
contract analysis pipeline:

    extract_entities -> build_graph -> check_compliance -> generate_report

Each node is a pure function that transforms the AgentState, enabling
easy testing and debugging.

Architecture:
    The workflow uses a Protocol-based extractor interface, allowing
    easy swapping between mock extraction (for demos) and real LLM-based
    extraction (for production).

Example:
    >>> from src.workflow import app
    >>> result = app.invoke({"raw_text": contract_text, ...})
    >>> print(result["compliance_report"])
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from langgraph.graph import StateGraph, END

from src.graph_builder import GraphBuilder
from src.models import RiskSeverity
from src.exceptions import GraphBuildError, ExtractionError

logger = logging.getLogger(__name__)

# =============================================================================
# STATE & PROTOCOLS
# =============================================================================

@dataclass
class AgentState:
    """
    Typed state container for the compliance analysis workflow.
    
    Using dataclass instead of TypedDict for better IDE support,
    default values, and method support.
    
    Attributes:
        raw_text: The original contract text to analyze.
        extracted_clauses: List of clause dictionaries with id, topic, text.
        extracted_entities: List of entity dictionaries with name, type.
        extracted_relationships: List of relationship dictionaries.
        compliance_report: Generated compliance report markdown.
        errors: List of errors encountered during processing.
        metadata: Additional metadata about the analysis.
    """
    
    raw_text: str
    extracted_clauses: list[dict[str, Any]] = field(default_factory=list)
    extracted_entities: list[dict[str, Any]] = field(default_factory=list)
    extracted_relationships: list[dict[str, Any]] = field(default_factory=list)
    compliance_report: str = ""
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for LangGraph compatibility."""
        return {
            "raw_text": self.raw_text,
            "extracted_clauses": self.extracted_clauses,
            "extracted_entities": self.extracted_entities,
            "extracted_relationships": self.extracted_relationships,
            "compliance_report": self.compliance_report,
            "errors": self.errors,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentState":
        """Create from dictionary."""
        return cls(
            raw_text=data.get("raw_text", ""),
            extracted_clauses=data.get("extracted_clauses", []),
            extracted_entities=data.get("extracted_entities", []),
            extracted_relationships=data.get("extracted_relationships", []),
            compliance_report=data.get("compliance_report", ""),
            errors=data.get("errors", []),
            metadata=data.get("metadata", {}),
        )


# TypedDict for LangGraph compatibility (it requires TypedDict)
from typing import TypedDict

class AgentStateDict(TypedDict, total=False):
    """TypedDict version for LangGraph compatibility."""
    raw_text: str
    extracted_clauses: list[dict[str, Any]]
    extracted_entities: list[dict[str, Any]]
    extracted_relationships: list[dict[str, Any]]
    compliance_report: str
    errors: list[str]
    metadata: dict[str, Any]


@runtime_checkable
class ContractExtractor(Protocol):
    """
    Protocol for contract extraction implementations.
    
    Allows swapping between mock extraction and LLM-based extraction.
    """
    
    def extract(
        self, text: str
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """
        Extract clauses, entities, and relationships from text.
        
        Returns:
            Tuple of (clauses, entities, relationships).
        """
        ...


class MockExtractor:
    """
    Pattern-based extractor for demo purposes.
    
    Uses regex and keyword matching to simulate LLM extraction.
    Replace with LLMExtractor for production use.
    """
    
    # Clause patterns with regex
    CLAUSE_PATTERNS: dict[str, re.Pattern] = {
        "Indemnification": re.compile(
            r"indemnif\w*|hold\s+harmless", re.IGNORECASE
        ),
        "Liability": re.compile(
            r"limitation\s+of\s+liability|liability\s+(cap|limit)", re.IGNORECASE
        ),
        "Confidentiality": re.compile(
            r"confidential\w*|non-disclosure|NDA", re.IGNORECASE
        ),
        "Termination": re.compile(
            r"terminat\w*|cancel\w*", re.IGNORECASE
        ),
        "IP Rights": re.compile(
            r"intellectual\s+property|IP\s+rights|copyright|patent", re.IGNORECASE
        ),
    }
    
    ENTITY_PATTERNS: dict[str, re.Pattern] = {
        "Party": re.compile(
            r"\b(Developer|Client|Contractor|Company|Vendor|Provider|Customer)\b",
            re.IGNORECASE
        ),
    }
    
    def extract(
        self, text: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Extract contract elements using pattern matching.
        
        Args:
            text: Contract text to analyze.
        
        Returns:
            Tuple of (clauses, entities, relationships).
        """
        clauses: list[dict[str, Any]] = []
        entities: list[dict[str, Any]] = []
        relationships: list[dict[str, Any]] = []
        seen_entities: set[str] = set()
        
        # Split into sections (simple approach - look for numbered sections)
        sections = re.split(r"\n\s*\d+\.\s+", text)
        
        for idx, section in enumerate(sections):
            if not section.strip():
                continue
                
            # Match clause topics
            for topic, pattern in self.CLAUSE_PATTERNS.items():
                if pattern.search(section):
                    clause_id = str(len(clauses) + 1)
                    # Extract first 200 chars as summary
                    summary = section.strip()[:200]
                    if len(section) > 200:
                        summary += "..."
                    
                    clauses.append({
                        "id": clause_id,
                        "topic": topic,
                        "text": summary,
                        "full_text": section.strip(),
                    })
                    break  # One topic per section
            
            # Extract entities
            for entity_type, pattern in self.ENTITY_PATTERNS.items():
                for match in pattern.finditer(section):
                    entity_name = match.group(1).title()
                    if entity_name not in seen_entities:
                        entities.append({
                            "name": entity_name,
                            "type": entity_type,
                        })
                        seen_entities.add(entity_name)
        
        # Detect contradictions (simplified logic)
        relationships.extend(self._detect_contradictions(clauses))
        
        # Link clauses to entities
        relationships.extend(self._link_clauses_to_entities(clauses, entities))
        
        return clauses, entities, relationships
    
    def _detect_contradictions(
        self, clauses: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect potential contradictions between clauses."""
        contradictions: list[dict[str, Any]] = []
        
        # Find indemnification and liability clauses
        indemnity_clause = None
        liability_clause = None
        
        for clause in clauses:
            if clause["topic"] == "Indemnification":
                indemnity_clause = clause
            elif clause["topic"] == "Liability":
                liability_clause = clause
        
        # Check for unlimited indemnity vs liability cap conflict
        if indemnity_clause and liability_clause:
            full_indem = indemnity_clause.get("full_text", indemnity_clause["text"]).lower()
            full_liab = liability_clause.get("full_text", liability_clause["text"]).lower()
            
            has_unlimited_indem = "unlimited" in full_indem or "without limit" in full_indem
            has_liability_cap = "limited to" in full_liab or "cap" in full_liab or "shall not exceed" in full_liab
            indem_in_cap = "indemnif" in full_liab
            
            if has_unlimited_indem and has_liability_cap and indem_in_cap:
                contradictions.append({
                    "source": indemnity_clause["id"],
                    "target": liability_clause["id"],
                    "type": "CONTRADICTS",
                    "reason": (
                        f"The {indemnity_clause['topic']} clause states unlimited indemnification, "
                        f"while the {liability_clause['topic']} clause caps all liability "
                        f"including indemnification claims. This creates legal ambiguity."
                    ),
                    "severity": RiskSeverity.CRITICAL.value,
                })
        
        return contradictions
    
    def _link_clauses_to_entities(
        self,
        clauses: list[dict[str, Any]],
        entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Create OBLIGATES relationships between clauses and entities."""
        relationships: list[dict[str, Any]] = []
        
        for clause in clauses:
            full_text = clause.get("full_text", clause["text"]).lower()
            
            for entity in entities:
                entity_lower = entity["name"].lower()
                # Check if entity is mentioned as having an obligation
                if entity_lower in full_text:
                    if any(word in full_text for word in ["agrees to", "shall", "must", "will"]):
                        relationships.append({
                            "source": clause["id"],
                            "target": entity["name"],
                            "type": "OBLIGATES",
                            "target_type": "Entity",
                        })
        
        return relationships


# Global extractor instance (can be swapped for testing)
_extractor: ContractExtractor = MockExtractor()

# =============================================================================
# WORKFLOW NODES
# =============================================================================

def extract_entities(state: AgentStateDict) -> AgentStateDict:
    """
    Extract entities, clauses, and relationships from contract text.
    
    This node uses the configured extractor (MockExtractor by default)
    to parse the contract text and identify key elements.
    
    Args:
        state: Current workflow state containing raw_text.
    
    Returns:
        Updated state with extracted_clauses, extracted_entities,
        and extracted_relationships populated.
    """
    logger.info("🔍 Extracting Entities & Clauses")
    
    text = state.get("raw_text", "")
    errors: list[str] = list(state.get("errors", []))
    metadata: dict[str, Any] = dict(state.get("metadata", {}))
    
    if not text or not text.strip():
        logger.warning("Empty contract text provided")
        errors.append("Empty contract text provided")
        return {
            **state,
            "extracted_clauses": [],
            "extracted_entities": [],
            "extracted_relationships": [],
            "errors": errors,
        }
    
    try:
        clauses, entities, relationships = _extractor.extract(text)
        
        # Update metadata
        metadata["extraction_timestamp"] = datetime.now().isoformat()
        metadata["text_length"] = len(text)
        metadata["clause_count"] = len(clauses)
        metadata["entity_count"] = len(entities)
        
        # Log extraction results
        logger.info(
            f"Extraction complete: {len(clauses)} clauses, "
            f"{len(entities)} entities, {len(relationships)} relationships"
        )
        
        if relationships:
            contradictions = [r for r in relationships if r.get("type") == "CONTRADICTS"]
            if contradictions:
                logger.warning(f"⚠️  Identified {len(contradictions)} potential contradiction(s)")
        
        return {
            **state,
            "extracted_clauses": clauses,
            "extracted_entities": entities,
            "extracted_relationships": relationships,
            "errors": errors,
            "metadata": metadata,
        }
        
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        errors.append(f"Extraction error: {str(e)}")
        return {
            **state,
            "extracted_clauses": [],
            "extracted_entities": [],
            "extracted_relationships": [],
            "errors": errors,
        }

def build_graph(state: AgentStateDict) -> AgentStateDict:
    """
    Populate Neo4j knowledge graph with extracted data.
    
    Takes the extracted clauses, entities, and relationships from
    the previous node and creates corresponding nodes and edges
    in the Neo4j database.
    
    Also creates Risk nodes for any CONTRADICTS relationships with
    critical severity.
    
    Args:
        state: Workflow state with extracted data.
    
    Returns:
        State with updated metadata.
    """
    logger.info("🔨 Building Knowledge Graph")
    
    errors: list[str] = list(state.get("errors", []))
    metadata: dict[str, Any] = dict(state.get("metadata", {}))
    
    clauses = state.get("extracted_clauses", [])
    entities = state.get("extracted_entities", [])
    relationships = state.get("extracted_relationships", [])
    
    if not clauses and not entities:
        logger.warning("No data to build graph from")
        return state
    
    try:
        with GraphBuilder() as gb:
            gb.create_constraints()
            
            # Create Entity nodes
            entity_count = 0
            for entity in entities:
                try:
                    gb.add_entity(entity["name"], entity["type"])
                    entity_count += 1
                except Exception as e:
                    logger.warning(f"Failed to add entity {entity.get('name')}: {e}")
                    errors.append(f"Entity error: {e}")
            
            logger.info(f"Created {entity_count}/{len(entities)} entity nodes")
                
            # Create Clause nodes
            clause_count = 0
            for clause in clauses:
                try:
                    gb.add_clause(
                        clause["id"], 
                        clause.get("text", ""), 
                        clause["topic"]
                    )
                    clause_count += 1
                except Exception as e:
                    logger.warning(f"Failed to add clause {clause.get('id')}: {e}")
                    errors.append(f"Clause error: {e}")
            
            logger.info(f"Created {clause_count}/{len(clauses)} clause nodes")
                
            # Create Relationships and Risk nodes
            rel_count = 0
            risk_count = 0
            
            for rel in relationships:
                try:
                    if rel["type"] == "CONTRADICTS":
                        gb.create_relationship(
                            "Clause", "id", rel["source"],
                            "Clause", "id", rel["target"],
                            "CONTRADICTS",
                            {"reason": rel.get("reason", "")}
                        )
                        rel_count += 1
                        
                        # Create Risk node for critical contradictions
                        if rel.get("severity") == RiskSeverity.CRITICAL.value:
                            risk_id = f"risk-{rel['source']}-{rel['target']}"
                            gb.add_risk(
                                risk_id=risk_id,
                                severity=RiskSeverity.CRITICAL.value,
                                description=rel.get("reason", "Contradicting clauses detected"),
                                clause_id=rel["source"],
                                recommendation="Immediate legal review required."
                            )
                            risk_count += 1
                        
                    elif rel["type"] == "OBLIGATES":
                        gb.create_relationship(
                            "Clause", "id", rel["source"],
                            "Entity", "name", rel["target"],
                            "OBLIGATES"
                        )
                        rel_count += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to create relationship: {e}")
                    errors.append(f"Relationship error: {e}")
            
            logger.info(f"Created {rel_count}/{len(relationships)} relationships")
            if risk_count:
                logger.warning(f"Created {risk_count} risk node(s)")
            
            # Update metadata with graph stats
            metadata["graph_build_timestamp"] = datetime.now().isoformat()
            metadata["nodes_created"] = entity_count + clause_count + risk_count
            metadata["relationships_created"] = rel_count
                
    except Exception as e:
        logger.error(f"Error building graph: {e}")
        errors.append(f"Graph build error: {str(e)}")
        
    return {
        **state,
        "errors": errors,
        "metadata": metadata,
    }

def check_compliance(state: AgentStateDict) -> AgentStateDict:
    """
    Query the knowledge graph for compliance risks.
    
    Traverses the graph to identify:
    - Contradicting clauses
    - High-risk patterns
    - Identified risks with recommendations
    
    Args:
        state: Current workflow state.
    
    Returns:
        Updated state with compliance_report populated.
    """
    logger.info("🔎 Checking Compliance")
    
    errors: list[str] = list(state.get("errors", []))
    metadata: dict[str, Any] = dict(state.get("metadata", {}))
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_lines = [
        "# 📋 Compliance Risk Report",
        "",
        f"> **Generated**: {timestamp}  ",
        f"> **Contract Length**: {metadata.get('text_length', 'N/A')} characters  ",
        f"> **Clauses Analyzed**: {metadata.get('clause_count', 'N/A')}",
        "",
        "---",
        "",
    ]
    
    try:
        with GraphBuilder() as gb:
            # Get contradictions
            contradictions = gb.get_contradictions()
            
            # Get risks
            risks = gb.get_risks()
            
            # Critical findings section
            if contradictions or risks:
                report_lines.append("## 🚨 CRITICAL FINDINGS")
                report_lines.append("")
                
                if contradictions:
                    report_lines.append("### Contradicting Clauses")
                    report_lines.append("")
                    report_lines.append("| # | Clause A | Clause B | Issue |")
                    report_lines.append("|---|----------|----------|-------|")
                    
                    for idx, c in enumerate(contradictions, 1):
                        topic_a = c.get('clause1_topic', 'Unknown')
                        topic_b = c.get('clause2_topic', 'Unknown')
                        reason = c.get('contradiction_reason', 'Conflicting terms')[:50]
                        report_lines.append(
                            f"| {idx} | {topic_a} (#{c['clause1_id']}) | "
                            f"{topic_b} (#{c['clause2_id']}) | {reason}... |"
                        )
                    
                    report_lines.append("")
                    
                    # Detailed breakdown
                    report_lines.append("#### Detailed Analysis")
                    report_lines.append("")
                    
                    for idx, c in enumerate(contradictions, 1):
                        report_lines.append(f"**Conflict #{idx}: {c.get('clause1_topic')} vs {c.get('clause2_topic')}**")
                        report_lines.append("")
                        report_lines.append(f"- **Clause {c['clause1_id']}**: _{c['clause1_text'][:100]}..._")
                        report_lines.append(f"- **Clause {c['clause2_id']}**: _{c['clause2_text'][:100]}..._")
                        if c.get("contradiction_reason"):
                            report_lines.append(f"- **Analysis**: {c['contradiction_reason']}")
                        report_lines.append("")
                
                if risks:
                    report_lines.append("### Identified Risks")
                    report_lines.append("")
                    
                    for risk in risks:
                        severity = risk.get('severity', 'unknown').upper()
                        emoji = {
                            "CRITICAL": "🔴",
                            "HIGH": "🟠",
                            "MEDIUM": "🟡",
                            "LOW": "🟢",
                        }.get(severity, "⚪")
                        
                        report_lines.append(f"{emoji} **{severity}**: {risk.get('description', 'N/A')}")
                        report_lines.append(f"   - Related Clause: #{risk.get('clause_id')} ({risk.get('clause_topic', 'N/A')})")
                        if risk.get('recommendation'):
                            report_lines.append(f"   - 💡 Recommendation: {risk['recommendation']}")
                        report_lines.append("")
                
                # Recommendations
                report_lines.append("---")
                report_lines.append("")
                report_lines.append("## 💡 Recommendations")
                report_lines.append("")
                report_lines.append("1. **Immediate Legal Review**: Critical contradictions require expert analysis.")
                report_lines.append("2. **Reconcile Conflicting Terms**: Clarify which clause takes precedence.")
                report_lines.append("3. **Add Precedence Language**: Include a clause specifying order of precedence.")
                report_lines.append("4. **Scope Clarification**: Define clear boundaries for indemnification obligations.")
                
                metadata["critical_issues"] = len(contradictions) + len([r for r in risks if r.get('severity') == 'critical'])
                
            else:
                report_lines.append("## ✅ No Critical Issues Found")
                report_lines.append("")
                report_lines.append("The contract analysis did not identify any contradicting clauses or critical risks.")
                report_lines.append("")
                report_lines.append("**Note**: This automated analysis may not catch all issues. ")
                report_lines.append("Human review is still recommended for important contracts.")
                metadata["critical_issues"] = 0
            
            # Footer
            report_lines.append("")
            report_lines.append("---")
            report_lines.append("")
            report_lines.append("*This report was generated by GraphRAG Legal Auditor. ")
            report_lines.append("For complex legal matters, consult with qualified legal counsel.*")
                
    except Exception as e:
        logger.error(f"Error checking compliance: {e}")
        errors.append(f"Compliance check error: {str(e)}")
        report_lines.append("## ❌ Error During Analysis")
        report_lines.append("")
        report_lines.append(f"An error occurred during the compliance check:")
        report_lines.append(f"```\n{e}\n```")
        report_lines.append("")
        report_lines.append("Please ensure Neo4j is running and try again.")
    
    metadata["compliance_check_timestamp"] = datetime.now().isoformat()
    
    return {
        **state, 
        "compliance_report": "\n".join(report_lines),
        "errors": errors,
        "metadata": metadata,
    }

def generate_report(state: AgentStateDict) -> AgentStateDict:
    """
    Finalize and format the compliance report.
    
    This is the terminal node in the workflow. Logs summary statistics
    and prepares the final state.
    
    Args:
        state: Final workflow state with compliance_report.
    
    Returns:
        Final state with updated metadata.
    """
    logger.info("📄 Generating Final Report")
    
    metadata: dict[str, Any] = dict(state.get("metadata", {}))
    errors = state.get("errors", [])
    report = state.get("compliance_report", "")
    
    # Log summary statistics
    has_critical = "CRITICAL" in report or metadata.get("critical_issues", 0) > 0
    
    if has_critical:
        logger.warning("⚠️  Report contains CRITICAL findings")
    else:
        logger.info("✅ Report completed with no critical issues")
    
    if errors:
        logger.warning(f"⚠️  {len(errors)} error(s) occurred during processing")
    
    # Final metadata
    metadata["report_generated_at"] = datetime.now().isoformat()
    metadata["has_critical_findings"] = has_critical
    metadata["error_count"] = len(errors)
    
    return {
        **state,
        "metadata": metadata,
    }


# =============================================================================
# WORKFLOW DEFINITION
# =============================================================================

def set_extractor(extractor: ContractExtractor) -> None:
    """
    Set the contract extractor to use.
    
    Allows swapping between MockExtractor and LLMExtractor.
    
    Args:
        extractor: An object implementing the ContractExtractor protocol.
    """
    global _extractor
    _extractor = extractor


def create_workflow() -> StateGraph:
    """
    Create and configure the compliance analysis workflow.
    
    The workflow consists of four nodes:
    1. extract_entities: Parse contract text and identify elements
    2. build_graph: Store elements in Neo4j knowledge graph
    3. check_compliance: Query graph for risks and contradictions
    4. generate_report: Format and finalize the compliance report
    
    Returns:
        Configured StateGraph ready for compilation.
    """
    wf = StateGraph(AgentStateDict)
    
    # Add nodes
    wf.add_node("extract_entities", extract_entities)
    wf.add_node("build_graph", build_graph)
    wf.add_node("check_compliance", check_compliance)
    wf.add_node("generate_report", generate_report)
    
    # Define entry point
    wf.set_entry_point("extract_entities")
    
    # Define edges (linear pipeline)
    wf.add_edge("extract_entities", "build_graph")
    wf.add_edge("build_graph", "check_compliance")
    wf.add_edge("check_compliance", "generate_report")
    wf.add_edge("generate_report", END)
    
    return wf


def create_initial_state(raw_text: str) -> AgentStateDict:
    """
    Create a properly initialized state for the workflow.
    
    Args:
        raw_text: The contract text to analyze.
    
    Returns:
        Initial AgentStateDict ready for workflow invocation.
    """
    return {
        "raw_text": raw_text,
        "extracted_clauses": [],
        "extracted_entities": [],
        "extracted_relationships": [],
        "compliance_report": "",
        "errors": [],
        "metadata": {
            "created_at": datetime.now().isoformat(),
        },
    }


# Create and compile the workflow
workflow = create_workflow()
app = workflow.compile()


__all__ = [
    "AgentState",
    "AgentStateDict",
    "ContractExtractor",
    "MockExtractor",
    "create_workflow",
    "create_initial_state",
    "set_extractor",
    "app",
    "workflow",
]
