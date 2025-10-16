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
    
    Returns:
        List of messages (info and warnings)
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
    
    # Write spreadsheet
    write_spreadsheet(model, output_path, template_path, rule_format)
    
    return message_list

