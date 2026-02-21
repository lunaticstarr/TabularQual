"""
TabularQual Python API Example
==============================

Install:
    pip install tabularqual

Or install from source:
    git clone https://github.com/sys-bio/TabularQual.git
    cd TabularQual
    pip install -e .

"""

from tabularqual import convert_spreadsheet_to_sbml, convert_sbml_to_spreadsheet

print("Spreadsheet to SBML")
stats = convert_spreadsheet_to_sbml(
    "examples/ToyExample_csv/",     # XLSX file, CSV folder, or CSV prefix
    "output_model.sbml",            # Output SBML file
)


print("--------------------------------")
print("SBML to Spreadsheet (XLSX)")
stats = convert_sbml_to_spreadsheet(
    "output_model.sbml",            # Input SBML file
    "output_model.xlsx",            # Output XLSX file
)


print("--------------------------------")
print("SBML to CSV files")
stats = convert_sbml_to_spreadsheet(
    "output_model.sbml",
    "output_model",                 # Prefix for CSV files
    output_csv=True,
)


# Options

print("--------------------------------")
print("Use colon notation for rules (A:2 instead of A >= 2)")
stats = convert_sbml_to_spreadsheet(
    "output_model.sbml",
    "output_colon.xlsx",
    rule_format="colon",
)

print("--------------------------------")
print("Use species names instead of IDs in rules")
stats = convert_sbml_to_spreadsheet(
    "output_model.sbml",
    "output_names.xlsx",
    use_name=True,
)

print("--------------------------------")
print("Suppress console output")
stats = convert_sbml_to_spreadsheet(
    "output_model.sbml",
    "output_quiet.xlsx",
    print_messages=False,
)
# All info is in the returned dict
print("--------------------------------")
print(f"Species: {stats['species']}")
print(f"Warnings: {len(stats['warnings'])}")


# --- Cleanup ---
import os
for f in ["output_model.sbml", "output_model.xlsx", "output_colon.xlsx",
          "output_names.xlsx", "output_quiet.xlsx"]:
    if os.path.exists(f):
        os.remove(f)
# CSV files
for f in stats.get("created_files", []):
    if os.path.exists(f):
        os.remove(f)
for suffix in ["_Model.csv", "_Species.csv", "_Transitions.csv", "_Interactions.csv"]:
    f = f"output_model{suffix}"
    if os.path.exists(f):
        os.remove(f)
