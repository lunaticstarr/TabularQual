from __future__ import annotations

import warnings

from .sbml_reader import read_sbml
from .spreadsheet_writer import write_spreadsheet, write_csv
from .tools import validate_sbml_file


def convert_sbml_to_spreadsheet(sbml_path: str, output_path: str, template_path: str = None, rule_format: str = "operators", output_csv: bool = False, print_messages: bool = True, validate: bool = True):
    """
    Convert an SBML-qual file to SpreadSBML spreadsheet format (XLSX or CSV).
    
    Args:
        sbml_path: Path to input SBML file
        output_path: Path to output file. For CSV output, this is the prefix for output files.
        template_path: Optional path to template.xlsx for README and Appendix sheets (XLSX only)
        rule_format: Format for transition rules - "operators" (default, uses >=, <=, etc.) or "colon" (uses : notation)
        output_csv: If True, output as CSV files instead of XLSX
        print_messages: Whether to print messages to console (set False for app use)
        validate: Whether to validate SBML annotations using sbmlutils (default True)
    
    Returns:
        Tuple of (message_list, created_files, result)
            - message_list: List of messages (info and warnings)
            - created_files: List of created file paths (for CSV, multiple files; for XLSX, single file)
            - result: Dict with validation info
    """
    # Suppress openpyxl warnings
    warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
    
    # Capture warnings during SBML reading
    message_list = []
    
    # Validate input SBML annotations first (if enabled)
    if validate:
        # For CLI (print_messages=True): limit to 10, for app (print_messages=False): get all
        max_errors = 10 if print_messages else None
        validation_result = validate_sbml_file(sbml_path, max_errors=max_errors, print_messages=print_messages)
    else:
        validation_result = {'errors': [], 'total_errors': 0}
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        # Read SBML
        model = read_sbml(sbml_path)
        
        # Capture any warnings
        for warning in w:
            warning_msg = str(warning.message)
            message_list.append(warning_msg)
            if print_messages:
                print(warning_msg)
    
    # Add info messages
    species_msg = f"Found {len(model.species)} species"
    transitions_msg = f"Found {len(model.transitions)} transitions"
    interactions_msg = f"Found {len(model.interactions)} interactions"
    
    if print_messages:
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
    
    # Create result dict with validation info
    result = {
        'messages': message_list,
        'created_files': created_files,
        'validation_errors': validation_result.get('errors', []),
        'total_validation_errors': validation_result.get('total_errors', 0)
    }
    
    return message_list, created_files, result

