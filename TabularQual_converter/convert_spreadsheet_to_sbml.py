from __future__ import annotations

from pathlib import Path
from .spreadsheet_reader import read_spreadsheet_to_model, detect_csv_input, read_csv_to_model
from .sbml_writer import write_sbml
import libsbml
import gc

def _get_version_info() -> str:
    """Get version information for TabularQual and libSBML"""
    try:
        from . import spec
        tabularqual_version = spec.VERSION
    except Exception:
        tabularqual_version = "unknown"
    
    try:
        libsbml_version = libsbml.getLibSBMLDottedVersion()
    except Exception:
        libsbml_version = "unknown"
    
    return f"Created by TabularQual version {tabularqual_version} with libSBML version {libsbml_version}"

def convert_spreadsheet_to_sbml(input_path: str, output_sbml: str, *, interactions_anno: bool = True, transitions_anno: bool = True) -> dict:
    """Convert spreadsheet (XLSX or CSV) to SBML and return statistics and warnings.
    
    Args:
        input_path: Path to input file. Can be:
            - An XLSX file path
            - A CSV file path (will look for sibling CSV files)
            - A directory containing CSV files
            - A prefix for CSV files (e.g., 'Example' for Example_Species.csv, etc.)
        output_sbml: Path to output SBML file
        interactions_anno: Whether to include interaction annotations
        transitions_anno: Whether to include transition annotations
    
    Returns:
        dict: Statistics including 'species', 'transitions', 'interactions' counts, and 'warnings' list
    """
    input_p = Path(input_path)
    
    # Check if input is XLSX
    if input_p.is_file() and input_p.suffix.lower() in ('.xlsx', '.xls'):
        im, validation_warnings = read_spreadsheet_to_model(input_path)
    else:
        # Try CSV detection
        is_csv, csv_files, csv_warnings = detect_csv_input(input_path)
        
        if is_csv:
            # Print CSV detection warnings
            for warning in csv_warnings:
                print(f"Warning: {warning}")
            
            # Check for required files
            if 'Species' not in csv_files or 'Transitions' not in csv_files:
                missing = []
                if 'Species' not in csv_files:
                    missing.append('Species')
                if 'Transitions' not in csv_files:
                    missing.append('Transitions')
                raise ValueError(f"Missing required CSV file(s): {', '.join(missing)}")
            
            im, validation_warnings = read_csv_to_model(csv_files)
            # Prepend CSV detection warnings
            validation_warnings = csv_warnings + validation_warnings
        else:
            # Fallback to XLSX (will raise error if file doesn't exist)
            im, validation_warnings = read_spreadsheet_to_model(input_path)
    
    # Print warnings to console
    for warning in validation_warnings:
        if warning.startswith("Found ") or warning.startswith("No "):
            print(warning)  # Info messages
        else:
            print(f"Warning: {warning}")  # Actual warnings
    
    # Collect stats
    stats = {
        'species': len(im.species),
        'transitions': len(im.transitions),
        'interactions': len(im.interactions),
        'warnings': validation_warnings
    }
    
    sbml_string = write_sbml(im, interactions_anno=interactions_anno, transitions_anno=transitions_anno)
    
    # Clean up model
    del im
    gc.collect()
    
    # Get version info
    version_comment = f"<!-- {_get_version_info()} -->\n"

    lines = sbml_string.split('\n')
    
    # Check if XML declaration is present
    if lines and lines[0].startswith('<?xml'):
        # XML declaration exists, insert comment after it
        lines.insert(1, version_comment)
    else:
        # No XML declaration, add it as first line, then version comment
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>'
        lines.insert(0, xml_declaration)
        lines.insert(1, version_comment)
    
    # Write the modified SBML to file
    with open(output_sbml, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    return stats