from __future__ import annotations

import warnings

from .sbml_reader import read_sbml
from .spreadsheet_writer import write_spreadsheet


def convert_sbml_to_spreadsheet(sbml_path: str, output_path: str, template_path: str = None, rule_format: str = "operators"):
    """
    Convert an SBML-qual file to SpreadSBML spreadsheet format.
    
    Args:
        sbml_path: Path to input SBML file
        output_path: Path to output spreadsheet file
        template_path: Optional path to template.xlsx for README and Appendix sheets
        rule_format: Format for transition rules - "operators" (default, uses >=, <=, etc.) or "colon" (uses : notation)
    """
    # Suppress openpyxl warnings
    warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
    
    # Read SBML
    model = read_sbml(sbml_path)
    
    # Print progress
    print(f"{len(model.species)} species found.")
    print(f"{len(model.transitions)} transitions found.")
    print(f"{len(model.interactions)} interactions found.")
    
    # Write spreadsheet
    write_spreadsheet(model, output_path, template_path, rule_format)

