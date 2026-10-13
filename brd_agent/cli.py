"""Command line: `python -m brd_agent run|watch|ask`."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import anthropic

from . import prompts
from .ingest import as_context, fingerprint, load_documents
from .llm import DEFAULT_MODEL, Claude, RefusalError
from .pipeline import STAGES, STAGES_BY_KEY, Pipeline


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("-i", "--input", type=Path, default=Path("brds"), help="Folder with BRD files (default: brds)")
    p.add_argument("-o", "--output", type=Path, default=Path("output"), help="Output folder (default: output)")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model (default: {DEFAULT_MODEL})")
    p.add_argument(
        "--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"],
        help="Reasoning depth vs. cost/speed (default: high)",
    )


def _add_run_options(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--stages", default="",
        help="Comma-separated subset to (re)build, prerequisites included. "
        f"Available: {', '.join(s.key for s in STAGES)}",
    )
    p.add_argument("--force", action="store_true", help="Archive the current pack and rebuild everything")
    p.add_argument(
        "--workers", type=int, default=1,
        help="Run independent stages in parallel (1 = one at a time with live streamed output)",
    )


def _run(args: argparse.Namespace) -> None:
    docs = load_documents(args.input)
    if not docs:
        sys.exit(f"No supported documents found in {args.input}")
    print(f"Loaded {len(docs)} document(s): {', '.join(d.name for d in docs)}")
    only = [s.strip() for s in args.stages.split(",") if s.strip()] or None
    unknown = [s for s in only or [] if s not in STAGES_BY_KEY]
    if unknown:
        sys.exit(f"Unknown stage(s): {', '.join(unknown)}")
    claude = Claude(model=args.model, effort=args.effort)
    Pipeline(docs, args.output, claude, workers=args.workers).run(only=only, force=args.force)


def _watch(args: argparse.Namespace) -> None:
    print(f"Watching {args.input} every {args.interval}s — Ctrl+C to stop")
    last = None
    while True:
        fp = None
        try:
            docs = load_documents(args.input)
            fp = fingerprint(docs) if docs else None
            if fp and fp != last:
                print(f"\nChange detected ({len(docs)} document(s)) — building solution pack")
                claude = Claude(model=args.model, effort=args.effort)
                Pipeline(docs, args.output, claude, workers=args.workers).run()
                last = fp
        except (anthropic.APIError, RefusalError, RuntimeError) as e:
            print(f"Build failed, will retry on next change: {e}", file=sys.stderr)
            last = fp
        time.sleep(args.interval)


def _ask(args: argparse.Namespace) -> None:
    docs = load_documents(args.input)
    pack_files = sorted(p for p in args.output.glob("*.md") if p.name != "PROGRESS.md")
    if not pack_files:
        sys.exit(f"No solution pack in {args.output}; run `python -m brd_agent run` first")
    pack = "\n\n".join(f'<document name="{p.name}">\n{p.read_text(encoding="utf-8")}\n</document>' for p in pack_files)
    claude = Claude(model=args.model, effort=args.effort)
    questions = [args.question] if args.question else None
    while True:
        question = questions.pop() if questions else input("\nQuestion (blank to quit): ").strip()
        if not question:
            return
        claude.write(
            prompts.INSTRUCTIONS, as_context(docs), prompts.ask_prompt(question, args.audience, pack),
            on_text=lambda t: print(t, end="", flush=True),
        )
        print()
        if args.question:
            return


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="brd_agent",
        description="Turn business requirement documents into a solution pack: analysis, HLD, LLD, "
        "delivery plan, tests, traceability, executive and business views, and slide decks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Build (or resume) the solution pack")
    _add_common(run)
    _add_run_options(run)
    run.set_defaults(func=_run)

    watch = sub.add_parser("watch", help="Rebuild automatically whenever the BRD folder changes")
    _add_common(watch)
    _add_run_options(watch)
    watch.add_argument("--interval", type=int, default=30, help="Seconds between checks (default: 30)")
    watch.set_defaults(func=_watch)

    ask = sub.add_parser("ask", help="Ask questions about the BRDs and the generated solution")
    _add_common(ask)
    ask.add_argument("question", nargs="?", help="Question; omit for an interactive session")
    ask.add_argument(
        "--audience", default="business", choices=["executive", "business", "technical"],
        help="Tailor the answer to this audience (default: business)",
    )
    ask.set_defaults(func=_ask)

    args = parser.parse_args(argv)
    # A key pasted into a terminal often carries stray spaces, which the API rejects.
    if os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_API_KEY"].strip()
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\nStopped. Completed stages are saved; re-run to resume.", file=sys.stderr)
    except anthropic.AuthenticationError:
        sys.exit("Authentication failed: set ANTHROPIC_API_KEY (or run `ant auth login`).")
    except anthropic.RateLimitError:
        sys.exit("Rate limited by the API. Completed stages are saved; re-run later to resume.")
    except anthropic.APIConnectionError:
        sys.exit("Network error reaching the API. Completed stages are saved; re-run to resume.")
    except anthropic.APIStatusError as e:
        sys.exit(f"API error {e.status_code}: {e.message}. Completed stages are saved; re-run to resume.")
    except RefusalError as e:
        sys.exit(str(e))
