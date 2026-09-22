"""Build the 17-row ClearFlight compliance traceability matrix.

Reads source/cs_uas_annexure_a_structure_material.txt, splits it into one
chunk per sub-clause, calls the OpenAI API once per chunk to classify and
paraphrase that row, validates the combined row against the schema, and
writes data/matrix.json.

The model that produced the data is recorded in data/provenance.json.

Usage:
    put OPENAI_API_KEY=sk-... in .env (or export it), then:
    python extract.py
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError, model_validator

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
SOURCE_PATH = ROOT / "source" / "cs_uas_annexure_a_structure_material.txt"
RAW_OUTPUT_PATH = ROOT / "private" / "raw_llm_outputs.json"  # local only, git-ignored
MATRIX_PATH = ROOT / "data" / "matrix.json"
PROVENANCE_PATH = ROOT / "data" / "provenance.json"

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")
# "default" omits the parameter (gpt-5.6-luna accepts only the default); a number such as "0" is
# sent as-is for models that accept it and make runs reproducible.
TEMPERATURE = os.environ.get("OPENAI_TEMPERATURE", "default")

EVALUATION_TYPES = (
    "records verification",
    "design/analysis review",
    "physical inspection",
    "ground test",
    "flight test",
    "laboratory test",
)
# Stage 1 is a desk review of the application (design, analysis, records, laboratory test
# reports). Physical inspection, ground test and flight test happen only at Stage 2.
STAGE1_TYPES = ("records verification", "design/analysis review", "laboratory test")
SUBSYSTEMS = ("Fasteners", "Propellers", "Landing gear", "Identification plate")
CATEGORIES = ("Micro", "Small", "Medium")
REQUIREMENT_TYPES = (
    "Structural strength",
    "Shock absorption",
    "Fastener security",
    "Vibration",
    "Clearance",
    "Material suitability",
    "Fabrication",
    "Deterioration protection",
    "Identification",
)

FIELD_NAMES = ("PAGE", "SECTION", "PARAMETER", "REQUIREMENT", "EVALUATION_METHOD", "GUIDANCE")

SYSTEM_PROMPT = """You are extracting one row of a compliance traceability matrix from a DGCA
(India) UAS certification document. You will be given the raw text of one
sub-clause. The USER message also states which evaluation stage(s) are
present in the Method of Evaluation text ("Stage 1", "Stage 2" or "Both").
That was determined programmatically from the literal labels in the source
text. Treat it as given: do not question it, and do not describe any stage
that is not listed.

Return ONLY a JSON object with exactly these fields:

- plain_paraphrase: 1-2 plain-English sentences restating the requirement
  for someone without regulatory background. Paraphrase the lettered
  requirement in the Compliance Criteria text, not the Parameter heading.
  Keep any condition the source states (for example "if applicable"): do
  not turn a conditional requirement into an unconditional one. Stay close
  to the clause's own wording: keep its modal verb ("must", "should",
  "may") and its terms (for example "material design values", not "design
  strength values"), and do not add requirements, qualifiers or sentences
  about evidence or verification that the Compliance Criteria text does not
  state.
- stage1_evaluation_types: if the stages present include Stage 1, an array of
  the evaluation type(s) used at Stage 1, chosen ONLY from "records
  verification", "design/analysis review" and "laboratory test". Stage 1 is
  a review of the application (the design, the analysis, records and
  laboratory test reports). Physical inspection, ground test and flight test
  are physical verifications that happen only at Stage 2: never list them
  for Stage 1, even if the guidance mentions an inspection or test; else
  null. Use ONE type unless the source explicitly allows a substitute or
  alternative route (for example "test reports, or analysis/FEA if the
  reports are not available") or the method differs by category. In those
  cases list every such type, primary route first. An alternative route
  means a different KIND of evidence accepted in place of the first. These
  are NOT alternatives, so keep one type: different calculation tools within
  one route (handbook methods and FEA are both design/analysis review),
  equivalent standards, supporting documents that accompany the main
  evidence, and activities that merely precede or follow the verification
  (for example "physical inspection after ground and flight tests" is one
  physical inspection, and a visual check after a load test is part of that
  test).
- stage2_evaluation_types: the same for Stage 2: if the stages present
  include Stage 2, an array of the evaluation type(s) used at Stage 2; else
  null.

  Evaluation types, each meaning specifically:
  - "records verification": checking a document or declaration the
    manufacturer submitted (records, QC procedures, flight logs,
    declarations), with no independent test or inspection performed. Test
    reports issued by an accredited testing laboratory, and static load test
    reports, are NOT records verification; see "laboratory test".
  - "design/analysis review": reviewing calculations, drawings, or analysis
    (e.g. FEA, design documents) submitted by the manufacturer.
  - "physical inspection": visually or manually examining the actual UAS or
    a component, without operating it.
  - "ground test": operating the UAS or a component on the ground, without
    flight.
  - "flight test": verification requiring actual flight of the UAS —
    witnessing a flight test, including the flight logs recorded during it —
    or a drop-from-height landing demonstration (a "drop test" that shows a
    safe landing counts as a flight test). Reviewing flight logs the
    manufacturer submitted is "records verification", not flight test.
  - "laboratory test": the evidence is testing done by an accredited
    laboratory separate from the manufacturer's own facility, often against
    a named standard. This includes reviewing that laboratory's test
    reports: the reviewer relies on the lab's accreditation (for example
    ISO/IEC 17025) as what makes the results valid, rather than re-deriving
    the test numbers. Use it whenever a stage rests on test reports from an
    accredited testing laboratory, even if analysis or FEA is allowed as a
    fallback. A static load test (loads applied to the structure) is also a
    laboratory test. Examples: "Stage 1: Review of material test reports from
    accredited testing laboratory", "Verification of test reports from an
    accredited testing lab" and "material type supported by test reports
    from accredited testing laboratories" are all laboratory tests, not
    records verification.

- evaluation_alternative_note: one plain-language sentence saying when an
  alternative or substitute evaluation route is accepted (for example
  "analysis or FEA may be submitted if laboratory test reports are not
  available"). Set it only when you listed more than one type for a stage
  because of an alternative route; otherwise null. When the types differ only
  because of the category (for example a load test for larger UAS and
  analysis for smaller ones), list both types but leave this null: that
  difference belongs in category_variation_note.
- applicable_categories: array, subset of ["Micro", "Small", "Medium"] — this
  describes which categories the REQUIREMENT ITSELF (Compliance Criteria)
  applies to, NOT which category is named in the Method of Evaluation.
  Default to all three unless the Compliance Criteria text itself restricts
  who the requirement applies to. A category-conditional VERIFICATION
  METHOD (e.g. "static test required for Medium and above, theoretical
  analysis sufficient for others") does NOT narrow applicable_categories —
  the requirement still applies to every category named there; describe the
  method difference only in category_variation_note, below.
  Example: a clause requiring the airframe to withstand flight limit loads,
  verified by static test for Medium+ and theoretical analysis otherwise,
  has applicable_categories = ["Micro","Small","Medium"] (the requirement is
  universal) — the category split belongs entirely in
  category_variation_note, not here.
- category_variation_note: one plain-language sentence describing how the
  requirement OR its verification method differs across categories, if it
  does (e.g. "verification differs: static load test required for Medium
  and above, theoretical analysis sufficient for Micro/Small"). Null if
  both the requirement and its verification are uniform across all
  applicable categories.
- subsystem_tag: the physical part the clause is about, exactly one of
  "Fasteners", "Propellers", "Landing gear" or "Identification plate", or
  null. Use the part the clause or its guidance names. The shock absorbing
  mechanism is part of the landing gear, so clauses about it use "Landing
  gear". Never use the nature of the requirement as a tag ("Identification"
  or "Vibration" describe what a requirement is about, not a part). The
  airframe or structure as a whole is NOT a subsystem. Use null if the
  clause applies system-wide, to the airframe or structure as a whole, or to
  materials in general and names no specific part (this is common for
  airframe-strength, material-strength and fabrication-process clauses).
- requirement_type: exactly one of the values below — the nature of the
  requirement (what it is ABOUT), distinct from which part it names. The
  Parameter/Characteristics text is the strongest signal; use the clause
  text to choose between clauses that share a parameter.
  - "Structural strength": the airframe or structure withstanding loads
    without failure or permanent deformation (limit loads, factor of safety).
  - "Shock absorption": absorbing landing or impact energy (landing gear,
    shock absorbers), including load limits under impact.
  - "Fastener security": preventing removable bolts, screws, nuts and pins
    from loosening or being lost.
  - "Vibration": limiting vibration in operation.
  - "Clearance": keeping moving parts, such as propellers, clear of the
    structure and the ground.
  - "Material suitability": whether the materials chosen for parts are
    suitable, durable and of known strength (selecting and qualifying
    materials). Not for the identification plate, which is "Identification".
  - "Fabrication": how parts are manufactured or assembled (processes,
    quality control, test programs for new methods).
  - "Deterioration protection": protection against loss of strength in
    service from wear, weathering, corrosion, temperature or moisture.
  - "Identification": the identification plate and its material (including
    its fire resistance), location and fixing.
- external_standard_cited: true or false — true if a specific external
  standard (ASTM, ISO, IEC, SAE, IS, ANSI, etc.) is named or clearly
  required ANYWHERE in the text blocks below, including the Guidance
  block, not just in Compliance Criteria. Do not count "per manufacturer
  specification" or "per design document" as an external standard. If more
  than one standard is cited, capture all of them, not just the first.
- external_standard_name: the standard(s) if cited, else null, in this exact
  format. Separate standards that must ALL be met with a semicolon and a
  space ("; "). Where the clause lets the reader satisfy the requirement
  with ONE of several standards (for example "X or Y or equivalent"), join
  those alternatives with " OR " (uppercase) inside a single item. Keep "or
  equivalent" / "or any other appropriate standard" as an alternative when
  the source says so. Never separate standards with commas; write a
  standard that has several parts required together as one item (for
  example "ABC 123 Part 1 and Part 2"). Format example, with made-up
  standards: "ISO 9999; ASTM D123 OR ISO 456 OR equivalent".
- llm_confidence_note: one short sentence flagging anything ambiguous about
  this classification, or "none" if straightforward. Do not return "none"
  unless every field above was a clean, unambiguous match to the source
  text — if you had to infer or guess at all, say so here.

Do not invent information not present in the source text. If the source
text does not specify something, say so in llm_confidence_note rather than
guessing."""

def nullable_types(allowed: tuple[str, ...]) -> dict:
    return {
        "anyOf": [
            {"type": "array", "items": {"type": "string", "enum": list(allowed)}},
            {"type": "null"},
        ]
    }

RESPONSE_SCHEMA = {
    "name": "matrix_row_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "plain_paraphrase": {"type": "string"},
            "stage1_evaluation_types": nullable_types(STAGE1_TYPES),
            "stage2_evaluation_types": nullable_types(EVALUATION_TYPES),
            "evaluation_alternative_note": {"type": ["string", "null"]},
            "applicable_categories": {
                "type": "array",
                "items": {"type": "string", "enum": list(CATEGORIES)},
            },
            "category_variation_note": {"type": ["string", "null"]},
            "subsystem_tag": {"anyOf": [{"type": "string", "enum": list(SUBSYSTEMS)}, {"type": "null"}]},
            "requirement_type": {"type": "string", "enum": list(REQUIREMENT_TYPES)},
            "external_standard_cited": {"type": "boolean"},
            "external_standard_name": {"type": ["string", "null"]},
            "llm_confidence_note": {"type": "string"},
        },
        "required": [
            "plain_paraphrase",
            "stage1_evaluation_types",
            "stage2_evaluation_types",
            "evaluation_alternative_note",
            "applicable_categories",
            "category_variation_note",
            "subsystem_tag",
            "requirement_type",
            "external_standard_cited",
            "external_standard_name",
            "llm_confidence_note",
        ],
        "additionalProperties": False,
    },
}

EvaluationType = Literal[
    "records verification",
    "design/analysis review",
    "physical inspection",
    "ground test",
    "flight test",
    "laboratory test",
]


class MatrixRow(BaseModel):
    clause_id: str
    section: str
    parameter: str
    requirement_text: str
    plain_paraphrase: str
    evaluation_method_raw: str
    evaluation_stage: Literal["Stage 1", "Stage 2", "Both"]
    stage1_evaluation_types: Optional[list[EvaluationType]]
    stage2_evaluation_types: Optional[list[EvaluationType]]
    evaluation_alternative_note: Optional[str]
    guidance_text: Optional[str]
    applicable_categories: list[Literal["Micro", "Small", "Medium"]]
    category_variation_note: Optional[str]
    subsystem_tag: Optional[Literal["Fasteners", "Propellers", "Landing gear", "Identification plate"]]
    requirement_type: Literal[
        "Structural strength",
        "Shock absorption",
        "Fastener security",
        "Vibration",
        "Clearance",
        "Material suitability",
        "Fabrication",
        "Deterioration protection",
        "Identification",
    ]
    external_standard_cited: bool
    external_standard_name: Optional[str]
    source_page: int
    llm_confidence_note: str

    @model_validator(mode="after")
    def check_consistency(self) -> "MatrixRow":
        # Each stage's type list is null exactly when that stage does not apply,
        # and is a non-empty list without repeats when it does.
        for number, types in ((1, self.stage1_evaluation_types), (2, self.stage2_evaluation_types)):
            applies = self.evaluation_stage in (f"Stage {number}", "Both")
            if applies and not types:
                raise ValueError(f"stage{number}_evaluation_types is empty but stage {number} applies")
            if not applies and types is not None:
                raise ValueError(f"stage{number}_evaluation_types={types!r} but stage {number} does not apply")
            if types and len(set(types)) != len(types):
                raise ValueError(f"stage{number}_evaluation_types repeats a type: {types!r}")
        if self.stage1_evaluation_types and not set(self.stage1_evaluation_types) <= set(STAGE1_TYPES):
            raise ValueError(
                f"stage1_evaluation_types={self.stage1_evaluation_types!r} includes a physical verification; "
                f"Stage 1 allows only {STAGE1_TYPES}"
            )
        if self.external_standard_cited != (self.external_standard_name is not None):
            raise ValueError("external_standard_cited and external_standard_name disagree")
        return self


def derive_evaluation_stage(evaluation_method_raw: str) -> str:
    """Lexical check: which literal stage labels appear in the Method of Evaluation text."""
    has_stage1 = "Stage 1" in evaluation_method_raw
    has_stage2 = "Stage 2" in evaluation_method_raw
    if has_stage1 and has_stage2:
        return "Both"
    if has_stage1:
        return "Stage 1"
    if has_stage2:
        return "Stage 2"
    raise ValueError("no 'Stage 1' or 'Stage 2' label found in Method of Evaluation text")


def parse_source(path: Path) -> list[dict]:
    """Split the hand-transcribed source file into one chunk per sub-clause."""
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"^### ", text, flags=re.MULTILINE)[1:]

    field_re = re.compile(r"^(" + "|".join(FIELD_NAMES) + r"):\s*(.*)$")
    chunks = []
    for block in blocks:
        lines = block.strip().splitlines()
        clause_id = lines[0].strip()

        fields: dict[str, str] = {}
        current_key = None
        for line in lines[1:]:
            match = field_re.match(line)
            if match:
                current_key = match.group(1)
                fields[current_key] = match.group(2).strip()
            elif current_key and line.strip():
                fields[current_key] += " " + line.strip()

        missing = [name for name in FIELD_NAMES if name not in fields]
        if missing:
            raise ValueError(f"{clause_id}: source block is missing field(s) {missing}")

        guidance = fields["GUIDANCE"].strip()
        chunks.append(
            {
                "clause_id": clause_id,
                "source_page": int(fields["PAGE"]),
                "section": fields["SECTION"],
                "parameter": fields["PARAMETER"],
                "requirement_text": fields["REQUIREMENT"],
                "evaluation_method_raw": fields["EVALUATION_METHOD"],
                "evaluation_stage": derive_evaluation_stage(fields["EVALUATION_METHOD"]),
                "guidance_text": None if guidance == "(none)" else guidance,
            }
        )
    return chunks


# A standard is any ISO / IEC / IS designation with a number, or a bare ASTM / SAE / ANSI.
STANDARD_RE = re.compile(r"\b(?:ISO(?:/IEC)?|IEC|IS)\s*\d[\d\-–]*|\bASTM\b|\bSAE\b|\bANSI\b")


def _normalise(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("–", "-").replace("—", "-")).upper()


def standards_missing(chunk: dict, llm_output: dict) -> list[str]:
    """Standards named in the source text of this clause that external_standard_name leaves out."""
    source = " ".join(
        t for t in (chunk["requirement_text"], chunk["evaluation_method_raw"], chunk["guidance_text"]) if t
    )
    named = _normalise(llm_output.get("external_standard_name") or "")
    return sorted({m for m in STANDARD_RE.findall(source) if _normalise(m) not in named})


def call_llm(client, chunk: dict, hint: str = "") -> dict:
    user_prompt = (
        f"Evaluation stage(s) present (determined programmatically): {chunk['evaluation_stage']}\n"
        f"Parameter/Characteristics: {chunk['parameter']}\n"
        f"Compliance Criteria (with Requirements): {chunk['requirement_text']}\n"
        f"Method of Evaluation: {chunk['evaluation_method_raw']}\n"
        f"Guidance on method of evaluation: {chunk['guidance_text'] or '(none)'}"
        + (f"\n\nNOTE: {hint}" if hint else "")
    )
    sampling = {} if TEMPERATURE.lower() == "default" else {"temperature": float(TEMPERATURE)}
    response = client.chat.completions.create(
        model=MODEL,
        **sampling,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_schema", "json_schema": RESPONSE_SCHEMA},
    )
    return json.loads(response.choices[0].message.content)


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set.")

    chunks = parse_source(SOURCE_PATH)
    if len(chunks) != 17:
        sys.exit(f"Expected 17 sub-clauses, parsed {len(chunks)}. Check the source file.")

    from openai import OpenAI

    client = OpenAI()

    raw_outputs: dict[str, dict] = {}
    rows: list[dict] = []
    errors: list[str] = []

    for chunk in chunks:
        clause_id = chunk["clause_id"]
        print(f"Extracting {clause_id}...", file=sys.stderr)
        try:
            llm_output = call_llm(client, chunk)
            missing = standards_missing(chunk, llm_output)
            if missing:  # one retry, naming exactly what was left out
                print(f"  {clause_id}: standards left out ({', '.join(missing)}); retrying once", file=sys.stderr)
                llm_output = call_llm(
                    client,
                    chunk,
                    hint=(
                        f"Your previous answer left out these standards named in the text above: "
                        f"{', '.join(missing)}. Return the full JSON again with every standard included "
                        "in external_standard_name and external_standard_cited set to true."
                    ),
                )
                missing = standards_missing(chunk, llm_output)
                if missing:
                    errors.append(f"{clause_id}: standards named in the source but missing from the output: {missing}")
                    continue
        except Exception as exc:  # noqa: BLE001 - report and continue to next clause
            errors.append(f"{clause_id}: LLM call failed - {exc}")
            continue

        raw_outputs[clause_id] = llm_output

        row_data = {
            "clause_id": clause_id,
            "section": chunk["section"],
            "parameter": chunk["parameter"],
            "requirement_text": chunk["requirement_text"],
            "evaluation_method_raw": chunk["evaluation_method_raw"],
            "evaluation_stage": chunk["evaluation_stage"],
            "guidance_text": chunk["guidance_text"],
            "source_page": chunk["source_page"],
            **llm_output,
        }
        try:
            row = MatrixRow.model_validate(row_data)
        except ValidationError as exc:
            errors.append(f"{clause_id}: schema validation failed - {exc}")
            continue
        rows.append(row.model_dump())

    RAW_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUT_PATH.write_text(json.dumps(raw_outputs, indent=2), encoding="utf-8")

    if errors:
        sys.exit("\n".join(errors) + f"\n\n{len(errors)} row(s) failed - fix and re-run before matrix.json is written.")

    if len(rows) != 17:
        sys.exit(f"Expected 17 validated rows, got {len(rows)}.")

    MATRIX_PATH.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    PROVENANCE_PATH.write_text(
        json.dumps({"model": MODEL, "provider": "OpenAI", "generated_on": date.today().isoformat()}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} rows to {MATRIX_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
