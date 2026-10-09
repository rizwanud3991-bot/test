"""Structured outputs the agent asks Claude for (validated with pydantic)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Priority = Literal["Must", "Should", "Could", "Won't"]
Severity = Literal["High", "Medium", "Low"]


class Stakeholder(BaseModel):
    name: str = Field(description="Role or group, e.g. 'Finance team'")
    interest: str
    influence: Severity


class Requirement(BaseModel):
    id: str = Field(description="Stable ID: FR-001 for functional, NFR-001 for non-functional")
    title: str
    description: str
    category: str = Field(description="Business area or quality attribute, e.g. 'Payments', 'Security'")
    priority: Priority
    source: str = Field(description="Source document name and section, or 'Inferred' when not stated")
    acceptance_criteria: list[str]


class Gap(BaseModel):
    area: str
    issue: str = Field(description="What is missing, vague or contradictory in the BRD")
    impact: Severity
    clarifying_question: str = Field(description="Question to ask the business owner to close the gap")


class Suggestion(BaseModel):
    title: str
    rationale: str = Field(description="Why this adds value even though the BRD did not ask for it")
    benefit_for: str = Field(description="Who benefits: users, operations, compliance, business, ...")
    effort: Severity


class Risk(BaseModel):
    id: str = Field(description="R-001, R-002, ...")
    description: str
    likelihood: Severity
    impact: Severity
    mitigation: str


class GlossaryTerm(BaseModel):
    term: str
    meaning: str = Field(description="Plain-language definition a non-technical reader understands")


class RequirementsAnalysis(BaseModel):
    project_name: str
    problem_statement: str
    business_objectives: list[str]
    success_metrics: list[str] = Field(description="Measurable KPIs; infer sensible ones if the BRD has none")
    stakeholders: list[Stakeholder]
    in_scope: list[str]
    out_of_scope: list[str]
    functional_requirements: list[Requirement]
    non_functional_requirements: list[Requirement]
    constraints: list[str]
    assumptions: list[str]
    dependencies: list[str]
    gaps_and_ambiguities: list[Gap]
    suggested_enhancements: list[Suggestion] = Field(
        description="Valuable capabilities the BRD authors did not think of"
    )
    risks: list[Risk]
    glossary: list[GlossaryTerm]


class TraceRow(BaseModel):
    requirement_id: str
    requirement_title: str
    hld_component: str
    lld_element: str = Field(description="API, class, table, job or screen that implements it")
    test_reference: str
    delivery_phase: str
    status: Literal["Covered", "Partially covered", "Not covered"]
    note: str


class TraceabilityMatrix(BaseModel):
    rows: list[TraceRow]


class Slide(BaseModel):
    title: str
    subtitle: str = Field(description="One-line takeaway; empty string if none")
    bullets: list[str] = Field(description="3-6 short bullets")
    speaker_notes: str


class Deck(BaseModel):
    title: str
    audience: str
    slides: list[Slide]


class ReviewScore(BaseModel):
    dimension: str
    score: int = Field(description="1 (poor) to 5 (excellent)")
    comment: str


class QualityReview(BaseModel):
    overall_score: int = Field(description="1 (poor) to 5 (excellent)")
    verdict: str
    scores: list[ReviewScore]
    uncovered_requirements: list[str]
    inconsistencies: list[str]
    recommended_fixes: list[str]
