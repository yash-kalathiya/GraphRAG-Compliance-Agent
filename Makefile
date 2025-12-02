.PHONY: help install dev-install test lint format type-check clean docker-up docker-down demo

# Default target
help:
	@echo "GraphRAG Legal Auditor - Available Commands"
	@echo "============================================"
	@echo ""
	@echo "Setup:"
	@echo "  make install       Install production dependencies"
	@echo "  make dev-install   Install with dev dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make test          Run test suite"
	@echo "  make test-cov      Run tests with coverage report"
	@echo "  make lint          Run linter (ruff)"
	@echo "  make format        Format code (black + ruff)"
	@echo "  make type-check    Run type checker (mypy)"
	@echo "  make check-all     Run all checks (lint, type, test)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up     Start Neo4j container"
	@echo "  make docker-down   Stop Neo4j container"
	@echo "  make docker-logs   View Neo4j logs"
	@echo ""
	@echo "Run:"
	@echo "  make demo          Run the demo script"
	@echo "  make clean         Remove cache and build artifacts"

# Installation
install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"
	pre-commit install

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

test-unit:
	pytest tests/ -v -m unit

test-integration:
	pytest tests/ -v -m integration

# Code Quality
lint:
	ruff check src/ tests/ --fix

format:
	black src/ tests/ run_demo.py
	ruff check src/ tests/ --fix

type-check:
	mypy src/

check-all: lint type-check test

# Docker
docker-up:
	docker-compose up -d
	@echo "Waiting for Neo4j to start..."
	@sleep 10
	@echo "Neo4j is ready at http://localhost:7474"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f neo4j

docker-clean:
	docker-compose down -v
	rm -rf data/neo4j

# Run
demo: docker-up
	@sleep 5
	python run_demo.py

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ .coverage
