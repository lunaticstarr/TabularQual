## TabularQual converter

Convert between spreadsheets specified in [SpreadSBML specification](.doc/SpreadSBML specification.docx) and SBML-qual for logical models (Boolean and multi-valued).

### Web App

Use TabularQual directly in your browser - no installation required!

🔗 **[Launch Web App](https://tabularqual.streamlit.app/)**

Note: there are currently resource limits on Streamlit cloud, please run it locally for large networks.

---

### Install

#### Option 1: Run Web App Locally

```bash

# 1) Install dependencies
pip install -r requirements.txt

# 2) Launch the web app
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

#### Option 2: Command-Line Tools

```bash
# Install dependencies and console script
pip install -r requirements.txt
pip install -e .
```

### Usage

* Spreadsheet ➜ SBML

```bash
to-sbml \
  --input examples/Faure2006/Faure2006.xlsx \
  --output examples/Faure2006/Faure2006_out.sbml
```

#### SBML ➜ Spreadsheet

```bash
to-table \
  --input examples/Faure2006/Faure2006_out.sbml \
  --output examples/Faure2006/Faure2006_reconstructed.xlsx
```

### Options

`to-sbml`:

- **--inter-anno**: use interaction annotations only (unless `--trans-anno` is also set).
- **--trans-anno**: use transition annotations only (unless `--inter-anno` is also set).
- If you pass both `--inter-anno` and `--trans-anno` or pass neither, the converter will include **both** interaction and transition annotations.

`to-table`:

* **--template**: optionally specify a template file for README and Appendix sheets
* **--colon-format**: use colon notation for transition rules (`:` means `>=`). Default uses operators (`>=`, `<`, etc.)

Examples:

```bash
# Interactions only
to-sbml --input in.xlsx --output out.sbml --inter-anno

# Transitions only
to-sbml --input in.xlsx --output out.sbml --trans-anno

# Both (default)
to-sbml --input in.xlsx --output out.sbml

# Use doc/template.xlsx as template for creating tables
to-table --input in.sbml --output out.xlsx --template doc/template.xlsx

# Use colon notation for rules (A:2 instead of A >= 2)
to-table --input in.sbml --output out.xlsx --colon-format
```

### Transition Rules Syntax

The Transition-Rules column supports boolean and comparison expressions using the following operators and syntax (space will be ignored):

* **Logical operators**: `&` (AND), `|` (OR), `!` (NOT)
* **Parentheses**: `(` and `)` for grouping expressions
* **For multi-value model**: threshold-based activation:
  * **Colon notation**: `A:2` means "A is at level 2 or higher" (`A >= 2`)
  * **Negated colon**: `!A:2` means "A is below level 2" (`A < 2`)
  * **Explicit comparisons**: `A >= 2`, `B <= 1`, `C != 0` for precise control
  * **Equivalent expressions**: `!CI:2 & !Cro:3` is the same as `CI < 2 & Cro < 3` or `CI <= 1 & Cro <= 2`
* **Simple species references**:
  * `A` - Species A is active (level >= 1 for multi-valued, or level = 1 for binary)
  * `!A` - Species A is inactive (level = 0)

**Examples**:

- `A & B` - Both A and B are active (level ≥ 1 for multi-valued)
- `A:2 | B < 1` - A is at level 2+ OR B is inactive
- `N & !CI:2 & !Cro:3` - N active AND CI below level 2 AND Cro below level 3
- `(A & B) | (!C & D != 1)` - Complex grouped expression

**Note**: When converting SBML to spreadsheet, rules are exported in **operator format** by default (`A >= 2`, `B < 3`). Use `--colon-format` to export in colon notation (`A:2`, `!B:3`) instead.

### Notes

- The reader ignores a first README sheet if present, and reads `Model`, `Species`, `Transitions`, and `Interactions`.
- The SBML to Spreadsheet converter automatically uses `doc/template.xlsx` if available for README and Appendix sheets.
- TODO: automatically detect Species:Type, Interactions:Target, Source and Sign
