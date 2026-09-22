# DGCA CS-UAS Compliance Traceability Matrix: Spec

## 1. Goal

Turn a bounded slice of DGCA's *Certification Scheme for Unmanned Aircraft Systems* (Gazette notification, 26 Jan 2022), Part 3 (Certification Criteria), Annexure A into a structured, browsable compliance traceability matrix. Each row is one compliance sub-clause, with a plain-language paraphrase, the verification method the scheme specifies, a subsystem tag, and an explicit flag for any clause that refers to an external standard (IEC, ISO, ASTM, SAE, IS) that is not reproduced in the document. The flag shows a reader which further documents a clause depends on.

## 2. Scope and non-goals

- One slice only (Section 3). The other seven Annexure A sections (General, Performance, Powerplant, Data Link, Secure Flight Module, Instruments, Qualification Testing) are not covered.
- Public, static and read-only: no login, no user accounts.
- No LLM calls at request time. Extraction runs once, offline; the deployed app only reads a static file.
- The matrix flags references to external standards. It does not interpret what those standards require.
- No chat or Q&A layer over the data.

## 3. Source scope

**Document:** Certification Scheme for Unmanned Aircraft Systems, Part 3 (Certification Criteria), Annexure A, "Requirements (Technical Criteria) for UAS". [DGCA portal](https://www.dgca.gov.in/digigov-portal/?baseLocale=en_US?page=5068/4998/servicename) — search Drones/UAS for the Certification Scheme and related documents; this page does not link to it directly.

**This is an independent project, not affiliated with or endorsed by DGCA.** Verify against the official Gazette before relying on this matrix for compliance decisions.

**Slice:** Section 4 (Structure) and Section 5 (Material and Construction), gazette pages 140-143.

- 4.1 Strength requirements, sub-items (a)-(e)
- 4.2 Shock absorbing mechanism of UAS, sub-items (a)-(b)
- 5.1 Type of material for construction, sub-items (a)-(c)
- 5.2 Fabrication Method, sub-items (a)-(c)
- 5.3 Means of protection against deterioration or loss of strength, sub-items (a)-(b)
- 5.4 Fire resistant identification plate on UAS, sub-items (a)-(b)

That is 17 sub-clauses.

Why this slice: Structure and Material requirements apply regardless of drone category or use case (quad, hex, VTOL, agriculture, logistics and mapping platforms all share airframe and material integrity requirements). Sections such as Data Link or Secure Flight Module are conditional on BVLOS, night operations or category. Every row in this slice is therefore readable without first working out whether it applies to the reader.

## 4. Data schema

One row per lettered sub-clause. The published `data/matrix.json` contains exactly these fields.

| Column | Type | Source |
|---|---|---|
| `clause_id` | string | Given directly, e.g. `"4.1(c)"` |
| `section` | string | Given directly, e.g. `"Structure"` or `"Material and Construction"` |
| `parameter` | string | From the "Parameter/Characteristics" column, e.g. `"Strength requirements"` |
| `requirement_text` | string | Verbatim, trimmed, from the "Compliance Criteria" column |
| `plain_paraphrase` | string | LLM-generated, one or two plain-language sentences that stay close to the clause's own wording: same modal verb (must, should, may) and terms, no added requirements or verification sentences |
| `evaluation_method_raw` | string | Verbatim, trimmed, from the "Method of Evaluation" column: the actual stage and test text, kept alongside the classified fields below |
| `evaluation_stage` | enum: `Stage 1` \| `Stage 2` \| `Both` | Computed in code: which literal "Stage 1" / "Stage 2" labels appear in `evaluation_method_raw` |
| `stage1_evaluation_types` | array of enum (see Section 5), or null | LLM classification of how the clause is evaluated at Stage 1. Only `records verification`, `design/analysis review` or `laboratory test`: Stage 1 is a review of the application (design, analysis, records, laboratory reports), and physical inspection, ground test and flight test happen only at Stage 2. One type normally; more than one only when the source allows a substitute or alternative route, or the method differs by category. Primary route first. Null only if `evaluation_stage` is `Stage 2` alone. |
| `stage2_evaluation_types` | array of enum (see Section 5), or null | The same for Stage 2. Null only if `evaluation_stage` is `Stage 1` alone. |
| `evaluation_alternative_note` | string or null | A plain-language sentence saying when an alternative or substitute evaluation route is accepted (e.g. 5.1: analysis or FEA may be submitted if laboratory test reports are not available). Set only when more than one type is listed for a stage because of an alternative route; otherwise null. Not an alternative route: different calculation tools within one route (handbook methods and FEA are both design/analysis review), equivalent standards, supporting documents, or activities that merely precede the verification. Differences by category belong in `category_variation_note`. |
| `guidance_text` | string or null | Verbatim, trimmed, from the "Guidance on method of evaluation" column. Null only if that cell is blank in the source. |
| `applicable_categories` | array, subset of `["Micro", "Small", "Medium"]` | Which categories the requirement itself applies to. The Certification Criteria cover only these three categories (Part 3 §2.6). Defaults to all three. |
| `category_variation_note` | string or null | A plain-language line describing how the requirement or its verification method differs across categories, when it does (e.g. 4.1(a): static load test for Medium and above, theoretical analysis sufficient for the others). Null when uniform. |
| `subsystem_tag` | enum or null | The physical part the clause is about: `Fasteners`, `Propellers`, `Landing gear` or `Identification plate`. A closed list, so the same part always gets the same tag; the shock absorbing mechanism is part of the landing gear. The airframe or structure as a whole is not a subsystem. Null when the clause applies system-wide, to the airframe or structure as a whole, or to materials in general and names no specific part. The list was written for this slice; extending to another section means adding parts. |
| `requirement_type` | enum (see Section 5) | The nature of the requirement: `Structural strength`, `Shock absorption`, `Fastener security`, `Vibration`, `Clearance`, `Material suitability`, `Fabrication`, `Deterioration protection` or `Identification`. |
| `external_standard_cited` | boolean | Whether the clause names or requires a named external standard, in the Compliance Criteria, Method of Evaluation or Guidance cell |
| `external_standard_name` | string or null | Every standard cited, in one fixed format. Standards that must all be met are separated by `"; "`. Where the clause lets the reader meet the requirement with one of several standards, those alternatives are joined by `" OR "` within one item (e.g. `"ISO 9999; ASTM D123 OR ISO 456 OR equivalent"`, with made-up standards). Never separated by commas. Null if `external_standard_cited` is false. |
| `source_page` | integer | Gazette page number the clause appears on |
| `llm_confidence_note` | string | One line: anything the model was unsure how to classify, or `"none"` |

This schema is the contract. If the extraction output does not match it exactly, fix the extraction before touching the UI; the UI must not compensate for a loose schema.

## 5. Extraction interface

**Input.** One sub-clause's raw text: the Parameter/Characteristics cell, the Compliance Criteria cell, the Method of Evaluation cell and the Guidance on method of evaluation cell, plus the clause id, source page and evaluation stage already determined in code (the model is never asked to infer those).

The Guidance column is part of the input. Several external-standard citations appear only there (for example, clause 5.1's ASTM reference is in its Guidance cell and nowhere else), so leaving it out would undercount `external_standard_cited`.

**Output.** A single JSON object containing only the fields the model is responsible for: `plain_paraphrase`, `stage1_evaluation_types`, `stage2_evaluation_types`, `evaluation_alternative_note`, `applicable_categories`, `category_variation_note`, `subsystem_tag`, `requirement_type`, `external_standard_cited`, `external_standard_name` and `llm_confidence_note`. Fields that are verbatim source text (`clause_id`, `section`, `parameter`, `requirement_text`, `evaluation_method_raw`, `guidance_text`, `source_page`) and `evaluation_stage` are set by code, not regenerated by the model. Use structured output (a JSON schema with enums) rather than parsing free text.

`applicable_categories` and `category_variation_note` let the matrix answer, structurally, whether compliance burden varies by drone category, instead of leaving that buried in a sentence inside `evaluation_method_raw`.

**Run settings.** The published data was generated with OpenAI's `gpt-5.6-luna`. The script records the model in `data/provenance.json` and the app shows it. The model is set with `OPENAI_MODEL` (default `gpt-5.6-luna`). This model accepts only the default temperature, so `OPENAI_TEMPERATURE` defaults to `default`, which omits the parameter; runs are then sampled and not exactly reproducible. For a model that accepts it, set `OPENAI_TEMPERATURE=0` for near-identical repeat runs.

**Prompt template**

```
SYSTEM:
You are extracting one row of a compliance traceability matrix from a DGCA
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
guessing.

USER:
Evaluation stage(s) present (determined programmatically): {evaluation_stage}
Parameter/Characteristics: {parameter}
Compliance Criteria (with Requirements): {requirement_text}
Method of Evaluation: {evaluation_method_raw}
Guidance on method of evaluation: {guidance_text}
```

## 6. Pipeline and file layout

```
clearflight-matrix/
  source/
    cs_uas_annexure_a_structure_material.txt   # hand-transcribed text of the
                                                # 17 sub-clauses, pages 140-143
  extract.py            # splits the source into 17 chunks, derives the stage,
                        # calls the LLM per chunk, validates, writes data/matrix.json
  data/
    matrix.json         # the static output: 17 rows matching the schema
    provenance.json     # the model that generated the data (shown in the app)
  app.py                # Streamlit app, reads data/matrix.json and nothing else
  requirements.txt
  SPEC.md
  README.md              # repo landing page: what it is, how to run, links here
  LICENSE                # MIT, covers the code only, not the DGCA source text
```

Steps:

1. **Source text.** Get clean text for the 17 sub-clauses out of the PDF. The gazette table (multi-line cells, nested lettered sub-items) confuses naive `pdftotext` or `pypdf` extraction, so check the raw extraction against the printed page and hand-clean the 17 short entries.
2. **Split.** Split into 17 chunks, each carrying its `clause_id`, `parameter`, `requirement_text`, `evaluation_method_raw`, `guidance_text`, `source_page` and the derived `evaluation_stage`.
3. **Extract.** Run the extraction prompt (Section 5) per chunk.
4. **Check, validate and write.** For each clause, compare the standards named in its source text (an ISO, IEC or IS designation with a number, or ASTM, SAE, ANSI) with `external_standard_name`. A clause with a standard missing is retried once with the missing names spelled out, and fails if it is still missing. Then merge the model output with the known fields, validate every row against the schema (a pydantic model), and write `data/matrix.json` together with `data/provenance.json` (model and date). Nothing is written if any row fails.
5. **App.** `app.py` loads `matrix.json` (fresh on each run) and shows:
   - **Banners** at the top: the output is a draft and not a substitute for engineer sign-off, and how many clauses cite an external standard.
   - **Source and provenance:** a link to the DGCA source page, and a line naming the model that generated the summaries and classifications (read from `data/provenance.json`), stating that the requirement, method and guidance text is verbatim from the source.
   - **Search** over `requirement_text`, above the results.
   - **Filters**, in this order: UAS category, subsystem, requirement type, evaluation stage, Stage 1 evaluation type, Stage 2 evaluation type, external standard, and a checkbox for clauses citing an external standard.
     - *Cascading:* each filter offers only the values still possible after the filters above it, with a count beside each value.
     - *Category:* it does not hide clauses that apply to every category. A caption says how many clauses apply to every category and which differ in verification, and selecting a category lists those clauses' `category_variation_note`.
     - *Subsystem:* clauses with a null `subsystem_tag` are grouped as "Not tied to a specific part".
     - *Stage:* "involves" semantics. Involves Stage 1 includes clauses that also have a Stage 2; Involves both stages requires both. The Stage 1 and Stage 2 evaluation type filters appear only when that stage is involved, and a clause matches a type filter if any of its types match.
     - *External standard:* one option per named standard, built by splitting `external_standard_name` on `"; "` and `" OR "`. Open-ended alternatives ("equivalent", "any other appropriate standard") are not offered as names. A clause matches if it names any selected standard, including as one of several alternatives. The filter is hidden when no remaining clause names a standard.
   - **Matrix table:** one row per sub-clause with requirement type, subsystem, plain-language summary, stage, the evaluation types for each stage (alternatives shown joined by "or"), external standard and page.
   - **Source text by clause:** one expander per parent clause (4.1 to 5.4) showing the parameter once, with a table of its sub-clauses giving the verbatim requirement, method of evaluation and guidance, plus category and model notes. When filters are active only matching sub-clauses are shown, the expanders open, and parents with no match are hidden.

   Both tables are HTML tables so that long text wraps. All text from the data is HTML-escaped.
6. **Deploy.** Streamlit Community Cloud (or Hugging Face Spaces) from a public repository. No secrets are needed at deploy time because the running app makes no API calls.

## 7. Acceptance criteria

- `data/matrix.json` contains exactly 17 rows, one per sub-clause in Section 3, with every schema field populated (nulls only where the schema allows them).
- `evaluation_stage` on every row matches the literal "Stage 1" / "Stage 2" labels in `evaluation_method_raw`, and each stage's type list is null exactly when that stage is absent and is a non-empty list without repeats otherwise.
- Clauses that allow an alternative evaluation route (5.1(a)-(c)) list every route in the stage type list and carry an `evaluation_alternative_note`. Clauses about the airframe or structure as a whole (4.1(a), 4.1(b)) have a null `subsystem_tag`.
- Clause 4.1(a) lists `laboratory test` (a static load test, for Medium and above) and `design/analysis review` (for the others) at Stage 1 and has no `evaluation_alternative_note`, because the difference is by category. Clause 5.4(a) lists `laboratory test` and `records verification` with an `evaluation_alternative_note` (a manufacturer's certificate is accepted for certified fire-resistant material).
- No Stage 1 type list contains `physical inspection`, `ground test` or `flight test`; those occur only at Stage 2. This is enforced by the output schema (the Stage 1 enum excludes them) and by a validator.
- `subsystem_tag` is one of the four allowed values, or null, on every row; 4.2(a) and 4.2(b) both read `Landing gear`.
- `data/provenance.json` names the model that produced the data, and the app shows it together with a link to the DGCA source page.
- Paraphrases keep the clause's modal verb and terms and add nothing the Compliance Criteria text does not state (for example 5.3(b) says "material design values", and 5.4(a) has no added evidence sentence).
- Every standard named in a clause's source text appears in that row's `external_standard_name`; `extract.py` enforces this.
- `external_standard_name` follows the fixed format in Section 4 on every row: `"; "` between standards that must all be met, `" OR "` between alternatives, no commas. Clause 5.3(b) shows its temperature standard and its humidity alternatives (IS 9000 Part 4 OR IEC 60068-2-78 OR equivalent) as separate items.
- `requirement_type` is one of the nine allowed values on every row.
- At least one row has `external_standard_cited: true` with a real standard name, and rows that cite more than one standard list all of them (5.1(b) cites both ISO/IEC 17025 and ASTM).
- Clause 4.1(a) has a non-null `category_variation_note` and `applicable_categories` of all three categories.
- The deployed app loads with no login, the draft banner is visible without scrolling, and the filters behave as described in Section 6: cascading options, "involves" stage semantics, stage type filters shown only for an involved stage, and long text wrapping in both tables.

## 8. Possible extension

Extend to another Annexure A section (for example Powerplant) with the same schema. The `requirement_type` list was written for this slice and would need new values.
