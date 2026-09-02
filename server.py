"""
BIS Agentic RAG Assistant - REST API Server Entry Point
======================================================
Launches the FastAPI application using Uvicorn.

Usage:
    python server.py                    # Runs on 127.0.0.1:8000
    python server.py --host 0.0.0.0     # Expose on all network interfaces
    python server.py --port 8080        # Custom port
    python server.py --reload           # Auto-reload on code edits
"""
from __future__ import annotations

import argparse
import uvicorn
from rich.console import Console
from rich.panel import Panel

from src.config import CONFIG, validate_environment

console = Console()


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for REST API server."""
    parser = argparse.ArgumentParser(description="BIS Agentic RAG Assistant REST API Server")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host IP address to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port number to bind (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    return parser.parse_args()


def display_server_banner(host: str, port: int) -> None:
    """Print styled startup banner for REST API."""
    docs_url = f"http://{host}:{port}/docs"
    banner_text = (
        "[bold green]BIS Agentic RAG REST API Server[/bold green]\n"
        f"[cyan]Server Address:[/cyan] http://{host}:{port}\n"
        f"[cyan]Swagger Docs:[/cyan] [link={docs_url}]{docs_url}[/link]\n"
        f"[dim]LLM Model: {CONFIG.llm_model} | Embedding: {CONFIG.embedding_provider}[/dim]"
    )
    console.print(Panel.fit(banner_text, border_style="green"))


def main() -> None:
    """Validate environment and launch Uvicorn web server."""
    validate_environment()
    args = parse_args()
    display_server_banner(args.host, args.port)

    uvicorn.run(
        "app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=CONFIG.log_level.lower(),
    )


if __name__ == "__main__":
    main()
