from __future__ import annotations

import warnings

from .sbml_reader import read_sbml
from .spreadsheet_writer import write_spreadsheet, write_csv


def convert_sbml_to_spreadsheet(sbml_path: str, output_path: str, template_path: str = None, rule_format: str = "operators", output_csv: bool = False):
    """
    Convert an SBML-qual file to SpreadSBML spreadsheet format (XLSX or CSV).
    
    Args:
        sbml_path: Path to input SBML file
        output_path: Path to output file. For CSV output, this is the prefix for output files.
        template_path: Optional path to template.xlsx for README and Appendix sheets (XLSX only)
        rule_format: Format for transition rules - "operators" (default, uses >=, <=, etc.) or "colon" (uses : notation)
        output_csv: If True, output as CSV files instead of XLSX
    
    Returns:
        Tuple of (message_list, created_files)
            - message_list: List of messages (info and warnings)
            - created_files: List of created file paths (for CSV, multiple files; for XLSX, single file)
    """
    # Suppress openpyxl warnings
    warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
    
    # Capture warnings during SBML reading
    message_list = []
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        # Read SBML
        model = read_sbml(sbml_path)
        
        # Capture any warnings
        for warning in w:
            warning_msg = str(warning.message)
            message_list.append(warning_msg)
            print(warning_msg)
    
    # Add info messages
    species_msg = f"Found {len(model.species)} species"
    transitions_msg = f"Found {len(model.transitions)} transitions"
    interactions_msg = f"Found {len(model.interactions)} interactions"
    
    print(species_msg)
    print(transitions_msg)
    print(interactions_msg)
    
    message_list.append(species_msg)
    message_list.append(transitions_msg)
    message_list.append(interactions_msg)
    
    # Write output
    if output_csv:
        created_files = write_csv(model, output_path, rule_format)
    else:
        actual_path = write_spreadsheet(model, output_path, template_path, rule_format)
        created_files = [actual_path]
    
    return message_list, created_files

