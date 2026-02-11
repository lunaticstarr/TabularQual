from __future__ import annotations

from typing import List, Tuple, Dict, Optional
import libsbml
from xml.etree import ElementTree as ET
import os
import gc
import warnings
from datetime import datetime, timezone

from .types import QualModel, ModelInfo, Species, Transition, InteractionEvidence, Person


def read_sbml(sbml_path: str) -> QualModel:
    """Read an SBML-qual file and convert it to QualModel"""
    doc = libsbml.readSBMLFromFile(sbml_path)
    
    try:
        if doc.getNumErrors() > 0:
            errors = []
            for i in range(doc.getNumErrors()):
                err = doc.getError(i)
                if err.getSeverity() >= libsbml.LIBSBML_SEV_ERROR:
                    errors.append(str(err.getMessage()))
            if errors:
                raise ValueError(f"SBML parsing errors: {'; '.join(errors)}")
        
        model = doc.getModel()
        if model is None:
            raise ValueError("No model found in SBML file")
        
        qual_model = model.getPlugin("qual")
        if qual_model is None:
            raise ValueError("No qual plugin found in model")
        
        # Read model info
        model_info = _read_model_info(model, sbml_path)
        
        # Read species
        species_dict = _read_species(qual_model)
        
        # Read transitions
        transitions, interactions = _read_transitions(qual_model)
        
        result = QualModel(
            model=model_info,
            species=species_dict,
            transitions=transitions,
            interactions=interactions
        )
        
        return result
    finally:
        # delete the libsbml document
        del doc
        gc.collect()


def _read_model_info(model: libsbml.Model, sbml_path: str) -> ModelInfo:
    """Extract model-level information"""
    if model.isSetId():
        model_id = model.getId()
    else:
        # Use filename without extension if no id provided
        filename = os.path.basename(sbml_path)
        model_id = os.path.splitext(filename)[0]
    
    name = model.getName() if model.isSetName() else None
    
    # Parse notes
    notes = []
    versions = []
    if model.isSetNotes():
        notes_str = model.getNotesString()
        # Extract notes
        extracted_notes = _extract_text_from_notes(notes_str)
        for note in extracted_notes:
            # Check for version information
            if note.startswith('Version:'):
                versions.append(note.replace('Version:', '').strip())
            else:
                notes.append(note)
    
    # Parse annotations
    source_urls = []
    described_by = []
    derived_from = []
    biological_processes = []
    taxons = []
    other_annotations = []
    created_iso = None
    modified_iso = None
    creators = []
    contributors = []
    
    if model.isSetAnnotation():
        anno_str = model.getAnnotationString()
        anno_dict = _parse_rdf_annotation(anno_str)
        
        source_urls = anno_dict.get('bqmodel:is', [])
        described_by = anno_dict.get('bqmodel:isDescribedBy', [])
        derived_from = anno_dict.get('bqmodel:isDerivedFrom', [])
        biological_processes = anno_dict.get('bqbiol:isVersionOf', [])
        taxons = anno_dict.get('bqbiol:hasTaxon', [])
        
        # Timestamps
        if 'dcterms:created' in anno_dict:
            created_iso = anno_dict['dcterms:created'][0]
        if 'dcterms:modified' in anno_dict:
            modified_iso = anno_dict['dcterms:modified'][0]
        
        # Creators and contributors
        if 'dcterms:creator' in anno_dict:
            creators = anno_dict['dcterms:creator']
        if 'dcterms:contributor' in anno_dict:
            contributors = anno_dict['dcterms:contributor']
        
        # Collect other qualifiers not handled above
        known_keys = {
            'bqmodel:is', 'bqmodel:isDescribedBy', 'bqmodel:isDerivedFrom',
            'bqbiol:isVersionOf', 'bqbiol:hasTaxon',
            'dcterms:created', 'dcterms:modified', 'dcterms:creator', 'dcterms:contributor'
        }
        for key, values in anno_dict.items():
            if key not in known_keys and (key.startswith('bqmodel:') or key.startswith('bqbiol:')):
                # Store as (qualifier_name, url) tuples
                qualifier_name = key.split(':', 1)[1] if ':' in key else key
                # Print warning for unknown qualifier
                warnings.warn(f"Model annotation: Found unknown/invalid qualifier '{qualifier_name}' in SBML file. This will be stored in Model Notes.")
                for url in values:
                    other_annotations.append((qualifier_name, url))
    
    # Set current time if Created field is empty
    if not created_iso:
        created_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return ModelInfo(
        model_id=model_id,
        name=name,
        source_urls=source_urls,
        described_by=described_by,
        derived_from=derived_from,
        biological_processes=biological_processes,
        taxons=taxons,
        created_iso=created_iso,
        modified_iso=modified_iso,
        creators=creators,
        contributors=contributors,
        versions=versions,
        notes=notes,
        other_annotations=other_annotations
    )


def _read_species(qual_model) -> Dict[str, Species]:
    """Read all qualitative species"""
    species_dict = {}
    
    for i in range(qual_model.getNumQualitativeSpecies()):
        qs = qual_model.getQualitativeSpecies(i)
        species_id = qs.getId()
        name = qs.getName() if qs.isSetName() else None
        compartment = qs.getCompartment() if qs.isSetCompartment() else None
        constant = qs.getConstant() if qs.isSetConstant() else None
        initial_level = qs.getInitialLevel() if qs.isSetInitialLevel() else None
        max_level = qs.getMaxLevel() if qs.isSetMaxLevel() else None
        
        # Parse notes and extract type information
        notes = []
        species_type = None
        if qs.isSetNotes():
            notes_str = qs.getNotesString()
            all_notes = _extract_text_from_notes(notes_str)
            # Check for type information in notes
            for note in all_notes:
                if note.startswith("Type:"):
                    # Extract type value
                    type_value = note.replace("Type:", "").strip()
                    # Validate against allowed types
                    from . import spec
                    species_type = spec.normalize_type(type_value)
                else:
                    notes.append(note)
        
        # Parse annotations
        annotations = []
        if qs.isSetAnnotation():
            anno_str = qs.getAnnotationString()
            annotations = _parse_annotations_to_list(anno_str)
            # Check for unknown qualifiers and warn
            from . import spec
            for qualifier, identifier in annotations:
                if qualifier not in spec.RELATIONS:
                    warnings.warn(f"Species '{species_id}': Found unknown/invalid qualifier '{qualifier}' in SBML file.")
        
        species_dict[species_id] = Species(
            species_id=species_id,
            name=name,
            compartment=compartment,
            constant=constant,
            initial_level=initial_level,
            max_level=max_level,
            type=species_type,
            annotations=annotations,
            notes=notes
        )
    
    return species_dict


def _read_transitions(qual_model) -> Tuple[List[Transition], List[InteractionEvidence]]:
    """Read all transitions and extract interaction information"""
    transitions = []
    interactions = []
    
    for i in range(qual_model.getNumTransitions()):
        tr = qual_model.getTransition(i)
        transition_id = tr.getId() if tr.isSetId() else None
        name = tr.getName() if tr.isSetName() else None
        
        # Get target (output)
        outputs = []
        for j in range(tr.getNumOutputs()):
            out = tr.getOutput(j)
            outputs.append(out.getQualitativeSpecies())
        
        if not outputs:
            continue
        target = outputs[0]  # Should only have one output per transition
        
        # Get inputs and their signs
        inputs_with_signs = []
        for j in range(tr.getNumInputs()):
            inp = tr.getInput(j)
            source = inp.getQualitativeSpecies()
            sign = inp.getSign() if inp.isSetSign() else None
            threshold = inp.getThresholdLevel() if inp.isSetThresholdLevel() else 1
            
            # Convert libsbml sign enum to string
            sign_str = None
            if sign is not None:
                if sign == libsbml.INPUT_SIGN_POSITIVE:
                    sign_str = "positive"
                elif sign == libsbml.INPUT_SIGN_NEGATIVE:
                    sign_str = "negative"
                elif sign == libsbml.INPUT_SIGN_DUAL:
                    sign_str = "dual"
                elif sign == libsbml.INPUT_SIGN_UNKNOWN:
                    sign_str = "unknown"
            
            inputs_with_signs.append((source, sign_str, threshold))
            
            # Extract interaction-level annotations if present
            inter_notes = []
            inter_annotations = []
            if inp.isSetNotes():
                notes_str = inp.getNotesString()
                inter_notes = _extract_text_from_notes(notes_str)
            if inp.isSetAnnotation():
                anno_str = inp.getAnnotationString()
                inter_annotations = _parse_annotations_to_list(anno_str)
                # Check for unknown qualifiers and warn
                from . import spec
                for qualifier, identifier in inter_annotations:
                    if qualifier not in spec.RELATIONS:
                        warnings.warn(f"Interaction (target='{target}', source='{source}'): Found unknown/invalid qualifier '{qualifier}' in SBML file.")
            
            if sign_str or inter_annotations or inter_notes:
                interactions.append(InteractionEvidence(
                    target=target,
                    source=source,
                    sign=sign_str,
                    annotations=inter_annotations,
                    notes=inter_notes
                ))
        
        # Parse transition notes (filter out "Level X:" lines)
        notes = []
        if tr.isSetNotes():
            notes_str = tr.getNotesString()
            notes = _extract_text_from_notes(notes_str, filter_level_prefix=True)
        
        # Parse transition annotations
        annotations = []
        if tr.isSetAnnotation():
            anno_str = tr.getAnnotationString()
            annotations = _parse_annotations_to_list(anno_str)
            # Check for unknown qualifiers and warn
            from . import spec
            for qualifier, identifier in annotations:
                if qualifier not in spec.RELATIONS:
                    transition_name = transition_id if transition_id else f"target={target}"
                    warnings.warn(f"Transition '{transition_name}': Found unknown/invalid qualifier '{qualifier}' in SBML file.")
        
        # Get function terms and create separate transitions for each level
        # Collect all non-default function terms
        function_terms = []
        for j in range(tr.getNumFunctionTerms()):
            ft = tr.getFunctionTerm(j)
            if ft.isSetResultLevel() and ft.getResultLevel() > 0:  # Skip default term (level 0)
                level = ft.getResultLevel()
                rule = None
                if ft.isSetMath():
                    math_ast = ft.getMath()
                    rule = _mathml_to_rule(math_ast, inputs_with_signs)
                
                # If no rule found, create default
                if rule is None and inputs_with_signs:
                    rule = " & ".join([src for src, _, _ in inputs_with_signs])
                
                # Warn about blank or empty rules
                if not rule or rule.strip() == "" or rule.strip() == "()":
                    warnings.warn(f"Warning: Transition for target '{target}' has blank or empty rule. Setting to 1 (default level).")
                    rule = "1"

                function_terms.append((level, rule or ""))
        
        # If no function terms with rules, create one transition without level
        if not function_terms:
            rule = None
            level = None
            # Check if there's any function term at all
            for j in range(tr.getNumFunctionTerms()):
                ft = tr.getFunctionTerm(j)
                if ft.isSetMath():
                    math_ast = ft.getMath()
                    rule = _mathml_to_rule(math_ast, inputs_with_signs)
                    if ft.isSetResultLevel():
                        level = ft.getResultLevel()
                    break
            
            if rule is None and inputs_with_signs:
                rule = " & ".join([src for src, _, _ in inputs_with_signs])
            
            # Warn about blank or empty rules
            if not rule or rule.strip() == "" or rule.strip() == "()":
                warnings.warn(f"Warning: Transition for target '{target}' has blank or empty rule. Setting to 1 (default level).")
                rule = "1"
            # TODO: set the species to Constant=True if the rule is blank?

            transitions.append(Transition(
                transition_id=transition_id,
                name=name,
                target=target,
                level=level,
                rule=rule or "",
                annotations=annotations,
                notes=notes
            ))
        else:
            # Create separate transition for each function term (level)
            for idx, (level, rule) in enumerate(function_terms):
                # Create transition ID with level suffix if multiple levels
                if len(function_terms) > 1:
                    tid = f"{transition_id}_{level}" if transition_id else None
                else:
                    tid = transition_id
                
                transitions.append(Transition(
                    transition_id=tid,
                    name=name,
                    target=target,
                    level=level,
                    rule=rule,
                    annotations=annotations,
                    notes=notes
                ))
    
    return transitions, interactions


def _mathml_to_rule(math_ast, inputs_with_signs) -> str:
    """Convert MathML AST to rule string"""
    
    def convert_ast_node(node) -> str:
        """Recursively convert AST node to expression string"""
        if node is None:
            return ""
        
        node_type = node.getType()
        
        # Logical operators
        if node_type == libsbml.AST_LOGICAL_AND:
            children = [convert_ast_node(node.getChild(i)) for i in range(node.getNumChildren())]
            return " & ".join(f"({c})" if " | " in c else c for c in children)
        
        elif node_type == libsbml.AST_LOGICAL_OR:
            children = [convert_ast_node(node.getChild(i)) for i in range(node.getNumChildren())]
            return " | ".join(f"({c})" if " & " in c else c for c in children)
        
        elif node_type == libsbml.AST_LOGICAL_NOT:
            child = convert_ast_node(node.getChild(0))
            # Add parentheses if child is complex
            if " " in child:
                return f"!({child})"
            return f"!{child}"
        
        # Relational operators
        elif node_type == libsbml.AST_RELATIONAL_EQ:
            left = convert_ast_node(node.getChild(0))
            right = convert_ast_node(node.getChild(1))
            # Handle special case: "species == 1" -> just "species"
            if right == "1" or right == "1.0":
                return left
            # Handle "species == 0" -> "!species"
            elif right == "0" or right == "0.0":
                return f"!{left}"
            return f"{left} == {right}"
        
        elif node_type == libsbml.AST_RELATIONAL_NEQ:
            left = convert_ast_node(node.getChild(0))
            right = convert_ast_node(node.getChild(1))
            return f"{left} != {right}"
        
        elif node_type == libsbml.AST_RELATIONAL_LT:
            left = convert_ast_node(node.getChild(0))
            right = convert_ast_node(node.getChild(1))
            return f"{left} < {right}"
        
        elif node_type == libsbml.AST_RELATIONAL_LEQ:
            left = convert_ast_node(node.getChild(0))
            right = convert_ast_node(node.getChild(1))
            return f"{left} <= {right}"
        
        elif node_type == libsbml.AST_RELATIONAL_GT:
            left = convert_ast_node(node.getChild(0))
            right = convert_ast_node(node.getChild(1))
            return f"{left} > {right}"
        
        elif node_type == libsbml.AST_RELATIONAL_GEQ:
            left = convert_ast_node(node.getChild(0))
            right = convert_ast_node(node.getChild(1))
            # Handle "species >= 1" -> just "species"
            if right == "1" or right == "1.0":
                return left
            return f"{left} >= {right}"
        
        # Variables and constants
        elif node_type == libsbml.AST_NAME:
            return node.getName()
        
        elif node_type == libsbml.AST_INTEGER:
            return str(node.getInteger())
        
        elif node_type == libsbml.AST_REAL:
            val = node.getReal()
            if val == int(val):
                return str(int(val))
            return str(val)
        
        # Fallback
        else:
            return libsbml.formulaToL3String(node)
    
    result = convert_ast_node(math_ast)
    # Clean up empty results or "()" patterns
    if result and result.strip() in ["", "()", "(  )"]:
        return ""
    return result


def _parse_rdf_annotation(anno_str: str) -> Dict[str, List]:
    """Parse RDF annotation string into a dictionary"""
    result = {}
    
    try:
        # Parse XML
        root = ET.fromstring(anno_str)
        
        # Define namespaces
        ns = {
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'dcterms': 'http://purl.org/dc/terms/',
            'vCard': 'http://www.w3.org/2001/vcard-rdf/3.0#',
            'bqbiol': 'http://biomodels.net/biology-qualifiers/',
            'bqmodel': 'http://biomodels.net/model-qualifiers/'
        }
        
        # Find all RDF descriptions
        for desc in root.findall('.//rdf:Description', ns):
            # Parse timestamp elements
            for elem_name in ['dcterms:created', 'dcterms:modified']:
                elem = desc.find(f'.//{elem_name}', ns)
                if elem is not None:
                    dtf = elem.find('.//dcterms:W3CDTF', ns)
                    if dtf is not None and dtf.text:
                        result[elem_name] = [dtf.text]
            
            # Parse creator/contributor
            for elem_name in ['dcterms:creator', 'dcterms:contributor']:
                creators_elem = desc.find(f'.//{elem_name}', ns)
                if creators_elem is not None:
                    persons = []
                    for li in creators_elem.findall('.//rdf:li', ns):
                        person = Person()
                        n_elem = li.find('.//vCard:N', ns)
                        if n_elem is not None:
                            family = n_elem.find('.//vCard:Family', ns)
                            given = n_elem.find('.//vCard:Given', ns)
                            if family is not None and family.text:
                                person.family_name = family.text
                            if given is not None and given.text:
                                person.given_name = given.text
                        
                        org_elem = li.find('.//vCard:ORG', ns)
                        if org_elem is not None:
                            orgname = org_elem.find('.//vCard:Orgname', ns)
                            if orgname is not None and orgname.text:
                                person.organization = orgname.text
                        
                        email_elem = li.find('.//vCard:EMAIL', ns)
                        if email_elem is not None and email_elem.text:
                            person.email = email_elem.text
                        
                        persons.append(person)
                    result[elem_name] = persons
            
            # Parse resource references (URLs)
            for prefix in ['bqmodel', 'bqbiol']:
                for elem in desc.findall(f'.//{prefix}:*', ns):
                    qual_name = elem.tag.split('}')[-1]
                    key = f"{prefix}:{qual_name}"
                    urls = []
                    for li in elem.findall('.//rdf:li', ns):
                        resource = li.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource')
                        if resource:
                            urls.append(resource)
                    if urls:
                        result[key] = urls
    
    except Exception:
        pass
    
    return result


def _parse_annotations_to_list(anno_str: str) -> List[Tuple[str, str]]:
    """Parse RDF annotation into list of (qualifier, identifier) tuples"""
    annotations = []
    
    try:
        # libsbml may return annotation strings without namespace declarations
        # Add them if missing to enable proper XML parsing
        if '<rdf:RDF>' in anno_str or '<rdf:RDF ' in anno_str:
            # Check if namespace declarations are missing
            if 'xmlns:rdf=' not in anno_str:
                anno_str = anno_str.replace(
                    '<rdf:RDF',
                    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
                    'xmlns:bqbiol="http://biomodels.net/biology-qualifiers/" '
                    'xmlns:bqmodel="http://biomodels.net/model-qualifiers/" '
                    'xmlns:dcterms="http://purl.org/dc/terms/"'
                )
        
        root = ET.fromstring(anno_str)
        ns = {
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'bqbiol': 'http://biomodels.net/biology-qualifiers/',
            'bqmodel': 'http://biomodels.net/model-qualifiers/'
        }
        
        for desc in root.findall('.//rdf:Description', ns):
            for prefix in ['bqmodel', 'bqbiol']:
                for elem in desc.findall(f'.//{prefix}:*', ns):
                    qual_name = elem.tag.split('}')[-1]
                    for li in elem.findall('.//rdf:li', ns):
                        resource = li.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource')
                        if resource:
                            annotations.append((qual_name, resource))
    
    except Exception:
        pass
    
    return annotations


def _extract_text_from_notes(notes_str: str, filter_level_prefix: bool = False) -> List[str]:
    """Extract text content from XHTML notes
    
    Args:
        notes_str: The XHTML notes string
        filter_level_prefix: If True, filter out lines starting with "Level X:"
    
    Returns:
        List of note strings, where each <p> tag becomes a separate note
    """
    notes = []
    
    try:
        # Remove namespace declarations for easier parsing
        notes_str = notes_str.replace(' xmlns="http://www.w3.org/1999/xhtml"', '')
        root = ET.fromstring(notes_str)
        
        # Each <p> element becomes a separate note
        for p_elem in root.findall('.//p'):
            text = ''.join(p_elem.itertext()).strip()
            if text:
                # Check for note separator tags <notes1>...</notes1>
                import re
                pattern = r'<notes(\d+)>\s*(.*?)\s*</notes\1>'
                matches = re.findall(pattern, text, re.DOTALL)
                if matches:
                    # Extract content from each match
                    for _, content in matches:
                        content = content.strip()
                        if content:
                            # Filter out "Level X:" prefix if requested
                            if filter_level_prefix and content.startswith('Level ') and ':' in content:
                                continue
                            notes.append(content)
                else:
                    # No separators found, treat as single note
                    # Filter out "Level X:" prefix if requested
                    if filter_level_prefix and text.startswith('Level ') and ':' in text:
                        continue
                    notes.append(text)
    
    except Exception:
        # Fallback: just extract text between tags
        import re
        text = re.sub('<[^>]+>', '', notes_str)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for line in lines:
            if filter_level_prefix and line.startswith('Level ') and ':' in line:
                continue
            if line:
                notes.append(line)
    
    return notes

