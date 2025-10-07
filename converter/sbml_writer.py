from __future__ import annotations

from typing import List, Tuple, Dict
from datetime import datetime, timezone
import re
import libsbml

from . import spec
from .types import InMemoryModel, Species as SpeciesT, Transition as TransitionT, InteractionEvidence
from .expr_parser import parse as parse_expr, ast_to_mathml


def write_sbml(model: InMemoryModel, *, interactions_anno: bool = True, transitions_anno: bool = True) -> str:
    # Prefer constructing document with qual namespaces; fallback to enabling package
    doc = None
    try:
        ns = libsbml.QualPkgNamespaces(3, 1, 1)
        doc = libsbml.SBMLDocument(ns)
    except Exception:
        doc = libsbml.SBMLDocument(3, 1)
        try:
            qual_uri = libsbml.QualExtension.getXmlnsL3V1V1()
        except Exception:
            qual_uri = "http://www.sbml.org/sbml/level3/version1/qual/version1"
        if not doc.enablePackage(qual_uri, "qual", True):
            raise ValueError("Failed to enable qual package")

    m = doc.createModel()
    # Ensure required flag after enabling
    try:
        doc.setPackageRequired("qual", True)
    except Exception:
        pass
    m.setId(model.model.model_id)
    if model.model.name:
        m.setName(model.model.name)

    # Metaid generator
    meta_counter = 1
    def next_metaid() -> str:
        nonlocal meta_counter
        s = f"metaid_{meta_counter:07d}"
        meta_counter += 1
        return s

    # Model-level notes
    if model.model.notes:
        _append_notes(m, model.model.notes)
    if model.model.versions:
        _append_notes_concat(m, [f"Version: {v}" for v in model.model.versions])

    # Annotations for model
    if not m.isSetMetaId():
        m.setMetaId(next_metaid())
    _add_model_annotations(m, model)

    # Compartment(s)
    comp_names = set()
    for s in model.species.values():
        comp = s.compartment or spec.DEFAULT_COMPARTMENT
        comp_names.add(comp)
    if not comp_names:
        comp_names.add(spec.DEFAULT_COMPARTMENT)
    for cname in sorted(comp_names):
        c = m.createCompartment()
        c.setId(cname)
        c.setConstant(True)

    # Qual plugin
    qual_model = m.getPlugin("qual")
    if qual_model is None:
        raise ValueError("Qual plugin unavailable on model")

    # Species
    for s in model.species.values():
        qs = qual_model.createQualitativeSpecies()
        qs.setId(s.species_id)
        if not qs.isSetMetaId():
            qs.setMetaId(next_metaid())
        if s.name:
            qs.setName(s.name)
        qs.setCompartment(s.compartment or spec.DEFAULT_COMPARTMENT)
        if s.constant is not None:
            qs.setConstant(bool(s.constant))
        else: # constant attribute is required, default to False
            qs.setConstant(False)
        if s.initial_level is not None:
            qs.setInitialLevel(int(s.initial_level))
        if s.max_level is not None:
            qs.setMaxLevel(int(s.max_level))
        if s.notes:
            _append_notes(qs, s.notes)
        # TODO: add Type to notes?
        if s.annotations:
            _add_annotations(qs, s.annotations, use_model=False)

    # Group transitions by target to handle multiple levels
    transitions_by_target: Dict[str, List[TransitionT]] = {}
    for t in model.transitions:
        if t.target not in transitions_by_target:
            transitions_by_target[t.target] = []
        transitions_by_target[t.target].append(t)

    # Transitions
    for target, target_transitions in transitions_by_target.items():
        # Create one transition per target species
        qt = qual_model.createTransition()
        
        # Use the first transition's ID or generate one
        # Strip level suffix from transition ID (e.g., tr_Cro_2 -> tr_Cro)
        first_transition = target_transitions[0]
        if first_transition.transition_id:
            # Remove level suffix if present (e.g., _2, _3)
            base_id = first_transition.transition_id
            # Match pattern like tr_Cro_2 and extract tr_Cro
            match = re.match(r'^(.+)_(\d+)$', base_id)
            if match:
                base_id = match.group(1)
            qt.setId(base_id)
        else:
            qt.setId(f"tr_{target}")
            
        if not qt.isSetMetaId():
            qt.setMetaId(next_metaid())
        if first_transition.name:
            qt.setName(first_transition.name)
            
        # Outputs
        out = qt.createOutput()
        out.setQualitativeSpecies(target)
        out.setTransitionEffect(_qual_enum("QUAL_TRANSITION_EFFECT_ASSIGNMENT_LEVEL", 1))

        # Function terms - one for each level
        ft_default = qt.createDefaultTerm()
        ft_default.setResultLevel(0)
        
        # Collect all unique species IDs from all rules for this target
        all_species_ids = set()
        for t in target_transitions:
            ast = parse_expr(t.rule)
            all_species_ids.update(_collect_ids_from_ast(ast))
        
        # Create inputs for all referenced species
        for sid in sorted(all_species_ids):
            inp = qt.createInput()
            inp.setQualitativeSpecies(sid)
            if not inp.isSetMetaId():
                inp.setMetaId(next_metaid())
            inp.setTransitionEffect(_qual_enum("QUAL_TRANSITION_EFFECT_NONE", 0))

        # Collect all rules for this transition to add as notes
        rules_list = []
        for t in target_transitions:
            level = t.level if t.level is not None else 1
            rules_list.append(f"Level {level}: {t.rule}")
        
        # Create function terms for each level
        for t in target_transitions:
            ft = qt.createFunctionTerm()
            level = int(t.level) if t.level is not None else 1
            ft.setResultLevel(level)
            
            # Parse rule to MathML
            ast = parse_expr(t.rule)
            mathml_content = ast_to_mathml(ast)
            mathml = f"<math xmlns=\"http://www.w3.org/1998/Math/MathML\">{mathml_content}</math>"
            _set_mathml(ft, mathml)

        # Add rules as notes to the transition
        if rules_list:
            _append_notes(qt, rules_list)
        
        # Notes and annotations from the first transition
        if first_transition.notes:
            _append_notes_concat(qt, first_transition.notes)
        if transitions_anno and first_transition.annotations:
            _add_annotations(qt, first_transition.annotations, use_model=False)

    # Interactions (optional): add to corresponding transition inputs
    if interactions_anno and model.interactions:
        for inter in model.interactions:
            # Find transition whose output species equals interaction target
            for i in range(qual_model.getNumTransitions()):
                tr = qual_model.getTransition(i)
                out_species = None
                if tr.getNumOutputs() > 0:
                    out_species = tr.getOutput(0).getQualitativeSpecies()
                if out_species == inter.target:
                    # Find matching input by species
                    found_input = None
                    try:
                        for j in range(tr.getNumInputs()):
                            candidate = tr.getInput(j)
                            if candidate.getQualitativeSpecies() == inter.source:
                                found_input = candidate
                                break
                    except Exception:
                        found_input = None
                    if found_input is None:
                        print(f"No input found for {inter.source} in {tr.getId()}, creating one.")
                        found_input = tr.createInput()
                        found_input.setQualitativeSpecies(inter.source)
                        if not found_input.isSetMetaId():
                            found_input.setMetaId(next_metaid())
                        found_input.setTransitionEffect(_qual_enum("QUAL_TRANSITION_EFFECT_NONE", 0))
                    # sign
                    if inter.sign:
                        s = (inter.sign or "").strip().lower()
                        try:
                            if s == "positive":
                                found_input.setSign(_qual_enum("QUAL_SIGN_POSITIVE", 0))
                            elif s == "negative":
                                found_input.setSign(_qual_enum("QUAL_SIGN_NEGATIVE", 1))
                            elif s == "dual":
                                found_input.setSign(_qual_enum("QUAL_SIGN_DUAL", 2))
                            elif s == "unknown":
                                found_input.setSign(_qual_enum("QUAL_SIGN_UNKNOWN", 3))
                            else:
                                _append_notes(found_input, [f"Sign: {inter.sign}"])
                        except Exception:
                            print(f"Invalid sign: {inter.sign} for {inter.source} in {tr.getId()}, adding to notes.")
                            _append_notes(found_input, [f"Sign: {inter.sign}"])
                    # annotations and notes
                    if inter.annotations:
                        _add_annotations(found_input, inter.annotations, use_model=False)
                    if inter.notes:
                        _append_notes(found_input, inter.notes)
                    break

    return doc.toSBML()


def _set_mathml(ft: libsbml.QualFunctionTerm, mathml: str) -> None:
    astnode = libsbml.readMathMLFromString(mathml)
    if astnode is None:
        raise ValueError("Invalid MathML for function term")
    ft.setMath(astnode)


def _append_notes(node: libsbml.SBase, lines: List[str]) -> None:
    """Append notes to an SBML node
    
    For single notes or notes with embedded newlines, write directly.
    For multiple separate notes, wrap each with separator tags to preserve them through round-trips.
    """
    if not lines:
        return
    
    paragraphs = []
    
    if len(lines) == 1:
        # Single note - write directly without separators
        paragraphs.append(f"<p>{_xml_escape(lines[0])}</p>")
    else:
        # Multiple notes - wrap each with separator tags for round-trip preservation
        for idx, note in enumerate(lines, 1):
            wrapped = f"&lt;notes{idx}&gt;\n{_xml_escape(note)}\n&lt;/notes{idx}&gt;"
            paragraphs.append(f"<p>{wrapped}</p>")
    
    xhtml = "<body xmlns=\"http://www.w3.org/1999/xhtml\">" + "".join(paragraphs) + "</body>"
    node.setNotes(xhtml)


def _append_notes_concat(node: libsbml.SBase, lines: List[str]) -> None:
    """Append notes to existing notes instead of overwriting them"""
    existing_notes = ""
    if node.isSetNotes():
        existing_notes = node.getNotesString()
    
    new_notes = "\n".join([f"<p>{_xml_escape(l)}</p>" for l in lines])
    
    if existing_notes:
        # Extract the body content from existing notes
        if "<body" in existing_notes and "</body>" in existing_notes:
            start = existing_notes.find("<body")
            start = existing_notes.find(">", start) + 1
            end = existing_notes.find("</body>")
            if start > 0 and end > start:
                body_content = existing_notes[start:end]
                combined_content = body_content + new_notes
            else:
                combined_content = new_notes
        else:
            combined_content = existing_notes + new_notes
    else:
        combined_content = new_notes
    
    xhtml = f"<body xmlns=\"http://www.w3.org/1999/xhtml\">{combined_content}</body>"
    node.setNotes(xhtml)


def _xml_escape(s: str) -> str:
    # XML escaping to avoid parsing errors
    xml_escape_map = {
        "&": "&amp;",
        "<": "&lt;", 
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&apos;"
    }
    for k, v in xml_escape_map.items():
        s = s.replace(k, v)
    return s


def _add_model_annotations(m: libsbml.Model, im: InMemoryModel) -> None:
    # Publications / sources / derivedFrom etc. as CVTerms on model
    for url in im.model.source_urls:
        uri = _to_identifiers_url(url)
        _add_cvterm(m, True, getattr(libsbml, "BQM_IS", 0), uri)
    for url in im.model.described_by:
        uri = _to_identifiers_url(url)
        _add_cvterm(m, True, getattr(libsbml, "BQM_IS_DESCRIBED_BY", 0), uri)
    for url in im.model.derived_from:
        uri = _to_identifiers_url(url)
        _add_cvterm(m, True, getattr(libsbml, "BQM_IS_DERIVED_FROM", 0), uri)
    for proc in im.model.biological_processes:
        uri = _to_identifiers_url(proc)
        _add_cvterm(m, False, getattr(libsbml, "BQB_IS_VERSION_OF", 0), uri)
    for tax in im.model.taxons:
        uri = _to_identifiers_url(tax)
        _add_cvterm(m, False, getattr(libsbml, "BQB_HAS_TAXON", 0), uri)
    # TODO: hasProperty for MAMO terms based on species max_level
    # Model history: creators, contributors, created/modified using dc terms
    _add_model_history(m, im)


def _add_model_history(m: libsbml.Model, im: InMemoryModel) -> None:
    try:
        history = libsbml.ModelHistory()
    except Exception:
        return
    # Creators
    for p in im.model.creators:
        c = libsbml.ModelCreator()
        if p.family_name:
            c.setFamilyName(p.family_name)
        if p.given_name:
            c.setGivenName(p.given_name)
        if p.email:
            c.setEmail(p.email)
        if p.organization:
            c.setOrganization(p.organization)
        history.addCreator(c)
    # Contributors (not available in libsbml 5.20.4; fall back to addCreator)
    for p in im.model.contributors:
        c = libsbml.ModelCreator()
        if p.family_name:
            c.setFamilyName(p.family_name)
        if p.given_name:
            c.setGivenName(p.given_name)
        if p.email:
            c.setEmail(p.email)
        if p.organization:
            c.setOrganization(p.organization)
        if hasattr(history, "addContributor"):
            history.addContributor(c)
        else:
            history.addCreator(c)
    # Dates
    created = _to_iso8601(im.model.created_iso)
    if created:
        d = libsbml.Date()
        if hasattr(d, "setDateAsString"):
            d.setDateAsString(created)
            history.setCreatedDate(d)
    modified = _to_iso8601(im.model.modified_iso)
    if modified:
        d = libsbml.Date()
        if hasattr(d, "setDateAsString"):
            d.setDateAsString(modified)
            history.setModifiedDate(d)
    m.setModelHistory(history)


def _add_annotations(node: libsbml.SBase, pairs: List[Tuple[str, str]], use_model: bool) -> None:
    # For each (relation, identifiers_str) create one CVTerm with multiple resources if comma-separated
    for rel, ident in pairs:
        predicate = _relation_to_predicate(rel, use_model)
        cv = libsbml.CVTerm(libsbml.MODEL_QUALIFIER if use_model else libsbml.BIOLOGICAL_QUALIFIER)
        cv.setQualifierType(libsbml.MODEL_QUALIFIER if use_model else libsbml.BIOLOGICAL_QUALIFIER)
        if use_model:
            cv.setModelQualifierType(predicate)
        else:
            cv.setBiologicalQualifierType(predicate)
        # split identifiers by comma into multiple resources within the same bag
        for token in [t.strip() for t in str(ident).split(',') if str(t).strip()]:
            uri = _to_identifiers_url(token)
            cv.addResource(uri)
        node.addCVTerm(cv)


def _relation_to_predicate(rel: str, use_model: bool) -> int:
    r = (rel or "").strip()
    if use_model:
        bqm = {
            "is": getattr(libsbml, "BQM_IS", 0),
            "isDerivedFrom": getattr(libsbml, "BQM_IS_DERIVED_FROM", 0),
            "isDescribedBy": getattr(libsbml, "BQM_IS_DESCRIBED_BY", 0),
            "isInstanceOf": getattr(libsbml, "BQM_IS_INSTANCE_OF", 0),
            "hasInstance": getattr(libsbml, "BQM_HAS_INSTANCE", 0),
        }
        return bqm.get(r, getattr(libsbml, "BQM_IS", 0))
    bqb = {
        "is": getattr(libsbml, "BQB_IS", 0),
        "hasVersion": getattr(libsbml, "BQB_HAS_VERSION", 0),
        "isVersionOf": getattr(libsbml, "BQB_IS_VERSION_OF", 0),
        "isDescribedBy": getattr(libsbml, "BQB_IS_DESCRIBED_BY", 0),
        "hasPart": getattr(libsbml, "BQB_HAS_PART", 0),
        "isPartOf": getattr(libsbml, "BQB_IS_PART_OF", 0),
        "hasProperty": getattr(libsbml, "BQB_HAS_PROPERTY", 0),
        "isPropertyOf": getattr(libsbml, "BQB_IS_PROPERTY_OF", 0),
        "encodes": getattr(libsbml, "BQB_ENCODES", 0),
        "isEncodedBy": getattr(libsbml, "BQB_IS_ENCODED_BY", 0),
        "isHomologTo": getattr(libsbml, "BQB_IS_HOMOLOG_TO", 0),
        "occursIn": getattr(libsbml, "BQB_OCCURS_IN", 0),
        "hasTaxon": getattr(libsbml, "BQB_HAS_TAXON", 0),
    }
    return bqb.get(r, getattr(libsbml, "BQB_IS", 0))


def _add_cvterm(node: libsbml.SBase, is_model: bool, predicate: int, uri: str) -> None:
    if is_model:
        cv = libsbml.CVTerm(libsbml.MODEL_QUALIFIER)
        cv.setQualifierType(libsbml.MODEL_QUALIFIER)
        cv.setModelQualifierType(predicate)
    else:
        cv = libsbml.CVTerm(libsbml.BIOLOGICAL_QUALIFIER)
        cv.setQualifierType(libsbml.BIOLOGICAL_QUALIFIER)
        cv.setBiologicalQualifierType(predicate)
    cv.addResource(uri)
    node.addCVTerm(cv)


def _to_identifiers_url(identifier: str) -> str:
    s = identifier.strip()
    if not s:
        return s
    
    # Check if it's already a URL/URI
    if s.startswith(("http://", "https://", "ftp://", "urn:", "doi:")):
        return s
    
    # Check if it's a compact identifier (prefix:accession pattern)
    if ":" in s and not s.startswith(":"):
        first_colon_pos = s.find(":")
        if first_colon_pos > 0:
            prefix = s[:first_colon_pos]
            accession = s[first_colon_pos + 1:]

            if prefix and accession:
                return f"https://identifiers.org/{s}"
    
    return f"https://identifiers.org/{s}"


def _collect_ids_from_ast(ast) -> List[str]:
    kind = ast[0]
    if kind == 'id':
        return [ast[1]]
    if kind in ('eq', 'le', 'ge', 'gt', 'lt', 'neq'):
        return [ast[1]]  # Return the species name from threshold nodes
    if kind == 'not_species':
        return [ast[1]]  # Return the species name from negated species nodes
    if kind == 'not':
        return _collect_ids_from_ast(ast[1])
    if kind in ('and', 'or'):
        return list(dict.fromkeys(_collect_ids_from_ast(ast[1]) + _collect_ids_from_ast(ast[2])))
    return []


def _qual_enum(name: str, default_value: int) -> int:
    # Gracefully resolve enums across libsbml versions
    value = getattr(libsbml, name, None)
    if isinstance(value, int):
        return value
    return default_value


def _to_iso8601(value: str | None) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Try python-dateutil if available for robust parsing
    dt = None
    try:
        from dateutil import parser as dateutil_parser  # type: ignore
        dt = dateutil_parser.parse(s)
    except Exception:
        dt = None
    if dt is None:
        # Handle common cases
        # Replace trailing Z to be compatible with fromisoformat
        try:
            s2 = s
            if s.endswith("Z") and "+" not in s and "-" in s[10:]:
                # keep Z; fromisoformat does not like Z
                s2 = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s2)
        except Exception:
            dt = None
    if dt is None:
        # Try a set of common fallback formats (dates with/without time)
        fmts = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y/%m/%d",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y %H:%M:%S",
        ]
        for fmt in fmts:
            try:
                dt = datetime.strptime(s, fmt)
                break
            except Exception:
                continue
    if dt is None:
        return None
    # Normalize to UTC and return ISO string without microseconds, with Z
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        iso = dt.replace(microsecond=0).isoformat()
        if iso.endswith("+00:00"):
            iso = iso[:-6] + "Z"
        return iso
    except Exception:
        return None