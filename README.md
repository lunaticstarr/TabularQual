## TabularQual converter

Convert between spreadsheets (XLSX, CSV) and SBML-qual for logical models (Boolean and multi-valued).

![TabularQual](doc/tabularqual.png "Example TabularQual spreadsheet representation of a Boolean model")

Note: the format is specified [here](doc/TabularQual_specification_v0.1.3.docx).

### Install

Install directly from PyPI:

```bash
pip install tabularqual
```

Or install from source (developmental):

```bash
git clone https://github.com/sys-bio/TabularQual.git
cd TabularQual
pip install -e .
```

### Usage

TabularQual can be used directly in **web app**, as a **Python package**, or via the **command line (CLI)**.

#### Web App

Use directly in your browser -- no installation required!

**[Launch Web App](https://tabularqual.streamlit.app/)**

Note: there are currently resource limits on Streamlit cloud, please switch to a local version for large networks by running:

```bash
streamlit run app.py
```

#### Python API

```python
from tabularqual import convert_spreadsheet_to_sbml, convert_sbml_to_spreadsheet

# Spreadsheet to SBML (accepts XLSX file, CSV folder, or CSV prefix)
stats = convert_spreadsheet_to_sbml("Model.xlsx", "Model.sbml")

# SBML to Spreadsheet
stats = convert_sbml_to_spreadsheet("Model.sbml", "Model.xlsx")

# SBML to CSV files
stats = convert_sbml_to_spreadsheet("Model.sbml", "Model", output_csv=True)
```

Both functions return a `dict` with conversion statistics:

```python
{
    'species': 10,           # number of species
    'transitions': 10,       # number of transitions
    'interactions': 25,      # number of interactions
    'warnings': [...],       # list of warning/info messages
    'created_files': [...],  # output files created (to-table only)
}
```

See [`examples/python_api_example.py`](examples/python_api_example.py) for a complete working example.

#### CLI

##### Spreadsheet to SBML

```bash
# Simple usage (output defaults to input name with .sbml extension)
to-sbml examples/ToyExample.xlsx

# From CSV directory
to-sbml examples/ToyExample_csv/

# From CSV files (using prefix - looks for Model_Species.csv, Model_Transitions.csv, etc.)
to-sbml Model
```

##### SBML to Spreadsheet

```bash
# Simple usage (output defaults to input name with .xlsx extension)
to-table examples/ToyExample.sbml

# To CSV files (creates Model_Model.csv, Model_Species.csv, etc.)
to-table examples/ToyExample.sbml --csv
```

#### Options

`to-sbml INPUT [OUTPUT]`:

- **INPUT**: input file/path. Supports XLSX, CSV file, directory with CSVs, or CSV prefix (e.g., `Model` for `Model_Species.csv`, `Model_Transitions.csv`, etc.)
- **OUTPUT**: output SBML file (optional, defaults to input name with `.sbml` extension)
- **--inter-anno**: use interaction annotations only (unless `--trans-anno` is also set)
- **--trans-anno**: use transition annotations only (unless `--inter-anno` is also set)
- **--use-name**: when referring to species, names have been used in the spreadsheet (default: use ID)
- **--no-validate**: skip annotation validation

`to-table INPUT [OUTPUT]`:

- **INPUT**: input SBML file
- **OUTPUT**: output file/prefix (optional, defaults to input name)
- **--csv**: output as CSV files (`{prefix}_Model.csv`, `{prefix}_Species.csv`, `{prefix}_Transitions.csv`, `{prefix}_Interactions.csv`)
- **--template**: specify a template file for README and Appendix sheets (XLSX only)
- **--colon-format**: use colon notation for transition rules (`:` means `>=`)
- **--use-name**: use Species Name instead of ID in rules and interactions for better readability (default: use ID)
- **--no-validate**: skip annotation validation

### Transition Rules Syntax

The Rule column supports boolean and comparison expressions (spaces are ignored). See [doc/transition_rule_syntax.md](doc/transition_rule_syntax.md) for full details.

* **Logical operators**: `&` (AND), `|` (OR), `!` (NOT), `^` (XOR)
* **Parentheses**: `(` and `)` for grouping expressions
* **For multi-valued models**: threshold-based activation
  * **Colon notation**: `A:2` means "A is at level 2 or higher" (`A >= 2`)
  * **Negated colon**: `!A:2` means "A is below level 2" (`A < 2`)
  * **Explicit comparisons**: `A >= 2`, `B <= 1`, `C != 0` for precise control
  * **Equivalent expressions**: `!CI:2 & !Cro:3` is the same as `CI < 2 & Cro < 3` or `CI <= 1 & Cro <= 2`
* **Constant rules**:
  * **Boolean values**: `TRUE` / `FALSE` means the target will be fixed at level 1 / 0
  * **Integers**: target will be fixed at the level (for multi-valued models, this can be `2`, `3`, ...)

**Examples**:

- `A & B` - Both A and B are active (level ≥ 1 for multi-valued)
- `A ^ B` - Exactly one of A or B is active (XOR)
- `A:2 | B < 1` - A is at level 2+ OR B is inactive
- `N & !CI:2 & !Cro:3` - N active AND CI below level 2 AND Cro below level 3
- `(A & B) | (!C & D != 1)` - Complex grouped expression

Note: When importing SBML-qual files, the tool follows the spec (section 5.1): symbolic threshold references in MathML (e.g., `<ci>theta_t9_ex</ci>`) are replaced with their numeric `thresholdLevel` values. For Boolean models (threshold 0 or 1), the result is simplified to pure Boolean form (e.g., `A >= 1` → `A`, `A < 1` → `!A`).

### Validation

TabularQual performs several validations during conversion to ensure data quality and SBML compliance.

#### SId Format Validation

Model_ID, Species_ID, Transitions_ID, and Compartment fields must conform to the SBML SId specification (SBML Level 3 Version 2):

- Must start with a letter (A–Z, a–z) or underscore (`_`)
- May contain only letters, digits (0–9), and underscores
- Case-sensitive (equality determined by exact string matching)
- No spaces, slashes, or other special characters allowed
- Unique across their sheets

**Automatic Cleanup**: If an ID doesn't conform, it is automatically cleaned:

- Special characters (spaces, slashes, dashes, etc.) are replaced with underscores
- IDs starting with a digit get a leading underscore prepended
- Duplicate IDs are automatically renamed with suffixes (`_1`, `_2`, etc.)

**Example**: `PI3K/AKT-pathway` → `PI3K_AKT_pathway`

#### Field Value Validation

The converter validates controlled vocabulary fields:

- **Species Type**: Must be one of `Input`, `Internal`, or `Output` (case-insensitive)
- **Interaction Sign**: Must be one of `positive`, `negative`, `dual`, or `unknown` (case-insensitive)
- **Relation Qualifiers**: Must be one of `is`, `hasVersion`, `isVersionOf`, `isDescribedBy`, `hasPart`, `isPartOf`, `hasProperty`, `isPropertyOf`, `encodes`, `isEncodedBy`, `isHomologTo`, `occursIn`, `hasTaxon` (case-insensitive)

#### Annotation Validation

Annotations in the SBML output can be validated using `sbmlutils`:

- Validates that annotation URIs are correctly formed
- Checks that identifiers.org resources are valid
- Enable/disable with `--no-validate` flag or checkbox in web app

To use annotation validation: `pip install sbmlutils>=0.9.6`

### Notes

- The reader ignores a first README sheet if present, and reads `Model`, `Species`, `Transitions`, and `Interactions`.
- The SBML to Spreadsheet converter automatically uses `doc/template.xlsx` if available for README and Appendix sheets (XLSX output only).
- When `--use-name` is enabled, the converter uses **Species Name** in transition rules and interactions instead of Species_ID.
  - If a name conforms to SId format and is unique, it's used directly. Otherwise, it's quoted: `"Name"` or gets suffixes for duplicates: `"Name_1"`, `"Name_2"`, etc.
  - If any species are missing Names when `--use-name` is enabled, a warning is issued and IDs are used instead.
  - When `--use-name` is enabled, Species_ID becomes optional and is automatically generated from Names if missing.
- TODO: automatically detect Species:Type
