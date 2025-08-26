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

### Notes

- The reader ignores a first README sheet if present, and reads `Model`, `Species`, `Transitions`, and `Interactions`.
- Reverse conversion (SBML ➜ Spreadsheet) is TODO.
