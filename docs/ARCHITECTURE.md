# 🏗️ Architecture Overview

This document describes the architecture of the GraphRAG Legal Auditor system.

## System Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GraphRAG Legal Auditor                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │  run_demo.py │───▶│   Workflow   │───▶│    GraphBuilder      │   │
│  │   (CLI)      │    │  (LangGraph) │    │     (Neo4j)          │   │
│  └──────────────┘    └──────────────┘    └──────────────────────┘   │
│         │                   │                       │               │
│         ▼                   ▼                       ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │    Config    │    │  Extractor   │    │   Neo4j Database     │   │
│  │  (Pydantic)  │    │  (Protocol)  │    │   (Docker)           │   │
│  └──────────────┘    └──────────────┘    └──────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Module Responsibilities

### `src/graph_builder.py`
**Purpose**: Neo4j knowledge graph management

Key features:
- **Connection Pooling**: Singleton `_DriverPool` for efficient connection reuse
- **Retry Logic**: `@retry_on_transient` decorator handles transient failures
- **Security**: Input validation and whitelisted labels/relationships
- **CRUD Operations**: `add_clause()`, `add_entity()`, `add_risk()`, `create_relationship()`
- **Queries**: `get_contradictions()`, `get_risks()`, `get_graph_stats()`

```python
# Usage
with GraphBuilder() as gb:
    gb.add_clause("1", "Contract text...", "Indemnification")
    gb.create_relationship("Clause", "id", "1", "Entity", "name", "Acme", "OBLIGATES")
```

### `src/workflow.py`
**Purpose**: LangGraph workflow orchestration

Pipeline stages:
1. **extract_entities**: Parse contract → clauses, entities, relationships
2. **build_graph**: Store elements in Neo4j
3. **check_compliance**: Query for contradictions and risks
4. **generate_report**: Format markdown compliance report

Key patterns:
- **Protocol-based Extraction**: `ContractExtractor` protocol allows swapping extractors
- **State Management**: `AgentStateDict` tracks workflow state
- **Error Collection**: Errors accumulated in `state["errors"]`

### `src/models.py`
**Purpose**: Pydantic domain models

Models:
- `Clause`: Contract clause with ID, text, topic
- `Entity`: Party or organization in contract
- `Risk`: Identified compliance risk with severity
- `Relationship`: Connection between elements
- `ContractAnalysis`: Complete analysis result

### `src/exceptions.py`
**Purpose**: Custom exception hierarchy

```
GraphRAGException (base)
├── DatabaseConnectionError
├── GraphBuildError
├── ComplianceCheckError
├── ExtractionError
└── ValidationError
```

### `config/settings.py`
**Purpose**: Configuration management via Pydantic Settings

Environment variables:
- `NEO4J_URI`: Neo4j connection string
- `NEO4J_USER`, `NEO4J_PASSWORD`: Authentication
- `OPENAI_API_KEY`: For LLM extraction (production)
- `LOG_LEVEL`: Logging verbosity

## Data Flow

```
Contract Text
     │
     ▼
┌─────────────────────┐
│  MockExtractor /    │  Pattern matching or LLM-based
│  LLMExtractor       │
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│  Clauses            │  [{id, text, topic}, ...]
│  Entities           │  [{name, type}, ...]
│  Relationships      │  [{source, target, type}, ...]
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│  Neo4j Graph        │  Knowledge graph with typed nodes/edges
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│  Contradiction      │  CYPHER query for CONTRADICTS relationships
│  Detection          │
└─────────────────────┘
     │
     ▼
┌─────────────────────┐
│  Compliance Report  │  Markdown formatted with findings
└─────────────────────┘
```

## Neo4j Graph Schema

### Node Types

```cypher
(:Clause {
  id: string,           -- Unique identifier
  text: string,         -- Full clause text
  topic: string,        -- Category (Indemnification, Liability, etc.)
  section_number: string?,
  page_number: int?,
  updated_at: datetime
})

(:Entity {
  name: string,         -- Entity name
  type: string,         -- Party, Organization, etc.
  updated_at: datetime
})

(:Risk {
  id: string,
  severity: string,     -- low, medium, high, critical
  description: string,
  recommendation: string?,
  updated_at: datetime
})
```

### Relationship Types

```cypher
(Clause)-[:CONTRADICTS {reason: string}]->(Clause)
(Clause)-[:OBLIGATES]->(Entity)
(Clause)-[:HAS_RISK]->(Risk)
(Clause)-[:REFERENCES]->(Clause)
(Entity)-[:PARTY_TO]->(Clause)
```

## Security Considerations

### Input Validation
- All identifiers validated with `IDENTIFIER_PATTERN = r"^[a-zA-Z0-9_-]+$"`
- Labels and relationship types validated against whitelists
- Cypher injection prevented through parameterized queries

### Connection Management
- Connection pooling prevents resource exhaustion
- Automatic retry on transient failures
- Health check endpoint for monitoring

## Extending the System

### Custom Extractor
```python
from src.workflow import ContractExtractor, set_extractor

class LLMExtractor:
    def __init__(self, model: str = "gpt-4"):
        self.model = model
    
    def extract(self, text: str) -> tuple[list, list, list]:
        # Use LangChain + OpenAI for extraction
        ...
        return clauses, entities, relationships

# Set the custom extractor
set_extractor(LLMExtractor())
```

### Adding New Node Types
1. Add to `VALID_LABELS` in `graph_builder.py`
2. Create `add_<nodetype>()` method
3. Update models in `models.py`

### Adding New Relationships
1. Add to `VALID_RELATIONSHIP_TYPES` in `graph_builder.py`
2. Update extraction logic in `MockExtractor._detect_*()` methods

## Testing Strategy

### Unit Tests
- Mock Neo4j driver with `unittest.mock`
- Test individual workflow nodes in isolation
- Validate Pydantic model constraints

### Integration Tests
- Use testcontainers for Neo4j instance
- Test full workflow end-to-end
- Validate graph structure after operations

### Running Tests
```bash
# Unit tests only
make test

# With coverage
make coverage

# Type checking
make lint
```

## Performance Considerations

1. **Connection Pooling**: Single driver instance shared across GraphBuilder instances
2. **Batch Operations**: Consider `UNWIND` for bulk inserts in production
3. **Index Usage**: Constraints create automatic indexes on `id`/`name` fields
4. **Retry Logic**: Exponential backoff prevents thundering herd on failures
