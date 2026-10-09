"""Instructions and per-stage prompts."""

INSTRUCTIONS = """\
You are a principal solution architect and business analyst. You read business requirement \
documents (BRDs) and turn them into a solution pack that both technical and non-technical \
people can act on.

How to work:
- Ground everything in the BRDs supplied below. When you infer something the BRDs do not \
state, label it as an assumption rather than presenting it as a requirement.
- Refer to requirements by their IDs (FR-xxx, NFR-xxx) once those exist, so every document \
traces back to the analysis.
- Prefer concrete, decision-ready content over generic best-practice lists. If a choice \
depends on information that is missing, say what the choice depends on and give a default.
- Technology choices: recommend one option, name a credible alternative, and give the reason \
in a sentence. Stay vendor-neutral unless the BRDs name a platform.
- Write in GitHub-flavoured Markdown. Use Mermaid code blocks (```mermaid) for diagrams and \
keep them syntactically simple so they render on GitHub.
- Cost and effort figures are estimates; show the basis (team size, rates, durations) so a \
reader can adjust them.
"""


def analysis_prompt() -> str:
    return """\
Analyse the business requirement documents and produce the structured requirements analysis.

Extract every functional and non-functional requirement with a stable ID, MoSCoW priority, \
source reference and testable acceptance criteria. Then go beyond what is written:
- gaps_and_ambiguities: anything vague, missing, conflicting or untestable, each with the \
clarifying question you would put to the business owner.
- suggested_enhancements: capabilities the authors probably did not think of but would value \
(for example audit trails, self-service reporting, accessibility, data retention, \
observability, automation, AI assistance, disaster recovery). Only include ones that fit this \
project.
- risks: delivery, technical, security, compliance and adoption risks with mitigations.
- success_metrics: measurable KPIs; propose sensible ones if the BRDs give none.
- glossary: business and technical terms a non-technical reader would need explained."""


def hld_prompt(analysis_json: str) -> str:
    return f"""\
Requirements analysis (source of truth for IDs):
<analysis>
{analysis_json}
</analysis>

Write the High-Level Design (HLD). Audience: architects, engineering leads, and informed \
business stakeholders. Cover:
1. Solution overview in plain language (one short paragraph a non-technical reader can follow).
2. Architecture principles and key design drivers (link to NFR IDs).
3. System context diagram (Mermaid flowchart): users, the system, external systems.
4. Logical architecture / component diagram (Mermaid) and a table of components with \
responsibilities and the requirement IDs each one serves.
5. Key end-to-end flows for the most important business processes (Mermaid sequence diagrams).
6. Data architecture: main data entities, data flows, data ownership, retention.
7. Integration architecture: interfaces, protocols, sync vs async, error handling.
8. Technology stack recommendation with alternatives and rationale.
9. Deployment and infrastructure view (environments, hosting, scaling approach) with a diagram.
10. Security architecture: identity and access, data protection, threat considerations, compliance.
11. Non-functional design: how performance, availability, scalability, observability and DR \
targets will be met.
12. Architecture Decision Records: 3-6 key decisions (context, decision, consequences).
13. Open questions that affect the design."""


def lld_prompt(analysis_json: str, hld: str) -> str:
    return f"""\
Requirements analysis:
<analysis>
{analysis_json}
</analysis>

High-Level Design:
<hld>
{hld}
</hld>

Write the Low-Level Design (LLD) that a development team can build from. Stay consistent with \
the HLD component names. Cover:
1. Module / service breakdown: for each HLD component, its internal modules, classes or \
functions and their responsibilities.
2. API specification: endpoints (method, path, request/response fields, status codes, auth) \
for the main capabilities, as tables or concise OpenAPI-style snippets.
3. Data model: entity-relationship diagram (Mermaid erDiagram) plus table definitions with \
columns, types, keys, indexes and constraints.
4. Detailed sequence diagrams for the 3-5 most complex flows, including error paths.
5. State machines for entities with a lifecycle (Mermaid stateDiagram) where relevant.
6. Business rules and validation logic, each tied to requirement IDs.
7. Error handling, retries, idempotency and logging conventions.
8. Configuration, feature flags and secrets handling.
9. Background jobs, schedules and event/message contracts if any.
10. UI / screen inventory with the main fields and actions, if the solution has a UI.
11. Coding standards, repository layout and CI/CD pipeline steps."""


def delivery_prompt(analysis_json: str, hld: str) -> str:
    return f"""\
Requirements analysis:
<analysis>
{analysis_json}
</analysis>

High-Level Design:
<hld>
{hld}
</hld>

Write the Delivery Plan. Audience: sponsors, programme managers and team leads. Cover:
1. Delivery approach (e.g. phased / agile) and why.
2. Phases: MVP first, then later releases; for each phase the scope (requirement IDs), \
outcome for the business, and exit criteria.
3. Timeline as a Mermaid gantt chart plus a milestone table.
4. Team composition (roles, count, allocation) and RACI for key activities.
5. Effort estimate per phase (person-weeks) and a cost estimate with the assumptions shown \
(blended day rate, team size, infrastructure and licence costs). Mark these clearly as estimates.
6. Risk register: take the analysed risks, add delivery risks, give owner and mitigation.
7. Dependencies and decisions needed from the business, with the date they are needed by.
8. Change management and adoption plan: training, communication, rollout, hypercare.
9. Governance: ceremonies, reporting cadence, quality gates."""


def test_strategy_prompt(analysis_json: str, lld: str) -> str:
    return f"""\
Requirements analysis:
<analysis>
{analysis_json}
</analysis>

Low-Level Design:
<lld>
{lld}
</lld>

Write the Test Strategy. Cover:
1. Test levels and types (unit, integration, contract, end-to-end, performance, security, \
accessibility, UAT) with scope, tools and owners.
2. Test case catalogue: a table with test ID (TC-xxx), requirement ID, scenario, steps \
summary, expected result, and type. Cover every Must requirement at least once.
3. Non-functional test approach with measurable targets taken from the NFRs.
4. Test data and environment strategy.
5. Entry/exit criteria and the defect severity model.
6. UAT plan for business users in plain language."""


def traceability_prompt(analysis_json: str, hld: str, lld: str, delivery: str, tests: str) -> str:
    return f"""\
<analysis>
{analysis_json}
</analysis>
<hld>
{hld}
</hld>
<lld>
{lld}
</lld>
<delivery_plan>
{delivery}
</delivery_plan>
<test_strategy>
{tests}
</test_strategy>

Build the requirements traceability matrix. Include one row per requirement ID in the analysis \
(functional and non-functional). For each, name the HLD component, the LLD element, the test \
case ID(s) and the delivery phase that cover it, as they appear in the documents above. Mark \
status honestly: if a document does not cover the requirement, say "Not covered" or \
"Partially covered" and explain in the note."""


def executive_summary_prompt(analysis_json: str, hld: str, delivery: str) -> str:
    return f"""\
<analysis>
{analysis_json}
</analysis>
<hld>
{hld}
</hld>
<delivery_plan>
{delivery}
</delivery_plan>

Write a one-to-two page Executive Summary for C-level readers who will spend five minutes on \
it. No jargon; where a technical term is unavoidable, explain it in a few words. Structure:
- The opportunity / problem (why act now)
- What we will build, in one paragraph
- Business value and the KPIs we will measure
- Timeline and investment (headline numbers, clearly labelled as estimates)
- Top risks and how we handle them
- Decisions and approvals needed from leadership
- Recommendation

Open with a three-line "Bottom line" box (a Markdown blockquote)."""


def business_overview_prompt(analysis_json: str, hld: str, delivery: str) -> str:
    return f"""\
<analysis>
{analysis_json}
</analysis>
<hld>
{hld}
</hld>
<delivery_plan>
{delivery}
</delivery_plan>

Write a Business Overview for non-technical teams (operations, sales, finance, support, end \
users) who will use or be affected by the solution. Plain language and everyday analogies; no \
acronyms without explanation. Cover:
- What is changing and why it matters to them
- A day-in-the-life before vs after, for each main user group
- How the solution works, explained with a simple picture (one Mermaid flowchart with \
business-friendly labels only)
- What they will need to do: training, process changes, data they must provide
- When it arrives (phases in plain terms)
- How we will know it is working (the KPIs)
- FAQ: the 8-12 questions these readers are most likely to ask, with answers
- Glossary of terms they will hear"""


def deck_prompt(audience: str, analysis_json: str, summary_doc: str, extra_doc: str) -> str:
    if audience == "executive":
        brief = (
            "Executive steering committee. 8-10 slides. Focus on value, cost, timeline, risk and "
            "the decisions needed. No technical detail beyond one simple architecture slide."
        )
    else:
        brief = (
            "Delivery and business teams (mixed technical and non-technical). 12-16 slides. "
            "Cover the problem, scope, how the solution works, architecture in layers (simple "
            "first, then more detail), key flows, phases, what changes for each team, testing "
            "and UAT, risks, and next steps."
        )
    return f"""\
<analysis>
{analysis_json}
</analysis>
<primary_document>
{summary_doc}
</primary_document>
<supporting_document>
{extra_doc}
</supporting_document>

Create a presentation deck. Audience: {brief}
Each slide: a short title, a one-line takeaway subtitle, 3-6 crisp bullets (max ~12 words \
each), and speaker notes the presenter can read aloud (3-6 sentences). Start with a title \
slide and end with a next-steps / decisions slide."""


def review_prompt(analysis_json: str, documents: str) -> str:
    return f"""\
<analysis>
{analysis_json}
</analysis>
<solution_pack>
{documents}
</solution_pack>

Act as an independent design authority reviewing this solution pack against the original BRDs. \
Score (1-5) completeness, requirement coverage, architectural soundness, security and \
compliance, feasibility of plan and estimates, and clarity for non-technical readers. List any \
requirement not adequately covered, inconsistencies between documents (names, numbers, phases), \
and the concrete fixes you recommend, most important first."""


def change_impact_prompt(previous_json: str, current_json: str) -> str:
    return f"""\
The business requirement documents changed since the last run.

Previous requirements analysis:
<previous>
{previous_json}
</previous>

Current requirements analysis:
<current>
{current_json}
</current>

Write a Change Impact Report: added, removed and modified requirements (match by meaning, not \
only by ID), the effect on architecture, timeline, cost and risk, which stakeholders must be \
told, and recommended next steps. Start with a three-line summary for executives."""


def ask_prompt(question: str, audience: str, pack: str) -> str:
    style = {
        "executive": "Answer for a senior executive: short, outcome-focused, no jargon.",
        "business": "Answer for a non-technical business user: plain language and an example.",
        "technical": "Answer for an engineer: precise, reference components, APIs and data.",
    }[audience]
    return f"""\
<solution_pack>
{pack}
</solution_pack>

{style}
Use the BRDs and the solution pack above. Cite the document and requirement IDs you rely on. \
If the answer is not in the material, say so and suggest who should decide.

Question: {question}"""
