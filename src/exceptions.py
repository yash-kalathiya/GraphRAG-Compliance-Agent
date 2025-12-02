"""
Custom exceptions for the GraphRAG Legal Auditor.

This module provides a hierarchy of domain-specific exceptions
for better error handling and debugging.
"""

from __future__ import annotations

from typing import Optional


class GraphRAGException(Exception):
    """
    Base exception for all GraphRAG-related errors.
    
    Attributes:
        message: Human-readable error message.
        details: Optional additional context for debugging.
    """
    
    def __init__(self, message: str, details: Optional[dict] = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class DatabaseConnectionError(GraphRAGException):
    """Raised when connection to Neo4j fails."""
    
    def __init__(
        self, 
        message: str = "Failed to connect to Neo4j database",
        uri: Optional[str] = None,
    ) -> None:
        details = {"uri": uri} if uri else {}
        super().__init__(message, details)


class GraphBuildError(GraphRAGException):
    """Raised when graph construction fails."""
    
    def __init__(
        self,
        message: str = "Failed to build knowledge graph",
        node_type: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> None:
        details = {}
        if node_type:
            details["node_type"] = node_type
        if node_id:
            details["node_id"] = node_id
        super().__init__(message, details)


class ComplianceCheckError(GraphRAGException):
    """Raised when compliance checking fails."""
    
    def __init__(
        self,
        message: str = "Failed to perform compliance check",
        query: Optional[str] = None,
    ) -> None:
        details = {"query": query} if query else {}
        super().__init__(message, details)


class ExtractionError(GraphRAGException):
    """Raised when entity/clause extraction fails."""
    
    def __init__(
        self,
        message: str = "Failed to extract entities from text",
        text_sample: Optional[str] = None,
    ) -> None:
        details = {}
        if text_sample:
            # Truncate for readability
            details["text_sample"] = text_sample[:100] + "..." if len(text_sample) > 100 else text_sample
        super().__init__(message, details)


class ValidationError(GraphRAGException):
    """Raised when data validation fails."""
    
    def __init__(
        self,
        message: str = "Data validation failed",
        field: Optional[str] = None,
        value: Optional[str] = None,
    ) -> None:
        details = {}
        if field:
            details["field"] = field
        if value:
            details["value"] = str(value)
        super().__init__(message, details)
