from __future__ import annotations

from .spreadsheet_reader import read_spreadsheet_to_model
from .sbml_writer import write_sbml
import libsbml


def convert_spreadsheet_to_sbml(input_xlsx: str, output_sbml: str, *, interactions_anno: bool = True, transitions_anno: bool = True) -> None:
    im = read_spreadsheet_to_model(input_xlsx)
    doc = write_sbml(im, interactions_anno=interactions_anno, transitions_anno=transitions_anno)
    writer = libsbml.SBMLWriter()
    if not writer.writeSBMLToFile(doc, output_sbml):
        raise RuntimeError("Failed to write SBML file")