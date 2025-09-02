## TabularQual Converter

Convert spreadsheets specified in `SpreadSBML specification.html` to SBML-qual and back.

### Install

```bash
# 1) Create and activate a virtual environment (macOS/Linux)
python -m venv .venv
source .venv/bin/activate

# 2) Install dependencies and console script
pip install -r requirements.txt
pip install -e .
```

### Usage (Spreadsheet ➜ SBML)

```bash
to-sbml \
  --input table/Faure2006_MammalianCellCycle.xlsx \
  --output sbml/Faure2006_MammalianCellCycle_out.sbml
```

### Options

- **--inter-anno**: use interaction annotations only (unless `--trans-anno` is also set).
- **--trans-anno**: use transition annotations only (unless `--inter-anno` is also set).
- If you pass both `--inter-anno` and `--trans-anno` or pass neither, the converter will include **both** interaction and transition annotations.

Examples:

```bash
# Interactions only
to-sbml --input in.xlsx --output out.sbml --inter-anno

# Transitions only
to-sbml --input in.xlsx --output out.sbml --trans-anno

# Both (default)
to-sbml --input in.xlsx --output out.sbml
```

### Transition Rules Syntax

The Transition-Rules column supports boolean and comparison expressions using the following operators and syntax:

* **Logical operators**: `&` (AND), `|` (OR), `!` (NOT)
* **Comparison operators**: `=` (equal), `!=` (not equal), `>` (greater than), `<` (less than), `>=` (greater than or equal), `<=` (less than or equal)
* **Parentheses**: `(` and `)` for grouping expressions
* **Threshold notation**: Two forms supported:
  * Explicit: `A >= 2`, `B < 1`, `C != 0`
  * Compact: `A:2` (equivalent to `A = 2`)
* **Negated species**: `!A` (equivalent to `A = 0`)

**Examples**:

- `A & B` - Both A and B are active (level ≥ 1 for multi-valued)
- `A >= 2 | B < 1` - A is at level 2+ OR B is inactive
- `(A & B) | (!C & D != 1)` - Complex grouped expression
- `CycE:2 & !p53` - CycE at level 2 AND p53 inactive

### Notes

- The reader ignores a first README sheet if present, and reads `Model`, `Species`, `Transitions`, and `Interactions`.
- Reverse conversion (SBML ➜ Spreadsheet) and data validation is TODO.
