"""Offline tests: the whole pipeline runs against a fake Claude, no API key needed."""

import json
from pathlib import Path

import pytest

from brd_agent import cli
from brd_agent.ingest import load_documents
from brd_agent.pipeline import STAGES, Pipeline
from brd_agent.schemas import (
    Deck,
    Gap,
    GlossaryTerm,
    QualityReview,
    Requirement,
    RequirementsAnalysis,
    ReviewScore,
    Risk,
    Slide,
    Stakeholder,
    Suggestion,
    TraceabilityMatrix,
    TraceRow,
)


def _analysis(name="Onboarding") -> RequirementsAnalysis:
    req = Requirement(
        id="FR-001", title="Save and resume", description="Customer can resume", category="Onboarding",
        priority="Must", source="brd.md §4", acceptance_criteria=["Draft persists 30 days"],
    )
    nfr = req.model_copy(update={"id": "NFR-001", "title": "Availability", "category": "Reliability"})
    return RequirementsAnalysis(
        project_name=name, problem_statement="Slow paper onboarding", business_objectives=["Faster"],
        success_metrics=["<15 min"], stakeholders=[Stakeholder(name="Ops", interest="Less re-keying", influence="High")],
        in_scope=["Web"], out_of_scope=["Joint accounts"], functional_requirements=[req],
        non_functional_requirements=[nfr], constraints=["SOAP"], assumptions=["Cloud ok"], dependencies=["KYC vendor"],
        gaps_and_ambiguities=[Gap(area="NFR", issue="'most of the time'", impact="High", clarifying_question="SLA?")],
        suggested_enhancements=[Suggestion(title="Audit trail", rationale="Regulators", benefit_for="Compliance", effort="Low")],
        risks=[Risk(id="R-001", description="Budget", likelihood="Medium", impact="High", mitigation="Phase")],
        glossary=[GlossaryTerm(term="KYC", meaning="Know your customer")],
    )


class FakeClaude:
    def __init__(self):
        self.calls = []
        self.project = "Onboarding"

    def write(self, instructions, context, prompt, on_text=None, max_tokens=0):
        self.calls.append(prompt[:60])
        if on_text:
            on_text("chunk")
        return f"# Doc\n\n```mermaid\nflowchart LR\nA-->B\n```\n\n{len(self.calls)} </script>"

    def structured(self, instructions, context, prompt, schema, max_tokens=0):
        self.calls.append(schema.__name__)
        if schema is RequirementsAnalysis:
            return _analysis(self.project)
        if schema is TraceabilityMatrix:
            return TraceabilityMatrix(rows=[TraceRow(
                requirement_id="FR-001", requirement_title="Save", hld_component="Onboarding API",
                lld_element="POST /applications", test_reference="TC-001", delivery_phase="MVP",
                status="Covered", note="",
            )])
        if schema is Deck:
            return Deck(title="Deck", audience="Execs", slides=[
                Slide(title="Title", subtitle="Sub", bullets=["a"], speaker_notes="hi"),
                Slide(title="Next <steps>", subtitle="", bullets=["b & c"], speaker_notes="bye"),
            ])
        if schema is QualityReview:
            return QualityReview(overall_score=4, verdict="Good", scores=[ReviewScore(dimension="Coverage", score=4, comment="ok")],
                                 uncovered_requirements=[], inconsistencies=[], recommended_fixes=["Confirm SLA"])
        raise AssertionError(schema)

    def usage_summary(self):
        return "fake"


@pytest.fixture
def brds(tmp_path: Path) -> Path:
    folder = tmp_path / "brds"
    folder.mkdir()
    (folder / "brd.md").write_text("# BRD\nCustomers open accounts online.", encoding="utf-8")
    (folder / "notes.txt").write_text("Go-live before FY end.", encoding="utf-8")
    (folder / "ignore.exe").write_bytes(b"\x00")
    return folder


def test_load_documents_filters_and_sorts(brds):
    docs = load_documents(brds)
    assert [d.name for d in docs] == ["brd.md", "notes.txt"]


def test_full_run_writes_every_stage_and_resumes(brds, tmp_path):
    out = tmp_path / "out"
    fake = FakeClaude()
    Pipeline(load_documents(brds), out, fake).run()

    for stage in STAGES:
        assert (out / stage.main_file).exists(), stage.key
    for extra in ["01_requirements_analysis.json", "02_gaps_questions_and_ideas.md", "07_traceability_matrix.csv",
                  "10_executive_deck.html", "11_team_deck.html", "PROGRESS.md", "solution_pack.html"]:
        assert (out / extra).exists(), extra

    state = json.loads((out / ".state.json").read_text())
    assert set(state["stages"]) == {s.key for s in STAGES}
    assert "Next &lt;steps&gt;" in (out / "10_executive_deck.html").read_text()
    portal = (out / "solution_pack.html").read_text()
    assert "</script>\"" not in portal and "<\\/script>" in portal
    assert "11/11 stages complete" in portal

    # Same inputs: nothing is regenerated.
    again = FakeClaude()
    Pipeline(load_documents(brds), out, again).run()
    assert again.calls == []


def test_changed_inputs_archive_and_produce_change_impact(brds, tmp_path):
    out = tmp_path / "out"
    Pipeline(load_documents(brds), out, FakeClaude()).run(only=["analysis"])
    (brds / "brd.md").write_text("# BRD v2\nAlso joint accounts.", encoding="utf-8")

    fake = FakeClaude()
    fake.project = "Onboarding v2"
    Pipeline(load_documents(brds), out, fake).run(only=["hld"])

    history = list((out / "history").iterdir())
    assert len(history) == 1 and (history[0] / "01_requirements_analysis.json").exists()
    assert (out / "00_change_impact.md").exists()
    assert (out / "03_high_level_design.md").exists()
    assert not (out / "04_low_level_design.md").exists()
    assert "Change Impact Report" in (out / "solution_pack.html").read_text()


def test_parallel_workers(brds, tmp_path):
    out = tmp_path / "out"
    Pipeline(load_documents(brds), out, FakeClaude(), workers=3).run()
    assert (out / "12_quality_review.md").exists()


def test_cli_rejects_unknown_stage(brds, tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    with pytest.raises(SystemExit, match="Unknown stage"):
        cli.main(["run", "-i", str(brds), "-o", str(tmp_path / "o"), "--stages", "nope"])
