from __future__ import annotations

import click
from pathlib import Path
from .convert_spreadsheet_to_sbml import convert_spreadsheet_to_sbml
from .convert_sbml_to_spreadsheet import convert_sbml_to_spreadsheet


@click.group()
def main():
    pass


def _resolve_annotation_flags(inter_anno: bool, trans_anno: bool) -> tuple[bool, bool]:
    # If neither or both are provided, use both
    if (not inter_anno and not trans_anno) or (inter_anno and trans_anno):
        return True, True
    # Only one provided: select that one exclusively
    if inter_anno:
        return True, False
    return False, True


def _check_input_exists(input_path: str) -> bool:
    """Check if input exists - supports files, directories, and CSV prefixes."""
    p = Path(input_path)
    if p.exists():
        return True
    
    # Check if it's a prefix for CSV files
    # Handle both relative ("test") and absolute ("/path/to/test") paths
    if p.is_absolute():
        base_dir = p.parent
    else:
        base_dir = Path.cwd() / p.parent if str(p.parent) != '.' else Path.cwd()
    
    prefix = p.name.lower()
    
    if not base_dir.exists():
        return False
    
    for f in base_dir.iterdir():
        if f.is_file() and f.suffix.lower() == '.csv':
            if f.stem.lower().startswith(prefix + '_'):
                return True
    
    return False


@click.command(name="to-sbml")
@click.option("--input", "input_path", required=True, type=click.Path(), help="Input file: XLSX, CSV file, directory with CSVs, or CSV prefix (e.g., 'Example' for Example_Species.csv)")
@click.option("--output", "output_sbml", required=True, type=click.Path(dir_okay=False))
@click.option("--inter-anno", is_flag=True, default=False, help="Use interaction annotations only (unless --trans-anno also set)")
@click.option("--trans-anno", is_flag=True, default=False, help="Use transition annotations only (unless --inter-anno also set)")
def to_sbml_entry(input_path: str, output_sbml: str, inter_anno: bool, trans_anno: bool):
    # Validate input exists
    if not _check_input_exists(input_path):
        raise click.ClickException(f"Input not found: {input_path}")
    
    interactions_anno, transitions_anno = _resolve_annotation_flags(inter_anno, trans_anno)
    try:
        convert_spreadsheet_to_sbml(
            input_path,
            output_sbml,
            interactions_anno=interactions_anno,
            transitions_anno=transitions_anno,
        )
    except ValueError as e:
        raise click.ClickException(str(e))
    click.echo(f"Wrote SBML to {output_sbml}")


@click.command(name="to-table")
@click.option("--input", "input_sbml", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "output_path", required=True, type=click.Path(), help="Output path: XLSX file path or CSV prefix (with --csv flag)")
@click.option("--template", "template_xlsx", type=click.Path(exists=True, dir_okay=False), help="Template file for README and Appendix sheets (XLSX only)")
@click.option("--colon-format", "colon_format", is_flag=True, default=False, help="Use colon notation for transition rules (A:2 means A>=2). Default uses operators (>=, <, etc.)")
@click.option("--csv", "output_csv", is_flag=True, default=False, help="Output as CSV files instead of XLSX. Output path becomes a prefix (e.g., 'Example' creates Example_Model.csv, Example_Species.csv, etc.)")
def to_table_entry(input_sbml: str, output_path: str, template_xlsx: str = None, colon_format: bool = False, output_csv: bool = False):
    # Auto-detect template if not provided (only for XLSX output)
    if template_xlsx is None and not output_csv:
        # Look for template.xlsx in doc/ directory relative to this file
        doc_dir = Path(__file__).parent.parent / "doc"
        template_path = doc_dir / "template.xlsx"
        if template_path.exists():
            template_xlsx = str(template_path)
    
    rule_format = "colon" if colon_format else "operators"
    message_list, created_files = convert_sbml_to_spreadsheet(input_sbml, output_path, template_xlsx, rule_format, output_csv)
    
    if output_csv:
        click.echo(f"Wrote CSV files:")
        for f in created_files:
            click.echo(f"  - {f}")
    else:
        click.echo(f"Wrote spreadsheet to {created_files[0]}")


# Add the commands to the main group
main.add_command(to_sbml_entry)
main.add_command(to_table_entry)


if __name__ == "__main__":
    main()