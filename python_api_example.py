"""
TabularQual Python API Examples
================================

Install:
    pip install tabularqual

Or install from source:
    git clone https://github.com/sys-bio/TabularQual.git
    cd TabularQual
    pip install -e .

The two main functions:
    convert_spreadsheet_to_sbml(input_path, output_path, **options)
    convert_sbml_to_spreadsheet(input_path, output_path, **options)

Both return a stats dict:
    {
        "species":                 int,
        "transitions":             int,
        "interactions":            int,
        "warnings":                list[str],   # all messages produced
        "validation_errors":       list[str],   # annotation validation issues
        "total_validation_errors": int,
        "created_files":           list[str],   # output file paths
    }
"""

import os
from tabularqual import convert_spreadsheet_to_sbml, convert_sbml_to_spreadsheet

_CLEANUP: list[str] = []   # accumulate temp files for final removal


# ── 1. Basic Boolean model (XLSX → SBML) ────────────────────────────────────
print("=== 1. XLSX → SBML (Boolean model) ===")
stats = convert_spreadsheet_to_sbml(
    "examples/ToyExample.xlsx",
    "out_boolean.sbml",
)
print(f"  Species: {stats['species']}, Transitions: {stats['transitions']}")
_CLEANUP.append("out_boolean.sbml")


# ── 2. SBML → XLSX ─────────────────────────────────────────────
print("\n=== 2. SBML → XLSX ===")
stats = convert_sbml_to_spreadsheet(
    "out_boolean.sbml",
    "out_boolean.xlsx",
)
print(f"  Output: {stats['created_files']}")
_CLEANUP.append("out_boolean.xlsx")


# ── 3. SBML → CSV files ──────────────────────────────────────────────────────
print("\n=== 3. SBML → CSV files ===")
stats = convert_sbml_to_spreadsheet(
    "out_boolean.sbml",
    "out_boolean",      # prefix; creates out_boolean_Model.csv, etc.
    output_csv=True,
)
print(f"  Created: {[os.path.basename(f) for f in stats['created_files']]}")
_CLEANUP.extend(stats["created_files"])


# ── 4. CSV folder → SBML ─────────────────────────────────────────────────────
print("\n=== 4. CSV folder → SBML ===")
stats = convert_spreadsheet_to_sbml(
    "examples/ToyExample_csv/",   # folder containing ToyExample_*.csv
    "out_from_csv.sbml",
)
print(f"  Species: {stats['species']}")
_CLEANUP.append("out_from_csv.sbml")


# ── 5. Multi-valued model ────────────────────────────────────────────────────
# Multi-valued models have MaxLevel > 1 and rules that use threshold
# comparisons (A >= 2, B:2) or XOR (A ^ B).
# Each result level gets its own row in the Transitions sheet.
#
# Example rule excerpt from ThieffryThomas1995:
#   Target  Level  Rule
#   CycD    1      E2F1 | GF
#   RB      1      !CycD & !CycE & !CycA & !CycB
#   RB      2      !CycD:2 & !CycE:2 & !CycA:2 & !CycB:2
#   E2F1    1      !RB & !CycA & !CycB
#   E2F1    2      !RB:2 & !CycA & !CycB
#
print("\n=== 5. Multi-valued model (XLSX → SBML) ===")
stats = convert_spreadsheet_to_sbml(
    "examples/ThieffryThomas1995/ThieffryThomas1995_multivalue.xlsx",
    "out_multivalue.sbml",
)
print(f"  Species: {stats['species']}, Transitions: {stats['transitions']}")
_CLEANUP.append("out_multivalue.sbml")

# Round-trip with colon notation (A:2 instead of A >= 2)
stats = convert_sbml_to_spreadsheet(
    "out_multivalue.sbml",
    "out_multivalue_colon.xlsx",
    rule_format="colon",
)
print(f"  Round-trip (colon notation): {stats['created_files']}")
_CLEANUP.append("out_multivalue_colon.xlsx")


# ── 6. Reading and filtering warnings ────────────────────────────────────────
print("\n=== 6. Inspecting warnings ===")
stats = convert_spreadsheet_to_sbml(
    "examples/ToyExample.xlsx",
    "out_inspect.sbml",
    print_messages=False,   # suppress console output; handle programmatically
    validate=False,
)
all_warnings = stats["warnings"]

# Separate informational messages from actionable warnings
info  = [w for w in all_warnings if w.startswith("Found ") or w.startswith("No ")]
sid   = [w for w in all_warnings if "Invalid SId" in w or "Duplicate ID" in w]
other = [w for w in all_warnings if w not in info and w not in sid]

print(f"  Info messages : {len(info)}")
print(f"  SId fixes     : {len(sid)}")
print(f"  Other warnings: {len(other)}")
for w in other:
    print(f"    • {w}")
_CLEANUP.append("out_inspect.sbml")


# ── 7. Suppress all annotations (lean SBML) ──────────────────────────────────
print("\n=== 7. Lean SBML (no interaction/transition annotations) ===")
stats = convert_spreadsheet_to_sbml(
    "examples/ToyExample.xlsx",
    "out_lean.sbml",
    interactions_anno=False,
    transitions_anno=False,
    validate=False,
    print_messages=False,
)
print(f"  Done. File size: {os.path.getsize('out_lean.sbml')} bytes")
_CLEANUP.append("out_lean.sbml")


# ── Cleanup ──────────────────────────────────────────────────────────────────
for f in _CLEANUP:
    try:
        os.remove(f)
    except FileNotFoundError:
        pass
print("\nAll temporary files removed.")
