"""The staged pipeline: BRDs in, a progressively written solution pack out."""

from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from . import prompts, render
from .ingest import SourceDocument, as_context, fingerprint
from .llm import Claude
from .schemas import Deck, QualityReview, RequirementsAnalysis, TraceabilityMatrix

STATE_FILE = ".state.json"
ANALYSIS_JSON = "01_requirements_analysis.json"


@dataclass
class Context:
    """Everything stages share: source docs, the parsed analysis and each stage's main document."""

    claude: Claude
    out: Path
    docs_context: str
    analysis: RequirementsAnalysis | None = None
    texts: dict[str, str] = field(default_factory=dict)

    @property
    def analysis_json(self) -> str:
        assert self.analysis is not None, "analysis stage must run first"
        return self.analysis.model_dump_json(indent=2)

    def write(self, prompt: str, on_text: Callable[[str], None] | None) -> str:
        return self.claude.write(prompts.INSTRUCTIONS, self.docs_context, prompt, on_text=on_text)

    def structured(self, prompt: str, schema):
        return self.claude.structured(prompts.INSTRUCTIONS, self.docs_context, prompt, schema)


@dataclass
class Stage:
    key: str
    title: str
    audience: str
    deps: tuple[str, ...]
    main_file: str
    run: Callable[[Context, Callable[[str], None] | None], dict[str, str | bytes | Callable[[Path], bool]]]


# --- stage implementations -------------------------------------------------------------------


def _analysis(ctx: Context, on_text):
    analysis = ctx.structured(prompts.analysis_prompt(), RequirementsAnalysis)
    ctx.analysis = analysis
    return {
        "01_requirements_analysis.md": render.analysis_markdown(analysis),
        ANALYSIS_JSON: analysis.model_dump_json(indent=2),
        "02_gaps_questions_and_ideas.md": render.gaps_markdown(analysis),
    }


def _hld(ctx: Context, on_text):
    return {"03_high_level_design.md": ctx.write(prompts.hld_prompt(ctx.analysis_json), on_text)}


def _lld(ctx: Context, on_text):
    return {"04_low_level_design.md": ctx.write(prompts.lld_prompt(ctx.analysis_json, ctx.texts["hld"]), on_text)}


def _delivery(ctx: Context, on_text):
    text = ctx.write(prompts.delivery_prompt(ctx.analysis_json, ctx.texts["hld"]), on_text)
    return {"05_delivery_plan.md": text}


def _tests(ctx: Context, on_text):
    text = ctx.write(prompts.test_strategy_prompt(ctx.analysis_json, ctx.texts["lld"]), on_text)
    return {"06_test_strategy.md": text}


def _traceability(ctx: Context, on_text):
    t = ctx.texts
    matrix = ctx.structured(
        prompts.traceability_prompt(ctx.analysis_json, t["hld"], t["lld"], t["delivery"], t["tests"]),
        TraceabilityMatrix,
    )
    return {
        "07_traceability_matrix.md": render.traceability_markdown(matrix),
        "07_traceability_matrix.csv": lambda path: render.write_traceability_csv(matrix, path) or True,
    }


def _executive_summary(ctx: Context, on_text):
    t = ctx.texts
    text = ctx.write(prompts.executive_summary_prompt(ctx.analysis_json, t["hld"], t["delivery"]), on_text)
    return {"08_executive_summary.md": text}


def _business_overview(ctx: Context, on_text):
    t = ctx.texts
    text = ctx.write(prompts.business_overview_prompt(ctx.analysis_json, t["hld"], t["delivery"]), on_text)
    return {"09_business_overview.md": text}


def _deck(audience: str, prefix: str, primary: str, supporting: str):
    def run(ctx: Context, on_text):
        deck = ctx.structured(
            prompts.deck_prompt(audience, ctx.analysis_json, ctx.texts[primary], ctx.texts[supporting]),
            Deck,
        )
        return {
            f"{prefix}.md": render.deck_markdown(deck),
            f"{prefix}.html": render.deck_html(deck),
            f"{prefix}.pptx": lambda path: render.write_pptx(deck, path),
        }

    return run


def _review(ctx: Context, on_text):
    pack = "\n\n".join(
        f'<document name="{STAGES_BY_KEY[k].main_file}">\n{v}\n</document>'
        for k, v in ctx.texts.items()
        if k != "review"
    )
    review = ctx.structured(prompts.review_prompt(ctx.analysis_json, pack), QualityReview)
    return {"12_quality_review.md": render.review_markdown(review)}


STAGES: list[Stage] = [
    Stage("analysis", "Requirements Analysis", "Everyone", (), "01_requirements_analysis.md", _analysis),
    Stage("hld", "High-Level Design (HLD)", "Architects, tech leads", ("analysis",), "03_high_level_design.md", _hld),
    Stage("lld", "Low-Level Design (LLD)", "Developers", ("analysis", "hld"), "04_low_level_design.md", _lld),
    Stage("delivery", "Delivery Plan", "Sponsors, PMO", ("analysis", "hld"), "05_delivery_plan.md", _delivery),
    Stage("tests", "Test Strategy", "QA, business UAT", ("analysis", "lld"), "06_test_strategy.md", _tests),
    Stage(
        "executive_summary", "Executive Summary", "Executives", ("analysis", "hld", "delivery"),
        "08_executive_summary.md", _executive_summary,
    ),
    Stage(
        "business_overview", "Business Overview", "Non-technical teams", ("analysis", "hld", "delivery"),
        "09_business_overview.md", _business_overview,
    ),
    Stage(
        "traceability", "Traceability Matrix", "PMO, QA, architects",
        ("analysis", "hld", "lld", "delivery", "tests"), "07_traceability_matrix.md", _traceability,
    ),
    Stage(
        "executive_deck", "Executive Presentation", "Executives", ("analysis", "executive_summary", "delivery"),
        "10_executive_deck.md", _deck("executive", "10_executive_deck", "executive_summary", "delivery"),
    ),
    Stage(
        "team_deck", "Team Presentation", "Business & delivery teams", ("analysis", "business_overview", "hld"),
        "11_team_deck.md", _deck("team", "11_team_deck", "business_overview", "hld"),
    ),
    Stage(
        "review", "Quality Review", "Design authority",
        ("analysis", "hld", "lld", "delivery", "tests", "executive_summary", "business_overview", "traceability"),
        "12_quality_review.md", _review,
    ),
]
STAGES_BY_KEY = {s.key: s for s in STAGES}

VIEWS = {
    "executive": ["08_executive_summary.md", "10_executive_deck.md", "02_gaps_questions_and_ideas.md",
                  "00_change_impact.md", "12_quality_review.md"],
    "business": ["09_business_overview.md", "11_team_deck.md", "01_requirements_analysis.md",
                 "02_gaps_questions_and_ideas.md", "05_delivery_plan.md", "06_test_strategy.md"],
    "technical": ["03_high_level_design.md", "04_low_level_design.md", "07_traceability_matrix.md",
                  "06_test_strategy.md", "01_requirements_analysis.md", "12_quality_review.md"],
}


# --- orchestration ---------------------------------------------------------------------------


class Pipeline:
    def __init__(self, docs: list[SourceDocument], out: Path, claude: Claude, workers: int = 1):
        self.docs = docs
        self.out = out
        self.claude = claude
        self.workers = max(1, workers)
        self.fp = fingerprint(docs)
        self.ctx = Context(claude=claude, out=out, docs_context=as_context(docs))
        self.state: dict = {"fingerprint": self.fp, "stages": {}}
        self.lock = threading.Lock()
        self.previous_analysis: str | None = None

    # state ----------------------------------------------------------------------------------

    def _load_state(self, force: bool) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        path = self.out / STATE_FILE
        if not path.exists():
            return
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("fingerprint") == self.fp and not force:
            self.state = old
            return
        # Inputs changed (or a forced rebuild): archive the old pack so nothing is lost and
        # the change-impact report can compare old and new requirements.
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        archive = self.out / "history" / stamp
        archive.mkdir(parents=True, exist_ok=True)
        for item in self.out.iterdir():
            if item.name == "history":
                continue
            shutil.move(str(item), str(archive / item.name))
        prev = archive / ANALYSIS_JSON
        if prev.exists() and old.get("fingerprint") != self.fp:
            self.previous_analysis = prev.read_text(encoding="utf-8")
        print(f"Inputs changed: previous pack archived to {archive}")

    def _save_state(self) -> None:
        (self.out / STATE_FILE).write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def _restore(self, stage: Stage) -> None:
        """Load a completed stage's outputs from disk so later stages can use them."""
        if stage.key == "analysis":
            self.ctx.analysis = RequirementsAnalysis.model_validate_json(
                (self.out / ANALYSIS_JSON).read_text(encoding="utf-8")
            )
        self.ctx.texts[stage.key] = (self.out / stage.main_file).read_text(encoding="utf-8")

    # outputs --------------------------------------------------------------------------------

    def _persist(self, stage: Stage, outputs: dict) -> list[str]:
        written = []
        for name, content in outputs.items():
            path = self.out / name
            if callable(content):
                if content(path):
                    written.append(name)
                continue
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content.rstrip() + "\n", encoding="utf-8")
            written.append(name)
        self.ctx.texts[stage.key] = (self.out / stage.main_file).read_text(encoding="utf-8")
        return written

    def _refresh_reports(self) -> None:
        """Rewrite the progress page and the portal after every stage (progressive output)."""
        done = self.state["stages"]
        lines = [
            "# Solution Pack — Progress",
            "",
            f"Inputs: {', '.join(d.name for d in self.docs)}",
            f"Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"Completed: {len(done)}/{len(STAGES)} stages",
            "",
            "| # | Stage | Audience | Status | Files |",
            "|---|---|---|---|---|",
        ]
        for i, s in enumerate(STAGES, start=1):
            info = done.get(s.key)
            status = "✅ done" if info else "⏳ pending"
            files = ", ".join(f"[{f}]({f})" for f in info["files"]) if info else ""
            lines.append(f"| {i} | {s.title} | {s.audience} | {status} | {files} |")
        if (self.out / "00_change_impact.md").exists():
            lines += ["", "Inputs changed since the last run: see [00_change_impact.md](00_change_impact.md)."]
        lines += ["", "Open [solution_pack.html](solution_pack.html) for the executive / business / technical views."]
        (self.out / "PROGRESS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

        portal_docs = []
        if (self.out / "00_change_impact.md").exists():
            portal_docs.append({
                "file": "00_change_impact.md", "title": "Change Impact Report", "audience": "Everyone",
                "markdown": (self.out / "00_change_impact.md").read_text(encoding="utf-8"), "links": [],
            })
        extra_main = {"analysis": ["02_gaps_questions_and_ideas.md"]}
        for s in STAGES:
            if s.key not in done:
                continue
            for name in [s.main_file] + extra_main.get(s.key, []):
                title = s.title if name == s.main_file else "Gaps, Questions & Ideas"
                links = [f for f in done[s.key]["files"] if not f.endswith((".md", ".json"))]
                portal_docs.append({
                    "file": name, "title": title, "audience": s.audience,
                    "markdown": (self.out / name).read_text(encoding="utf-8"), "links": links,
                })
        project = self.ctx.analysis.project_name if self.ctx.analysis else "Solution Pack"
        meta = f"{len(done)}/{len(STAGES)} stages complete · generated from {len(self.docs)} document(s)"
        (self.out / "solution_pack.html").write_text(
            render.portal_html(project, meta, portal_docs, VIEWS), encoding="utf-8"
        )

    # running --------------------------------------------------------------------------------

    def _run_stage(self, stage: Stage, live: bool) -> None:
        started = time.time()
        print(f"\n▶ {stage.title} — started", flush=True)
        on_text = (lambda t: print(t, end="", flush=True)) if live else None
        outputs = stage.run(self.ctx, on_text)
        with self.lock:
            files = self._persist(stage, outputs)
            self.state["stages"][stage.key] = {
                "files": files,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save_state()
            self._refresh_reports()
        print(f"\n✔ {stage.title} — done in {time.time() - started:.0f}s → {', '.join(files)}", flush=True)

    def _change_impact(self) -> None:
        if not self.previous_analysis or self.ctx.analysis is None:
            return
        print("\n▶ Change Impact Report — started", flush=True)
        text = self.ctx.write(prompts.change_impact_prompt(self.previous_analysis, self.ctx.analysis_json), None)
        (self.out / "00_change_impact.md").write_text(text + "\n", encoding="utf-8")
        self.previous_analysis = None
        print("✔ Change Impact Report — done → 00_change_impact.md", flush=True)

    def run(self, only: list[str] | None = None, force: bool = False) -> None:
        self._load_state(force)
        wanted = set(only or STAGES_BY_KEY)
        # Pull in prerequisites of whatever was asked for.
        stack = list(wanted)
        while stack:
            for dep in STAGES_BY_KEY[stack.pop()].deps:
                if dep not in wanted:
                    wanted.add(dep)
                    stack.append(dep)

        pending: list[Stage] = []
        for s in STAGES:
            if s.key not in wanted:
                continue
            if s.key in self.state["stages"] and (self.out / s.main_file).exists():
                self._restore(s)
                print(f"↺ {s.title} — reusing previous output")
            else:
                pending.append(s)
        self._refresh_reports()

        done = set(self.state["stages"])
        while pending:
            ready = [s for s in pending if all(d in done for d in s.deps)]
            if not ready:
                raise RuntimeError(f"Unresolvable stage dependencies: {[s.key for s in pending]}")
            if self.workers == 1:
                stage = ready[0]
                self._run_stage(stage, live=True)
                finished = [stage]
            else:
                with ThreadPoolExecutor(max_workers=self.workers) as pool:
                    futures = {pool.submit(self._run_stage, s, False): s for s in ready}
                    finished = []
                    for fut in as_completed(futures):
                        fut.result()
                        finished.append(futures[fut])
            for s in finished:
                pending.remove(s)
                done.add(s.key)
                if s.key == "analysis":
                    self._change_impact()
                    with self.lock:
                        self._refresh_reports()

        print(f"\nSolution pack ready in {self.out}", file=sys.stderr)
        print(f"Usage — {self.claude.usage_summary()}", file=sys.stderr)
