#!/usr/bin/env python3
"""
GraphRAG Legal Auditor - Demo Runner

This script demonstrates the full compliance analysis pipeline:
1. Load a sample contract with known contradictions
2. Reset the Neo4j database
3. Run the LangGraph workflow
4. Output the compliance risk report

Usage:
    python run_demo.py                    # Run with default sample contract
    python run_demo.py --file contract.txt  # Run with custom contract
    python run_demo.py --verbose          # Enable debug logging
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import NoReturn

# ASCII art banner
BANNER = """
╔═════════════════════════════════════════════════════════╗
║   📊 GraphRAG Legal Auditor                        ║
║   Graph-Native Compliance Agent                   ║
╚═════════════════════════════════════════════════════════╝
"""

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="GraphRAG Legal Auditor - Analyze contracts for compliance risks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_demo.py                     Run with sample contract
  python run_demo.py -f my_contract.txt  Analyze custom contract
  python run_demo.py -v                  Verbose output
        """
    )
    parser.add_argument(
        "-f", "--file",
        type=Path,
        default=Path("data/sample_contract.txt"),
        help="Path to contract file (default: data/sample_contract.txt)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug logging"
    )
    parser.add_argument(
        "--skip-reset",
        action="store_true",
        help="Skip database reset (use existing graph data)"
    )
    return parser.parse_args()


def load_contract(file_path: Path) -> str:
    """
    Load contract text from file.
    
    Args:
        file_path: Path to the contract file.
    
    Returns:
        Contract text content.
    
    Raises:
        SystemExit: If file cannot be read.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        logger.info(f"✅ Loaded contract: {file_path} ({len(content):,} characters)")
        return content
    except FileNotFoundError:
        logger.error(f"❌ File not found: {file_path}")
        sys.exit(1)
    except PermissionError:
        logger.error(f"❌ Permission denied: {file_path}")
        sys.exit(1)


def reset_database() -> None:
    """
    Clear the Neo4j database for a fresh analysis.
    
    Raises:
        SystemExit: If database connection fails.
    """
    from src.graph_builder import GraphBuilder
    from src.exceptions import DatabaseConnectionError
    
    logger.info("🗑️  Resetting Neo4j database...")
    try:
        with GraphBuilder() as gb:
            gb.clear_database()
        logger.info("✅ Database cleared successfully")
    except DatabaseConnectionError as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.error("\n💡 Tip: Make sure Neo4j is running:")
        logger.error("   docker-compose up -d")
        logger.error("   # Wait 10-15 seconds for initialization")
        sys.exit(1)


def run_workflow(contract_text: str) -> dict:
    """
    Execute the LangGraph compliance analysis workflow.
    
    Args:
        contract_text: Raw contract text to analyze.
    
    Returns:
        Final workflow state with compliance report.
    """
    from src.workflow import app, create_initial_state
    
    logger.info("🚀 Starting LangGraph Workflow...")
    logger.info("")
    
    initial_state = create_initial_state(contract_text)
    
    result = app.invoke(initial_state)
    
    # Log any errors that occurred
    errors = result.get("errors", [])
    if errors:
        logger.warning(f"⚠️  {len(errors)} error(s) occurred during analysis")
        for err in errors:
            logger.warning(f"   • {err}")
    
    return result


def print_report(report: str) -> None:
    """Print the compliance report with formatting."""
    print("\n" + "═" * 60)
    print(report)
    print("═" * 60 + "\n")


def main() -> NoReturn | None:
    """
    Main entry point for the demo script.
    
    Orchestrates the full demo pipeline:
    1. Parse CLI arguments
    2. Load contract text
    3. Reset database (optional)
    4. Run analysis workflow
    5. Display report
    """
    args = parse_args()
    setup_logging(args.verbose)
    
    print(BANNER)
    
    # Step 1: Load contract
    contract_text = load_contract(args.file)
    
    # Step 2: Reset database (unless skipped)
    if not args.skip_reset:
        reset_database()
    else:
        logger.info("⏭️  Skipping database reset")
    
    # Step 3: Run workflow
    result = run_workflow(contract_text)
    
    # Step 4: Display report
    print_report(result["compliance_report"])
    
    # Summary
    logger.info("✅ Demo completed successfully!")
    logger.info("")
    logger.info("🔍 View the graph in Neo4j Browser: http://localhost:7474")
    logger.info("   Username: neo4j | Password: password")
    
    return None


if __name__ == "__main__":
    main()
