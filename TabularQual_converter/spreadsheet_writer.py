from __future__ import annotations

from typing import List, Dict, Any
import openpyxl
from openpyxl.styles import Font, PatternFill
from pathlib import Path
import shutil

from .types import QualModel, Person
from . import spec

def write_spreadsheet(model: QualModel, output_path: str, template_path: str = None, rule_format: str = "operators"):
    """Write QualModel to spreadsheet format
    
    Args:
        model: The in-memory model to write
        output_path: Path to output spreadsheet file
        template_path: Optional path to template.xlsx for README and Appendix sheets
        rule_format: Format for transition rules - "operators" (default, uses >=, <=, etc.) or "colon" (uses : notation)
    """
    
    # Use template if provided, otherwise create new workbook
    if template_path and Path(template_path).exists():
        # Copy template to output
        shutil.copy(template_path, output_path)
        wb = openpyxl.load_workbook(output_path)
        
        # Remove data sheets if they exist, keep README and Appendix
        for sheet_name in ['Model', 'Species', 'Transitions', 'Interactions']:
            if sheet_name in wb.sheetnames:
                del wb[sheet_name]
    else:
        wb = openpyxl.Workbook()
        # Remove default sheet
        if 'Sheet' in wb.sheetnames:
            del wb['Sheet']
    
    # Determine insertion position (after README if it exists)
    insert_pos = 1 if 'README' in wb.sheetnames else 0
    
    # Create sheets in order: README, Model, Species, Interactions, Transitions, Appendix
    _write_model_sheet(wb, model, insert_pos)
    _write_species_sheet(wb, model, insert_pos + 1)
    _write_interactions_sheet(wb, model, insert_pos + 2)
    _write_transitions_sheet(wb, model, insert_pos + 3, rule_format)
    
    # Save
    wb.save(output_path)
    wb.close()


def _write_model_sheet(wb: openpyxl.Workbook, model: QualModel, position: int = 0):
    """Write Model sheet"""
    ws = wb.create_sheet("Model", position)
    
    # No headers for Model sheet
    required_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    
    # Data rows (start from row 1)
    row = 1
    
    # Model_source
    ws.cell(row=row, column=1, value="Model_source")
    if model.model.source_urls:
        ws.cell(row=row, column=2, value=", ".join(_url_to_compact_id(url) for url in model.model.source_urls))
    row += 1
    
    # Model_ID (required)
    cell = ws.cell(row=row, column=1, value="Model_ID")
    cell.fill = required_fill
    ws.cell(row=row, column=2, value=model.model.model_id)
    row += 1
    
    # Name
    ws.cell(row=row, column=1, value="Name")
    if model.model.name:
        ws.cell(row=row, column=2, value=model.model.name)
    row += 1
    
    # Publication
    ws.cell(row=row, column=1, value="Publication")
    if model.model.described_by:
        ws.cell(row=row, column=2, value=", ".join(_url_to_compact_id(url) for url in model.model.described_by))
    row += 1
    
    # Origin_publication & Origin_model (from derived_from)
    origin_pubs = []
    origin_models = []
    if model.model.derived_from:
        for url in model.model.derived_from:
            compact_id = _url_to_compact_id(url)
            if 'biomodels' in compact_id.lower():
                origin_models.append(compact_id)
            else:
                origin_pubs.append(compact_id)
    
    ws.cell(row=row, column=1, value="Origin_publication")
    if origin_pubs:
        ws.cell(row=row, column=2, value=", ".join(origin_pubs))
    row += 1
    
    ws.cell(row=row, column=1, value="Origin_model")
    if origin_models:
        ws.cell(row=row, column=2, value=", ".join(origin_models))
    row += 1
    
    # Taxon
    ws.cell(row=row, column=1, value="Taxon")
    if model.model.taxons:
        ws.cell(row=row, column=2, value=", ".join(_url_to_compact_id(taxon) for taxon in model.model.taxons))
    row += 1
    
    # Biological_process
    ws.cell(row=row, column=1, value="Biological_process")
    if model.model.biological_processes:
        ws.cell(row=row, column=2, value=", ".join(_url_to_compact_id(process) for process in model.model.biological_processes))
    row += 1
    
    # Created
    ws.cell(row=row, column=1, value="Created")
    created_value = model.model.created_iso
    if not created_value:
        # Fallback to current time if not set
        from datetime import datetime, timezone
        created_value = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ws.cell(row=row, column=2, value=created_value)
    row += 1
    
    # Modified - use current timestamp
    from datetime import datetime, timezone
    ws.cell(row=row, column=1, value="Modified")
    ws.cell(row=row, column=2, value=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    row += 1
    
    # Creators
    max_creators = max(2, len(model.model.creators))
    for idx in range(1, max_creators + 1):
        ws.cell(row=row, column=1, value=f"Creator{idx}")
        if idx <= len(model.model.creators):
            ws.cell(row=row, column=2, value=_person_to_string(model.model.creators[idx - 1]))
        row += 1
    
    # Contributors
    max_contributors = max(2, len(model.model.contributors))
    for idx in range(1, max_contributors + 1):
        ws.cell(row=row, column=1, value=f"Contributor{idx}")
        if idx <= len(model.model.contributors):
            ws.cell(row=row, column=2, value=_person_to_string(model.model.contributors[idx - 1]))
        row += 1
    
    # Version
    ws.cell(row=row, column=1, value="Version")
    if model.model.versions:
        # Format as "Version: version1, version2, ..." if multiple versions
        version_str = ", ".join(model.model.versions)
        if len(model.model.versions) > 1 or not version_str.startswith("Version:"):
            version_str = f"Version: {version_str}"
        ws.cell(row=row, column=2, value=version_str)
    row += 1
    
    # Notes
    max_notes = max(3, len(model.model.notes))
    for idx in range(1, max_notes + 1):
        ws.cell(row=row, column=1, value=f"Notes{idx}")
        if idx <= len(model.model.notes):
            ws.cell(row=row, column=2, value=model.model.notes[idx - 1])
        row += 1
    
    # Comments - add TabularQual version
    ws.cell(row=row, column=1, value="Comments")
    ws.cell(row=row, column=2, value=f"Created by TabularQual version {spec.VERSION}")
    row += 1
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 80


def _write_species_sheet(wb: openpyxl.Workbook, model: QualModel, position: int = 0):
    """Write Species sheet"""
    ws = wb.create_sheet("Species", position)
    
    # Header style
    header_fill = PatternFill(start_color="F3F3F3", end_color="F3F3F3", fill_type="solid")
    header_font = Font(bold=True)
    required_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    
    # Group annotations by qualifier and determine max unique qualifiers
    max_qualifiers = 0
    max_notes = 0
    for species in model.species.values():
        # Group by qualifier
        grouped = {}
        for qualifier, identifier in species.annotations:
            if qualifier not in grouped:
                grouped[qualifier] = []
            grouped[qualifier].append(identifier)
        max_qualifiers = max(max_qualifiers, len(grouped))
        max_notes = max(max_notes, len(species.notes))
    
    # Ensure at least 2 Relation/Identifier pairs
    max_qualifiers = max(max_qualifiers, 2)
    # Ensure at least Notes1 column
    max_notes = max(max_notes, 1)
    
    # Build headers
    headers = ["Species_ID", "Name"]
    
    # Add Relation/Identifier pairs
    for i in range(max_qualifiers):
        headers.extend([f"Relation{i + 1}", f"Identifier{i + 1}"])
    
    headers.extend(["Compartment", "Type", "Constant", "InitialLevel", "MaxLevel"])
    
    # Add Notes
    for i in range(max_notes):
        headers.append(f"Notes{i + 1}")
    
    headers.append("Comments")
    
    # Write headers
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        if header == "Species_ID":
            cell.fill = required_fill
    
    # Write species data
    for row_idx, species in enumerate(sorted(model.species.values(), key=lambda s: s.species_id), 2):
        col = 1
        
        # Species_ID
        ws.cell(row=row_idx, column=col, value=species.species_id)
        col += 1
        
        # Name
        ws.cell(row=row_idx, column=col, value=species.name)
        col += 1
        
        # Annotations - group by qualifier and combine identifiers
        grouped_annos = {}
        for qualifier, identifier in species.annotations:
            if qualifier not in grouped_annos:
                grouped_annos[qualifier] = []
            grouped_annos[qualifier].append(_url_to_compact_id(identifier))
        
        for i in range(max_qualifiers):
            if i < len(grouped_annos):
                qualifier = list(grouped_annos.keys())[i]
                identifiers = grouped_annos[qualifier]
                ws.cell(row=row_idx, column=col, value=qualifier)
                ws.cell(row=row_idx, column=col + 1, value=", ".join(identifiers))
            col += 2
        
        # Compartment
        ws.cell(row=row_idx, column=col, value=species.compartment)
        col += 1
        
        # Type (not in our data structure, skip)
        col += 1
        
        # Constant
        if species.constant is not None:
            ws.cell(row=row_idx, column=col, value=str(species.constant))
        col += 1
        
        # InitialLevel
        if species.initial_level is not None:
            ws.cell(row=row_idx, column=col, value=species.initial_level)
        col += 1
        
        # MaxLevel
        if species.max_level is not None:
            ws.cell(row=row_idx, column=col, value=species.max_level)
        col += 1
        
        # Notes - write each note to separate column
        for i in range(max_notes):
            if i < len(species.notes):
                ws.cell(row=row_idx, column=col, value=species.notes[i])
            col += 1
        
        # Comments (skip)
        col += 1
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 30


def _write_transitions_sheet(wb: openpyxl.Workbook, model: QualModel, position: int = 0, rule_format: str = "operators"):
    """Write Transitions sheet"""
    ws = wb.create_sheet("Transitions", position)
    
    # Header style
    header_fill = PatternFill(start_color="F3F3F3", end_color="F3F3F3", fill_type="solid")
    header_font = Font(bold=True)
    required_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    
    # Group annotations by qualifier and determine max unique qualifiers
    max_qualifiers = 0
    max_notes = 0
    for transition in model.transitions:
        # Group by qualifier
        grouped = {}
        for qualifier, identifier in transition.annotations:
            if qualifier not in grouped:
                grouped[qualifier] = []
            grouped[qualifier].append(identifier)
        max_qualifiers = max(max_qualifiers, len(grouped))
        max_notes = max(max_notes, len(transition.notes))
    
    # Ensure at least 1 Relation/Identifier pair
    max_qualifiers = max(max_qualifiers, 1)
    # Ensure at least Notes1 column
    max_notes = max(max_notes, 1)
    
    # Build headers
    headers = ["Transition_ID", "Name", "Target", "Level", "Rule"]
    
    # Add Relation/Identifier pairs
    for i in range(max_qualifiers):
        headers.extend([f"Relation{i + 1}", f"Identifier{i + 1}"])
    
    # Add Notes
    for i in range(max_notes):
        headers.append(f"Notes{i + 1}")
    
    headers.append("Comments")
    
    # Write headers
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        if header in ["Target", "Rule"]:
            cell.fill = required_fill
    
    # Write transition data
    for row_idx, transition in enumerate(model.transitions, 2):
        col = 1
        
        # Transitions_ID
        ws.cell(row=row_idx, column=col, value=transition.transition_id)
        col += 1
        
        # Name
        ws.cell(row=row_idx, column=col, value=transition.name)
        col += 1
        
        # Target
        ws.cell(row=row_idx, column=col, value=transition.target)
        col += 1
        
        # Level
        if transition.level is not None:
            ws.cell(row=row_idx, column=col, value=transition.level)
        col += 1
        
        # Rule - convert format if needed
        rule = transition.rule
        if rule_format == "colon":
            rule = _convert_rule_to_colon(rule)
        ws.cell(row=row_idx, column=col, value=rule)
        col += 1
        
        # Annotations - group by qualifier and combine identifiers
        grouped_annos = {}
        for qualifier, identifier in transition.annotations:
            if qualifier not in grouped_annos:
                grouped_annos[qualifier] = []
            grouped_annos[qualifier].append(_url_to_compact_id(identifier))
        
        for i in range(max_qualifiers):
            if i < len(grouped_annos):
                qualifier = list(grouped_annos.keys())[i]
                identifiers = grouped_annos[qualifier]
                ws.cell(row=row_idx, column=col, value=qualifier)
                ws.cell(row=row_idx, column=col + 1, value=", ".join(identifiers))
            col += 2
        
        # Notes
        for i in range(max_notes):
            if i < len(transition.notes):
                ws.cell(row=row_idx, column=col, value=transition.notes[i])
            col += 1
        
        # Comments
        col += 1
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['E'].width = 40


def _write_interactions_sheet(wb: openpyxl.Workbook, model: QualModel, position: int = 0):
    """Write Interactions sheet"""
    # Always create the sheet, even if no interactions
    ws = wb.create_sheet("Interactions", position)
    
    # Header style
    header_fill = PatternFill(start_color="F3F3F3", end_color="F3F3F3", fill_type="solid")
    header_font = Font(bold=True)
    
    # Group annotations by qualifier and determine max unique qualifiers
    max_qualifiers = 0
    max_notes = 0
    for interaction in model.interactions:
        # Group by qualifier
        grouped = {}
        for qualifier, identifier in interaction.annotations:
            if qualifier not in grouped:
                grouped[qualifier] = []
            grouped[qualifier].append(identifier)
        max_qualifiers = max(max_qualifiers, len(grouped))
        max_notes = max(max_notes, len(interaction.notes))
    
    # Ensure at least 1 Relation/Identifier pair
    max_qualifiers = max(max_qualifiers, 1)
    # Ensure at least Notes1 column
    max_notes = max(max_notes, 1)
    
    # Build headers
    headers = ["Target", "Source", "Sign"]
    
    # Add Relation/Identifier pairs
    for i in range(max_qualifiers):
        headers.extend([f"Relation{i + 1}", f"Identifier{i + 1}"])
    
    # Add Notes
    for i in range(max_notes):
        headers.append(f"Notes{i + 1}")
    
    headers.append("Comments")
    
    # Write headers
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
    
    # Write interaction data
    for row_idx, interaction in enumerate(model.interactions, 2):
        col = 1
        
        # Target
        ws.cell(row=row_idx, column=col, value=interaction.target)
        col += 1
        
        # Source
        ws.cell(row=row_idx, column=col, value=interaction.source)
        col += 1
        
        # Sign
        ws.cell(row=row_idx, column=col, value=interaction.sign)
        col += 1
        
        # Annotations - group by qualifier and combine identifiers
        grouped_annos = {}
        for qualifier, identifier in interaction.annotations:
            if qualifier not in grouped_annos:
                grouped_annos[qualifier] = []
            grouped_annos[qualifier].append(_url_to_compact_id(identifier))
        
        for i in range(max_qualifiers):
            if i < len(grouped_annos):
                qualifier = list(grouped_annos.keys())[i]
                identifiers = grouped_annos[qualifier]
                ws.cell(row=row_idx, column=col, value=qualifier)
                ws.cell(row=row_idx, column=col + 1, value=", ".join(identifiers))
            col += 2
        
        # Notes
        for i in range(max_notes):
            if i < len(interaction.notes):
                ws.cell(row=row_idx, column=col, value=interaction.notes[i])
            col += 1
        
        # Comments
        col += 1
    
    # Adjust column widths
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 15


def _url_to_compact_id(url: str) -> str:
    """Convert identifiers.org URL to compact ID
    
    Handles:
    - identifiers.org/ncbigene:7132 -> ncbigene:7132
    - identifiers.org/ncbigene/7132 -> ncbigene:7132 (slash to colon)
    - Other URLs are kept as-is
    """
    if "identifiers.org/" in url:
        # Extract the part after identifiers.org/
        parts = url.split("identifiers.org/")
        if len(parts) > 1:
            compact_id = parts[1]
            # Convert slash to colon if present (e.g., ncbigene/7132 -> ncbigene:7132)
            # Only convert the first slash to maintain compatibility with nested identifiers
            if "/" in compact_id and ":" not in compact_id:
                compact_id = compact_id.replace("/", ":", 1)
            return compact_id
    return url


def _person_to_string(person: Person) -> str:
    """Convert Person object to formatted string"""
    parts = []
    if person.family_name:
        parts.append(person.family_name)
    if person.given_name:
        parts.append(person.given_name)
    if person.organization:
        parts.append(f'"{person.organization}"')
    if person.email:
        parts.append(person.email)
    return ", ".join(parts) if parts else ""


def _convert_rule_to_colon(rule: str) -> str:
    """Convert rule from operator format to colon format
    
    Examples:
        A >= 2 -> A:2
        B < 2 -> !B:2
        C = 0 -> !C
        D = 1 -> D
        E >= 1 -> E
    """
    import re
    
    # Handle >= operator (replace with colon notation)
    # A >= 2 becomes A:2, but A >= 1 becomes A
    def replace_geq(match):
        var = match.group(1)
        threshold = match.group(2)
        if threshold == '1':
            return var
        return f"{var}:{threshold}"
    
    rule = re.sub(r'(\w+)\s*>=\s*(\d+)', replace_geq, rule)
    
    # Handle < operator (replace with negation and colon notation)
    # A < 2 becomes !A:2, but A < 1 becomes !A
    def replace_lt(match):
        var = match.group(1)
        threshold = match.group(2)
        if threshold == '1':
            return f"!{var}"
        return f"!{var}:{threshold}"
    
    rule = re.sub(r'(\w+)\s*<\s*(\d+)', replace_lt, rule)
    
    # Handle = operator
    # A = 0 becomes !A, A = 1 becomes A, A = N becomes A:N
    def replace_eq(match):
        var = match.group(1)
        threshold = match.group(2)
        if threshold == '0':
            return f"!{var}"
        elif threshold == '1':
            return var
        return f"{var}:{threshold}"
    
    rule = re.sub(r'(\w+)\s*=\s*(\d+)', replace_eq, rule)
    
    # Handle == operator (same as =)
    def replace_eqeq(match):
        var = match.group(1)
        threshold = match.group(2)
        if threshold == '0':
            return f"!{var}"
        elif threshold == '1':
            return var
        return f"{var}:{threshold}"
    
    rule = re.sub(r'(\w+)\s*==\s*(\d+)', replace_eqeq, rule)
    
    return rule