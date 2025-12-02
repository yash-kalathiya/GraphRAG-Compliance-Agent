"""
Neo4j Graph Builder for Legal Contract Analysis.

This module provides a high-level interface for constructing and querying
a knowledge graph of legal contract elements (clauses, entities, risks)
and their relationships.

Features:
    - Connection pooling with singleton pattern
    - Automatic retry logic for transient failures
    - Thread-safe operations
    - Parameterized queries (no injection vulnerabilities)

Example:
    >>> with GraphBuilder() as gb:
    ...     gb.add_clause("1", "Indemnity clause text", "Indemnification")
    ...     gb.add_entity("Acme Corp", "Party")
    ...     contradictions = gb.get_contradictions()
"""

from __future__ import annotations

import logging
import re
import time
from contextlib import contextmanager
from functools import wraps
from threading import Lock
from typing import Any, Callable, Iterator, TypeVar

from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import ServiceUnavailable, AuthError, TransientError

from config.settings import settings
from src.exceptions import DatabaseConnectionError, GraphBuildError, ValidationError

logger = logging.getLogger(__name__)

# Type variable for generic retry decorator
T = TypeVar("T")

# Valid node labels (whitelist for security)
VALID_LABELS = frozenset({"Clause", "Entity", "Risk", "Party", "Organization"})
VALID_RELATIONSHIP_TYPES = frozenset({
    "CONTRADICTS", "REFERS_TO", "OBLIGATES", "MODIFIES", "SUPERSEDES", "HAS_RISK"
})

# Regex for valid identifiers (alphanumeric + underscore)
IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def retry_on_transient(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 5.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that retries a function on transient database errors.
    
    Uses exponential backoff with jitter for retry delays.
    
    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (TransientError, ServiceUnavailable) as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            f"Transient error on attempt {attempt + 1}/{max_retries + 1}, "
                            f"retrying in {delay:.2f}s: {e}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"Max retries exceeded: {e}")
            
            raise last_exception  # type: ignore
        return wrapper
    return decorator


class _DriverPool:
    """
    Thread-safe singleton for Neo4j driver connection pooling.
    
    Ensures only one driver instance exists per URI, reducing
    connection overhead and improving performance.
    """
    
    _instance: "_DriverPool | None" = None
    _lock: Lock = Lock()
    _drivers: dict[str, Driver] = {}
    
    def __new__(cls) -> "_DriverPool":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_driver(self, uri: str, user: str, password: str) -> Driver:
        """Get or create a driver for the given URI."""
        if uri not in self._drivers:
            with self._lock:
                if uri not in self._drivers:
                    driver = GraphDatabase.driver(uri, auth=(user, password))
                    driver.verify_connectivity()
                    self._drivers[uri] = driver
                    logger.info(f"Created new driver for {uri}")
        return self._drivers[uri]
    
    def close_all(self) -> None:
        """Close all pooled drivers."""
        with self._lock:
            for uri, driver in self._drivers.items():
                driver.close()
                logger.debug(f"Closed driver for {uri}")
            self._drivers.clear()


# Global driver pool instance
_driver_pool = _DriverPool()


def validate_identifier(value: str, field_name: str) -> str:
    """
    Validate that a string is a safe identifier.
    
    Args:
        value: The string to validate.
        field_name: Name of the field (for error messages).
    
    Returns:
        The validated string.
    
    Raises:
        ValidationError: If the string is not a valid identifier.
    """
    if not value or not IDENTIFIER_PATTERN.match(value):
        raise ValidationError(
            message=f"Invalid {field_name}: must be alphanumeric with underscores",
            field=field_name,
            value=value
        )
    return value


class GraphBuilder:
    """
    High-level interface for Neo4j graph operations.
    
    Manages the lifecycle of Neo4j connections and provides methods for
    creating nodes (Clause, Entity, Risk) and relationships (CONTRADICTS,
    REFERS_TO, OBLIGATES) in the knowledge graph.
    
    Supports context manager protocol for safe resource cleanup.
    Uses connection pooling for efficiency.
    
    Attributes:
        driver: Neo4j driver instance for database connections.
    
    Example:
        >>> with GraphBuilder() as builder:
        ...     builder.add_clause("1", "Sample text", "Liability")
    """
    
    _use_pool: bool = True  # Class-level flag for testing
    
    def __init__(self, *, use_pool: bool = True) -> None:
        """
        Initialize GraphBuilder with Neo4j connection.
        
        Args:
            use_pool: Whether to use connection pooling (disable for tests).
        """
        self._closed = False
        self._owns_driver = not use_pool
        
        try:
            if use_pool:
                self._driver = _driver_pool.get_driver(
                    settings.NEO4J_URI,
                    settings.NEO4J_USER,
                    settings.NEO4J_PASSWORD
                )
            else:
                self._driver = GraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
                )
                self._driver.verify_connectivity()
            logger.debug(f"Connected to Neo4j at {settings.NEO4J_URI}")
        except (ServiceUnavailable, AuthError) as e:
            raise DatabaseConnectionError(
                message=f"Failed to connect to Neo4j: {e}",
                uri=settings.NEO4J_URI
            ) from e
    
    def __enter__(self) -> "GraphBuilder":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit with cleanup."""
        self.close()
    
    def __repr__(self) -> str:
        status = "closed" if self._closed else "open"
        return f"<GraphBuilder uri={settings.NEO4J_URI!r} status={status}>"
    
    @property
    def driver(self) -> Driver:
        """Access the underlying Neo4j driver."""
        if self._closed:
            raise RuntimeError("GraphBuilder is closed")
        return self._driver
    
    @property
    def is_closed(self) -> bool:
        """Check if the builder has been closed."""
        return self._closed
    
    @contextmanager
    def _session(self) -> Iterator[Session]:
        """Create a managed session context."""
        if self._closed:
            raise RuntimeError("GraphBuilder is closed")
        session = self._driver.session()
        try:
            yield session
        finally:
            session.close()

    def close(self) -> None:
        """
        Close the GraphBuilder.
        
        If using connection pooling, only marks this instance as closed.
        If not using pooling, also closes the driver.
        """
        if not self._closed:
            self._closed = True
            if self._owns_driver and self._driver:
                self._driver.close()
                logger.debug("Neo4j driver closed.")
            logger.debug("GraphBuilder closed.")

    def clear_database(self) -> None:
        """
        Remove all nodes and relationships from the database.
        
        Warning:
            This operation is destructive and cannot be undone.
            Use with caution in production environments.
        """
        with self._session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Database cleared.")

    @retry_on_transient(max_retries=3)
    def create_constraints(self) -> None:
        """
        Create uniqueness constraints for graph integrity.
        
        Creates constraints on:
        - Clause.id: Ensures unique clause identifiers
        - Entity.name: Ensures unique entity names
        - Risk.id: Ensures unique risk identifiers
        
        This operation is idempotent and safe to call multiple times.
        """
        constraints = [
            ("clause_id_unique", "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Clause) REQUIRE c.id IS UNIQUE"),
            ("entity_name_unique", "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE"),
            ("risk_id_unique", "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Risk) REQUIRE r.id IS UNIQUE"),
        ]
        
        with self._session() as session:
            for name, query in constraints:
                session.run(query)
                logger.debug(f"Constraint '{name}' ensured.")
        
        logger.info(f"Ensured {len(constraints)} database constraints.")

    @retry_on_transient(max_retries=3)
    def add_clause(
        self, 
        clause_id: str, 
        text: str, 
        topic: str,
        *,
        section_number: str | None = None,
        page_number: int | None = None,
    ) -> None:
        """
        Add or update a Clause node in the graph.
        
        Uses MERGE to create the node if it doesn't exist, or update
        its properties if it does.
        
        Args:
            clause_id: Unique identifier for the clause.
            text: Full text content of the clause.
            topic: Subject matter category (e.g., "Indemnification").
            section_number: Optional section reference.
            page_number: Optional page number in source document.
        
        Raises:
            GraphBuildError: If the clause cannot be added.
            ValidationError: If inputs are invalid.
        """
        if not clause_id or not clause_id.strip():
            raise ValidationError("Clause ID cannot be empty", field="clause_id")
        if not text or not text.strip():
            raise ValidationError("Clause text cannot be empty", field="text")
        
        query = """
        MERGE (c:Clause {id: $id})
        SET c.text = $text, 
            c.topic = $topic, 
            c.section_number = $section_number,
            c.page_number = $page_number,
            c.updated_at = datetime()
        """
        try:
            with self._session() as session:
                session.run(
                    query, 
                    id=clause_id.strip(), 
                    text=text, 
                    topic=topic,
                    section_number=section_number,
                    page_number=page_number,
                )
            logger.debug(f"Added clause: {clause_id} ({topic})")
        except (TransientError, ServiceUnavailable):
            raise  # Let retry decorator handle these
        except Exception as e:
            raise GraphBuildError(
                message=f"Failed to add clause: {e}",
                node_type="Clause",
                node_id=clause_id
            ) from e

    @retry_on_transient(max_retries=3)
    def add_entity(self, name: str, entity_type: str) -> None:
        """
        Add or update an Entity node in the graph.
        
        Args:
            name: Name of the entity (e.g., "Acme Corporation").
            entity_type: Type classification (e.g., "Party", "Organization").
        
        Raises:
            GraphBuildError: If the entity cannot be added.
            ValidationError: If inputs are invalid.
        """
        if not name or not name.strip():
            raise ValidationError("Entity name cannot be empty", field="name")
        
        query = """
        MERGE (e:Entity {name: $name})
        SET e.type = $type, e.updated_at = datetime()
        """
        try:
            with self._session() as session:
                session.run(query, name=name.strip(), type=entity_type)
            logger.debug(f"Added entity: {name} ({entity_type})")
        except (TransientError, ServiceUnavailable):
            raise  # Let retry decorator handle these
        except Exception as e:
            raise GraphBuildError(
                message=f"Failed to add entity: {e}",
                node_type="Entity",
                node_id=name
            ) from e

    @retry_on_transient(max_retries=3)
    def add_risk(
        self,
        risk_id: str,
        severity: str,
        description: str,
        clause_id: str,
        *,
        recommendation: str | None = None,
    ) -> None:
        """
        Add a Risk node and link it to a Clause.
        
        Args:
            risk_id: Unique identifier for the risk.
            severity: Risk severity level (low, medium, high, critical).
            description: Detailed description of the risk.
            clause_id: ID of the clause this risk relates to.
            recommendation: Optional remediation suggestion.
        
        Raises:
            GraphBuildError: If the risk cannot be added.
            ValidationError: If severity is invalid.
        """
        valid_severities = {"low", "medium", "high", "critical"}
        if severity.lower() not in valid_severities:
            raise ValidationError(
                f"Invalid severity: must be one of {valid_severities}",
                field="severity",
                value=severity
            )
        
        query = """
        MERGE (r:Risk {id: $risk_id})
        SET r.severity = $severity,
            r.description = $description,
            r.recommendation = $recommendation,
            r.updated_at = datetime()
        WITH r
        MATCH (c:Clause {id: $clause_id})
        MERGE (c)-[:HAS_RISK]->(r)
        """
        try:
            with self._session() as session:
                session.run(
                    query,
                    risk_id=risk_id,
                    severity=severity.lower(),
                    description=description,
                    recommendation=recommendation,
                    clause_id=clause_id,
                )
            logger.debug(f"Added risk: {risk_id} -> clause {clause_id}")
        except (TransientError, ServiceUnavailable):
            raise
        except Exception as e:
            raise GraphBuildError(
                message=f"Failed to add risk: {e}",
                node_type="Risk",
                node_id=risk_id
            ) from e

    @retry_on_transient(max_retries=3)
    def create_relationship(
        self,
        source_label: str,
        source_key: str,
        source_val: str,
        target_label: str,
        target_key: str,
        target_val: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """
        Create a relationship between two nodes.
        
        This method creates a directed relationship from a source node
        to a target node. Both nodes must already exist in the graph.
        
        Security:
            Labels and relationship types are validated against whitelists
            to prevent Cypher injection attacks.
        
        Args:
            source_label: Label of the source node (e.g., "Clause").
            source_key: Property key to match source (e.g., "id").
            source_val: Value of the source key.
            target_label: Label of the target node.
            target_key: Property key to match target.
            target_val: Value of the target key.
            rel_type: Type of relationship (e.g., "CONTRADICTS").
            properties: Optional properties to set on the relationship.
        
        Raises:
            ValidationError: If labels or rel_type are invalid.
            GraphBuildError: If the relationship cannot be created.
        
        Example:
            >>> gb.create_relationship(
            ...     "Clause", "id", "1",
            ...     "Clause", "id", "2",
            ...     "CONTRADICTS",
            ...     {"reason": "Unlimited vs capped liability"}
            ... )
        """
        # Security: Validate labels against whitelist
        if source_label not in VALID_LABELS:
            raise ValidationError(
                f"Invalid source label: {source_label}. Must be one of {VALID_LABELS}",
                field="source_label",
                value=source_label
            )
        if target_label not in VALID_LABELS:
            raise ValidationError(
                f"Invalid target label: {target_label}. Must be one of {VALID_LABELS}",
                field="target_label",
                value=target_label
            )
        if rel_type not in VALID_RELATIONSHIP_TYPES:
            raise ValidationError(
                f"Invalid relationship type: {rel_type}. Must be one of {VALID_RELATIONSHIP_TYPES}",
                field="rel_type",
                value=rel_type
            )
        
        # Validate property keys (prevent injection via property names)
        if properties:
            for key in properties.keys():
                validate_identifier(key, "property_key")
        
        # Validate key names
        validate_identifier(source_key, "source_key")
        validate_identifier(target_key, "target_key")
        
        # Build properties string for Cypher (now safe after validation)
        props_str = ""
        if properties:
            props_list = [f"{k}: ${k}" for k in properties.keys()]
            props_str = " {" + ", ".join(props_list) + "}"
        
        # Labels and rel_type are now validated, safe to interpolate
        query = f"""
        MATCH (a:{source_label} {{{source_key}: $source_val}})
        MATCH (b:{target_label} {{{target_key}: $target_val}})
        MERGE (a)-[r:{rel_type}{props_str}]->(b)
        SET r.created_at = datetime()
        """
        
        params: dict[str, Any] = {"source_val": source_val, "target_val": target_val}
        if properties:
            params.update(properties)

        try:
            with self._session() as session:
                session.run(query, **params)
            logger.debug(f"Created relationship: ({source_val})-[{rel_type}]->({target_val})")
        except (TransientError, ServiceUnavailable):
            raise
        except Exception as e:
            raise GraphBuildError(
                message=f"Failed to create relationship: {e}",
                node_type=f"{source_label}->{target_label}"
            ) from e

    @retry_on_transient(max_retries=3)
    def get_contradictions(self) -> list[dict[str, Any]]:
        """
        Find all contradicting clause pairs in the graph.
        
        Returns:
            List of dictionaries containing clause pairs and their texts.
            Each dict has keys: clause1_id, clause1_text, clause2_id, clause2_text.
        
        Example:
            >>> contradictions = gb.get_contradictions()
            >>> for c in contradictions:
            ...     print(f"Clause {c['clause1_id']} contradicts {c['clause2_id']}")
        """
        query = """
        MATCH (c1:Clause)-[r:CONTRADICTS]->(c2:Clause)
        RETURN c1.id AS clause1_id, 
               c1.text AS clause1_text,
               c1.topic AS clause1_topic,
               c2.id AS clause2_id, 
               c2.text AS clause2_text,
               c2.topic AS clause2_topic,
               r.reason AS contradiction_reason
        ORDER BY c1.id
        """
        with self._session() as session:
            result = session.run(query)
            return [record.data() for record in result]

    @retry_on_transient(max_retries=3)
    def get_risks(self) -> list[dict[str, Any]]:
        """
        Retrieve all identified risks and their associated clauses.
        
        Returns:
            List of risk records with severity, description, and clause_id.
        """
        query = """
        MATCH (r:Risk)<-[:HAS_RISK]-(c:Clause)
        RETURN r.id AS risk_id,
               r.severity AS severity, 
               r.description AS description,
               r.recommendation AS recommendation,
               c.id AS clause_id,
               c.topic AS clause_topic
        ORDER BY 
            CASE r.severity 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                WHEN 'medium' THEN 3 
                ELSE 4 
            END
        """
        with self._session() as session:
            result = session.run(query)
            return [record.data() for record in result]
    
    @retry_on_transient(max_retries=3)
    def get_graph_stats(self) -> dict[str, int]:
        """
        Get statistics about the current graph.
        
        Returns:
            Dictionary with counts of nodes by label.
        """
        query = """
        MATCH (n)
        WITH labels(n) AS labels, count(*) AS count
        UNWIND labels AS label
        RETURN label, sum(count) AS node_count
        """
        stats: dict[str, int] = {}
        with self._session() as session:
            result = session.run(query)
            for record in result:
                stats[record["label"]] = record["node_count"]
        return stats
    
    def health_check(self) -> dict[str, Any]:
        """
        Check the health of the database connection.
        
        Returns:
            Dictionary with connection status and database info.
        """
        try:
            with self._session() as session:
                result = session.run("CALL dbms.components()")
                record = result.single()
                return {
                    "status": "healthy",
                    "name": record["name"] if record else "unknown",
                    "version": record["versions"][0] if record else "unknown",
                    "uri": settings.NEO4J_URI,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "uri": settings.NEO4J_URI,
            }
