# GraphRAG Legal Auditor: Graph-Native Compliance Agent

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.15-008CC1?logo=neo4j)](https://neo4j.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.0.10+-green.svg)](https://github.com/langchain-ai/langgraph)

![Graph Visualization](docs/graph_viz.png)

A production-grade **GraphRAG (Retrieval-Augmented Generation)** system designed to audit legal contracts for compliance risks. By leveraging **Knowledge Graphs** instead of simple vector similarity, this agent can detect complex logical contradictions (e.g., an *Indemnity* clause conflicting with a *Liability Cap*) that standard RAG systems often miss.

## 🚀 How it Works

### The Problem with Standard RAG
Standard RAG retrieves text chunks based on semantic similarity. If you ask "Is there a liability cap?", it finds the clause. However, if you ask "Does the indemnity clause contradict the liability cap?", standard RAG fails because it lacks the **structural understanding** of how clauses relate to one another.

### The GraphRAG Advantage
This system parses the contract into a **Knowledge Graph** stored in **Neo4j**:
- **Nodes**: `Clause`, `Entity` (e.g., "Developer", "Client"), `Risk`.
- **Edges**: `CONTRADICTS`, `REFERS_TO`, `OBLIGATES`.

By traversing these relationships, the agent can explicitly "see" that Clause 1 (Unlimited Indemnity) has a `CONTRADICTS` relationship with Clause 2 (Liability Cap), allowing for deterministic and accurate risk reporting.

## 🛠️ Tech Stack

- **Orchestration**: [LangGraph](https://github.com/langchain-ai/langgraph) for multi-agent state management.
- **Database**: [Neo4j](https://neo4j.com/) for graph storage and traversal.
- **Vector Store**: [LanceDB](https://lancedb.com/) for hybrid search (semantic + keyword).
- **LLM Integration**: [LangChain](https://github.com/langchain-ai/langchain) + OpenAI/Groq.
- **Protocol**: Model Context Protocol (MCP) ready.

## 📦 Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.10+

### 1. Clone and Install
```bash
git clone https://github.com/your-repo/graphrag-legal-auditor.git
cd graphrag-legal-auditor
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Start Neo4j
Spin up the graph database using Docker:
```bash
docker-compose up -d
```
*Wait about 10-20 seconds for Neo4j to fully initialize.*

### 3. Configure Environment
Create a `.env` file (optional, defaults are set for local dev):
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
OPENAI_API_KEY=sk-...
```

## 🏃‍♂️ Run the Demo

We have included a mock contract with a deliberate contradiction between the **Indemnification** and **Limitation of Liability** clauses.

Run the full pipeline:
```bash
python run_demo.py
```

### Expected Output
```text
Starting GraphRAG Compliance Agent Demo...
Loaded contract text (850 chars).
Resetting Neo4j database...
Running LangGraph Workflow...
--- Extracting Entities & Clauses ---
--- Building Knowledge Graph ---
--- Checking Compliance ---
--- Generating Final Report ---

========================================
# Compliance Risk Report

## CRITICAL: Contradictions Detected
- **Conflict**: Clause 1 contradicts Clause 2
  - *Clause 1*: The Developer agrees to indemnify...
  - *Clause 2*: Notwithstanding any other provision...
========================================
Demo Complete.
```

## 📂 Project Structure

```
graphrag-legal-auditor/
├── .vscode/               # VS Code settings & debug configs
├── config/
│   ├── __init__.py
│   └── settings.py        # Pydantic settings management
├── data/
│   └── sample_contract.txt
├── docs/                  # Documentation assets
├── notebooks/
│   └── exploration.ipynb  # Interactive graph exploration
├── src/
│   ├── __init__.py        # Package exports
│   ├── exceptions.py      # Custom exception hierarchy
│   ├── graph_builder.py   # Neo4j interaction logic
│   ├── models.py          # Pydantic domain models
│   └── workflow.py        # LangGraph agent definitions
├── tests/
│   ├── conftest.py        # Pytest fixtures
│   ├── test_graph_builder.py
│   ├── test_models.py
│   └── test_workflow.py
├── .env.example           # Environment template
├── .gitignore
├── .pre-commit-config.yaml
├── CONTRIBUTING.md        # Contribution guidelines
├── docker-compose.yml     # Neo4j container config
├── LICENSE
├── Makefile               # Development commands
├── pyproject.toml         # Modern Python packaging
├── README.md
├── requirements.txt
└── run_demo.py            # CLI entry point
```

## 🧪 Development

### Quick Commands

```bash
make help           # Show all available commands
make dev-install    # Install with dev dependencies
make test           # Run test suite
make test-cov       # Run tests with coverage
make lint           # Run linter
make format         # Format code
make check-all      # Run all checks (lint, type, test)
```

### Running Tests

```bash
# Unit tests (no external dependencies)
make test-unit

# Integration tests (requires Neo4j)
make test-integration

# With coverage report
make test-cov
```

## 🔮 Future Roadmap
- [ ] Integrate **LanceDB** for hybrid search on large contract repositories.
- [ ] Add **Groq** support for ultra-fast inference.
- [ ] Build a **Streamlit** frontend for interactive graph visualization.
- [ ] Add PDF parsing with `pdfplumber` or `PyMuPDF`.
- [ ] Implement MCP (Model Context Protocol) server.

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
