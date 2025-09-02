from __future__ import annotations

from .spreadsheet_reader import read_spreadsheet_to_model
from .sbml_writer import write_sbml
import libsbml

def _get_version_info() -> str:
    """Get version information for TabularQual and libSBML"""
    try:
        import pkg_resources
        tabularqual_version = pkg_resources.get_distribution("tabularqual").version
    except Exception:
        tabularqual_version = "unknown"
    
    try:
        libsbml_version = libsbml.getLibSBMLDottedVersion()
    except Exception:
        libsbml_version = "unknown"
    
    return f"Created by TabularQual version {tabularqual_version} with libSBML version {libsbml_version}"

def convert_spreadsheet_to_sbml(input_xlsx: str, output_sbml: str, *, interactions_anno: bool = True, transitions_anno: bool = True) -> None:
    im = read_spreadsheet_to_model(input_xlsx)
    sbml_string = write_sbml(im, interactions_anno=interactions_anno, transitions_anno=transitions_anno)
    
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