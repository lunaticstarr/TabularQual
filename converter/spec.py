from __future__ import annotations

# sheet names
SHEET_MODEL = "Model"
SHEET_SPECIES = "Species"
SHEET_TRANSITIONS = "Transitions"
SHEET_INTERACTIONS = "Interactions"  # optional

# Model sheet columns
MODEL_ID = "Model_ID"
MODEL_NAME = "Name"
MODEL_SOURCE = "Model_source"
MODEL_PUBLICATION = "Publication"
MODEL_ORIGIN_PUBLICATION = "Origin_publication"
MODEL_ORIGIN_MODEL = "Origin_model"
MODEL_TAXON = "Taxon"
MODEL_BIOLOGICAL_PROCESS = "Biological_process"
MODEL_CREATED = "Created"
MODEL_MODIFIED = "Modified"
MODEL_CREATOR_PREFIX = "Creator"
MODEL_CONTRIBUTOR_PREFIX = "Contributor"
MODEL_VERSION = "Version"
MODEL_NOTES_PREFIX = "Notes"

# Species sheet columns
SPECIES_ID = "Species_ID"
SPECIES_NAME = "Name"
SPECIES_RELATION_PREFIX = "Relation"
SPECIES_IDENTIFIER_PREFIX = "Identifier"
SPECIES_COMPARTMENT = "Compartment"
SPECIES_TYPE = "Type"  # Input/Internal/Output
SPECIES_CONSTANT = "Constant"
SPECIES_INITIAL_LEVEL = "InitialLevel"
SPECIES_MAX_LEVEL = "MaxLevel"
SPECIES_NOTES_PREFIX = "Notes"

# Interactions sheet columns (optional)
INTER_TARGET = "Target"
INTER_SOURCE = "Source"
INTER_SIGN = "Sign"  # positive, negative, dual, unknown
INTER_RELATION_PREFIX = "Relation"
INTER_IDENTIFIER_PREFIX = "Identifier"
INTER_NOTES_PREFIX = "Notes"

# Transitions sheet columns
TRANSITION_ID = "Transitions_ID"
TRANSITION_NAME = "Name"
TRANSITION_TARGET = "Target"
TRANSITION_LEVEL = "Level"
TRANSITION_RULE = "Rule"
TRANSITION_RELATION_PREFIX = "Relation"
TRANSITION_IDENTIFIER_PREFIX = "Identifier"
TRANSITION_NOTES_PREFIX = "Notes"

# Default compartment name if none provided
DEFAULT_COMPARTMENT = "default"

# Allowed boolean symbols
SYMBOL_AND = "&"
SYMBOL_OR = "|"
SYMBOL_NOT = "!"

# TODO: extend for multi-valued thresholds like A:2

def is_repeated_column(column_name: str, prefix: str) -> bool:
    if not column_name.startswith(prefix):
        return False
    # Accept exact or numeric suffix like Relation2, Identifier10
    if column_name == prefix:
        return True
    suffix = column_name[len(prefix):]
    return suffix.isdigit() and len(suffix) > 0


