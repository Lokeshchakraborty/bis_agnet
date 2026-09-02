"""
BIS Agentic RAG Assistant (Voice & Text Enabled)
================================================
A LangGraph-based conversational assistant for the Bureau of Indian Standards (BIS).

Usage:
    python main.py                     # Auto mode (Voice capture on empty input)
    python main.py --mode text         # Text-only mode
    python main.py --speak             # Enable voice playback for replies
    python main.py --clear-cache       # Clear cached responses
"""
from __future__ import annotations

import argparse
import json
import sys

from rich.console import Console
from rich.panel import Panel

from src.agent.session import Session
from src.audio.handler import LocalAudioHandler
from src.config import CONFIG, validate_environment
from src.tools.cache import ResponseCache

console = Console()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="BIS Agentic RAG Assistant")
    parser.add_argument(
        "--mode",
        choices=["auto", "text"],
        default="auto",
        help="'auto' allows microphone voice capture on empty input; 'text' disables voice input.",
    )
    parser.add_argument(
        "--speak",
        action="store_true",
        help="Speak responses aloud using offline text-to-speech synthesis.",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the persistent response cache before starting.",
    )
    return parser.parse_args()


def display_welcome_banner(speak_enabled: bool, mode: str) -> None:
    """Print styled startup banner with system configuration."""
    voice_status = "ON" if speak_enabled or mode == "auto" else "OFF"
    cache_status = "ON" if CONFIG.cache_enabled else "OFF"
    banner_text = (
        "[bold green]BIS Agentic RAG Assistant[/bold green]\n"
        f"[dim]Cache: {cache_status} | "
        f"Retrieval: Hybrid BM25 + Dense + Live Scrape (top-{CONFIG.rerank_top_n}) | "
        f"Voice Output: {voice_status}[/dim]"
    )
    console.print(Panel.fit(banner_text, border_style="green"))


def display_token_summary(payload: dict) -> None:
    """Render per-turn and session token consumption."""
    tu = payload.get("token_usage", {})
    if not tu:
        return

    turn_llm = tu.get("turn_llm_tokens", 0)
    p_tok = tu.get("turn_prompt_tokens", 0)
    c_tok = tu.get("turn_completion_tokens", 0)
    s_llm = tu.get("session_total_llm_tokens", 0)
    e_tok = tu.get("turn_embedding_tokens", 0)
    provider = tu.get("embedding_provider", "")
    saved = tu.get("session_total_saved_tokens", 0)
    cache_badge = " [bold green]🎉 Cache Hit (0 Tokens Burned)![/bold green]" if payload.get("cache_hit") else ""

    console.print(
        f"⚡ [bold cyan]Tokens:[/bold cyan] "
        f"Turn: [bold green]{turn_llm}[/bold green] (In: {p_tok}, Out: {c_tok}) | "
        f"Session Total: [bold magenta]{s_llm}[/bold magenta] | "
        f"Embedding: [dim]{e_tok} tokens ({provider})[/dim] | "
        f"Saved: [green]{saved} tokens[/green]{cache_badge}"
    )


def main() -> None:
    """Main CLI execution loop."""
    validate_environment()
    args = parse_args()

    if args.clear_cache:
        ResponseCache().clear()
        console.print("[yellow]Response cache cleared.[/yellow]")

    display_welcome_banner(args.speak, args.mode)

    audio_handler = None
    if args.mode == "auto" or args.speak:
        audio_handler = LocalAudioHandler(model_size="base")
    else:
        console.print("[dim]Voice input disabled (--mode text).[/dim]")

    session = Session()

    while True:
        try:
            console.print("\n[bold cyan]YOU : > [/bold cyan]", end="")
            user_input = input().strip()

            # Handle empty input for voice recording
            if user_input == "":
                if audio_handler is None or args.mode == "text":
                    console.print("[yellow]Voice input is disabled. Type your question.[/yellow]")
                    continue
                audio_file = audio_handler.record_audio()
                user_query = audio_handler.transcribe(audio_file)
                if not user_query:
                    console.print("[yellow]Could not hear any speech. Please try again.[/yellow]")
                    continue
                console.print(f"[bold magenta]Transcribed:[/bold magenta] {user_query}")
            else:
                user_query = user_input

            if user_query.lower() in {"exit", "quit", "q"}:
                console.print("[yellow]Goodbye![/yellow]")
                break

            with console.status("[cyan]Thinking...[/cyan]", spinner="dots"):
                state = session.run_turn(user_query)

            payload = session.to_json(state)
            title = f"BIS Assistant ({payload['intent']})"
            if payload.get("cache_hit"):
                title += " [CACHE]"

            console.print(Panel(
                json.dumps(payload, indent=2, ensure_ascii=False),
                title=title,
                border_style="cyan",
            ))

            display_token_summary(payload)

            # Optional Voice Playback
            if (args.speak or (args.mode == "auto" and user_input == "")) and audio_handler and payload.get("core_response"):
                audio_handler.speak_text(payload["core_response"])

        except KeyboardInterrupt:
            console.print("\n[yellow]Exiting...[/yellow]")
            sys.exit(0)
        except Exception as exc:
            console.print(f"[red]Error in turn: {exc}[/red]")


if __name__ == "__main__":
    main()