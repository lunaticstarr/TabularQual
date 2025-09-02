from __future__ import annotations

import click
from .convert_spreadsheet_to_sbml import convert_spreadsheet_to_sbml


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

@click.command(name="to-sbml")
@click.option("--input", "input_xlsx", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "output_sbml", required=True, type=click.Path(dir_okay=False))
@click.option("--inter-anno", is_flag=True, default=False, help="Use interaction annotations only (unless --trans-anno also set)")
@click.option("--trans-anno", is_flag=True, default=False, help="Use transition annotations only (unless --inter-anno also set)")
def to_sbml_entry(input_xlsx: str, output_sbml: str, inter_anno: bool, trans_anno: bool):
    interactions_anno, transitions_anno = _resolve_annotation_flags(inter_anno, trans_anno)
    convert_spreadsheet_to_sbml(
        input_xlsx,
        output_sbml,
        interactions_anno=interactions_anno,
        transitions_anno=transitions_anno,
    )
    click.echo(f"Wrote SBML to {output_sbml}")


# Add the command to the main group
main.add_command(to_sbml_entry)


if __name__ == "__main__":
    main()