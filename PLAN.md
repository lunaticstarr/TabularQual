## TabularQual Converter: Plan and File Structure

### Goals
- Convert between a spreadsheet format (as specified in `SpreadSBML specification.html`) and SBML-qual.
- Phase 1: Spreadsheet (.xlsx) ➜ SBML-qual (.sbml)
- Phase 2: SBML-qual (.sbml) ➜ Spreadsheet (.xlsx) [TODO]

### High-level Plan
1. Define schemas/mappings from spreadsheet sheets/columns to SBML-qual elements and annotations per spec.
2. Implement a robust spreadsheet reader:
   - Accepts `.xlsx` files; reads required sheets: `Model`, `Species`, `Transitions`; optional sheet: `Interactions`.
   - Validates required columns; normalizes header casing and trims whitespace.
   - Supports repeated columns with numeric suffixes (e.g., `Relation1`, `Identifier1`, ...).
3. Implement SBML-qual writer using libSBML:
   - Create SBML L3V1 with Qual v1 namespace.
   - Create compartments, qualitative species, transitions, function terms.
   - Map annotations to CVTerms and model history (creators, created/modified dates) where applicable.
   - Encode rules to MathML using a small Boolean expression parser for Table 5 symbols.
4. Implement CLI for spreadsheet ➜ SBML conversion.
5. Validate with `table/Faure2006_MammalianCellCycle.xlsx` against `sbml/Faure2006_MammalianCellCycle.sbml` [manual spot checks first].
6. Phase 2 (reverse conversion) [TODO].

### File Structure
```
TabularQual-converter/
  PLAN.md                       # This plan
  requirements.txt              # Python deps
  README.md                     # Quick usage
  converter/
    __init__.py
    spec.py                     # Column names, mappings, constants
    spreadsheet_reader.py       # Read and validate spreadsheet into dataclasses
    expr_parser.py              # Parse boolean rules to an AST
    sbml_writer.py              # Create SBML-qual model using libSBML
    convert_spreadsheet_to_sbml.py  # Orchestrator function
    cli.py                      # CLI entry points
    types.py                    # Dataclasses for in-memory model
```

### Assumptions and Open Questions
- Qualifier mapping: we map common `bqmodel`/`bqbiol` qualifiers to libSBML enums; any missing enums will be marked TODO.
- Input `sign` (Interactions): SBML-qual Input supports `sign` attribute; if absent in the spec version encountered, we will omit it. [TODO: verify against libSBML version at install time]
- Multi-valued thresholds (`A:2`): initial support limited to Boolean models (threshold `:1`). [TODO: extend AST and MathML for multi-valued]
- Compartments: default to `cytosol` if unspecified; create additional compartments if provided by `Species.Compartment`.
- Notes fields: stored as XHTML notes. We will not sanitize rich text beyond basic escaping. [TODO]

### Milestones
1) Spreadsheet ➜ SBML-qual conversion (this PR)
2) Round-trip tests with example models [TODO]
3) SBML-qual ➜ Spreadsheet converter [TODO]
4) CI and validation suite [TODO]


