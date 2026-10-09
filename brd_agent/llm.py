"""Thin wrapper around the Anthropic SDK used by every pipeline stage."""

from __future__ import annotations

import sys
from typing import Callable, TypeVar

import anthropic
from pydantic import BaseModel

DEFAULT_MODEL = "claude-opus-5-5"
# Server-side fallback: if a safety classifier declines a request, the API re-runs it on a
# recommended model inside the same call instead of returning a refusal.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

T = TypeVar("T", bound=BaseModel)


class RefusalError(RuntimeError):
    pass


class Claude:
    def __init__(self, model: str = DEFAULT_MODEL, effort: str = "high", echo: bool = True):
        self.client = anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.echo = echo
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_tokens = 0

    def _system(self, instructions: str, context: str) -> list[dict]:
        # Instructions + source documents form a stable prefix shared by every stage, so it is
        # cached once and re-read cheaply by the rest of the pipeline.
        return [
            {"type": "text", "text": instructions},
            {"type": "text", "text": context, "cache_control": {"type": "ephemeral"}},
        ]

    def _record(self, message) -> None:
        usage = message.usage
        self.input_tokens += (usage.input_tokens or 0) + (usage.cache_creation_input_tokens or 0)
        self.cache_read_tokens += usage.cache_read_input_tokens or 0
        self.output_tokens += usage.output_tokens or 0

    @staticmethod
    def _check_stop(message) -> None:
        if message.stop_reason == "refusal":
            details = message.stop_details
            reason = getattr(details, "explanation", None) or "no explanation given"
            raise RefusalError(f"Claude declined this stage: {reason}")
        if message.stop_reason == "max_tokens":
            print("\n[warning] output hit max_tokens and may be truncated", file=sys.stderr)

    def write(
        self,
        instructions: str,
        context: str,
        prompt: str,
        on_text: Callable[[str], None] | None = None,
        max_tokens: int = 64000,
    ) -> str:
        """Stream a long Markdown deliverable and return its text."""
        with self.client.beta.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=self._system(instructions, context),
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            for text in stream.text_stream:
                if on_text:
                    on_text(text)
            message = stream.get_final_message()
        self._record(message)
        self._check_stop(message)
        return "".join(block.text for block in message.content if block.type == "text").strip()

    def structured(
        self,
        instructions: str,
        context: str,
        prompt: str,
        schema: type[T],
        max_tokens: int = 64000,
    ) -> T:
        """Ask for JSON that is guaranteed to match `schema`, returned as a validated model."""
        with self.client.beta.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=self._system(instructions, context),
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            output_format=schema,
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()
        self._record(message)
        self._check_stop(message)
        parsed = message.parsed_output
        if parsed is None:
            raise RuntimeError("Claude returned no structured output for this stage")
        return parsed

    def usage_summary(self) -> str:
        return (
            f"input tokens: {self.input_tokens:,} | cached input reads: {self.cache_read_tokens:,} "
            f"| output tokens: {self.output_tokens:,}"
        )
