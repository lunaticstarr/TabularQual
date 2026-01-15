RDF_TAG_ITEM = ['rdf:RDF',
                'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"',
                'xmlns:bqbiol="http://biomodels.net/biology-qualifiers/"']

RDF_TAG = ' '.join(RDF_TAG_ITEM)

import libsbml

def getIndent(num_indents=0):
  """
  Parameters
  ----------
  num_indents: int
    Time of indentation
  
  Returns
  -------
  :str
  """
  return '  ' * (num_indents)
  
def insertList(insert_to,
                insert_from,
                start_loc=None):
  """
  Insert a list to another list.

  Parameters
  ----------
  insert_to:list
      List where new list is inserted to

  inser_from: list
      A list where items will be inserted from

  start_loc: int
      If not given, insert_from will be 
      added in the middle of insert_to
  """
  if start_loc is None:
    start_loc = int(len(insert_to)/2)
  indents = getIndent(start_loc)
  insert_from_indented = [indents+val for val in insert_from]
  return insert_to[:start_loc] + \
          insert_from_indented + \
          insert_to[start_loc:]

def createAnnotationItem(knowledge_source,
                          identifier):
  """
  Create a one-line annotation,
  e.g., <rdf:li rdf:resource="http://identifiers.org/chebi/CHEBI:15414"/>

  Parameters
  ----------
  knowledge_source: str

  identifier: str

  Returns
  -------
  str
  """
  annotation_items = ['identifiers.org',
                      knowledge_source,
                      identifier]
  res = '<rdf:li rdf:resource="http://' + \
        '/'.join(annotation_items)  +\
        '"/>'
  return res

def createTag(tag_str):
  """
  Create a tag based on the given string
  
  Parameters
  ---------
  str: inp_str

  Returns
  -------
  list-str
  """
  head_str = tag_str
  tail_str = tag_str.split(' ')[0]
  res_tag = ['<'+head_str+'>', '</'+tail_str+'>']
  return res_tag

def createAnnotationContainer(items):
  """
  Create an empty annotation container
  that will hold the annotation blocks

  Parameters
  ----------
  items: str-list

  Returns
  -------
  list-str
  """
  container =[]
  for one_item in items:
    one_t = createTag(one_item)
    container = insertList(insert_from=one_t,
                                insert_to=container)
  return container

def createAnnotationString(qualifier,
                        knowledge_source,
                        candidates,
                        meta_id):
  """
  Create a string of annotations,
  using a list of strings.
  (of candidates)
  Can replace an entire annotation. 

  Parameters
  ----------
  qualifier: str
      Qualifier to be used for annotations.
      E.g., 'bqbiol:isDescribedBy'

  knowledge_source: str
      Knowledge source of the annotation.
      E.g., 'uniprot'

  candidates: list-str
      e.g., ['CHEBI:12345', 'CHEBI:98765']

  meta_id: str
      Meta ID of the element to be included in the annotation. 

  Returns
  -------
  str
  """
      
  # First, construct an empty container
  container_items = ['annotation', 
                      RDF_TAG,
                      'rdf:Description rdf:about="#' + str(meta_id) + '"',
                      qualifier,
                      'rdf:Bag']
  empty_container = createAnnotationContainer(container_items)
  # Next, create annotation lines
  items_from = []
  for one_cand in candidates:
    if one_cand != '':
      items_from.append(createAnnotationItem(knowledge_source,one_cand))

  result = insertList(insert_to=empty_container,
                              insert_from=items_from)
  return ('\n').join(result)

def createAnnotationStringFromDict(all_annotations, meta_id):
    """
    Create a complete RDF annotation string from a dictionary of annotations.
    
    Parameters:
    -----------
    all_annotations: dict
        A nested dictionary with the structure:
        {
            'relation1': {
                'resource1': ['id1', 'id2'],
                'resource2': ['id3', 'id4']
            },
            'relation2': {
                'resource3': ['id5', 'id6']
            }
        }
    meta_id: str
        MetaID of the species
        
    Returns:
    --------
    str
        Complete annotation string
    """
    # Start RDF annotation
    annotation_string = (
        '<annotation>\n'
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:bqbiol="http://biomodels.net/biology-qualifiers/">\n'
        f'    <rdf:Description rdf:about="#{meta_id}">\n'
    )
    
    # Add each relation and its resources/identifiers
    for relation, resources in all_annotations.items():
        for resource, identifiers in resources.items():
            # Skip if no valid identifiers
            if not identifiers:
                continue
                
            # Remove duplicates while preserving order
            unique_identifiers = []
            for id in identifiers:
                if id and id not in unique_identifiers:
                    unique_identifiers.append(id)
            
            # Skip if no valid identifiers after removing duplicates
            if not unique_identifiers:
                continue
            
            # Add this relation with all its identifiers
            annotation_string += f'      <bqbiol:{relation}>\n'
            annotation_string += '        <rdf:Bag>\n'
            
            for identifier in unique_identifiers:
                annotation_string += f'          <rdf:li rdf:resource="http://identifiers.org/{resource}/{identifier}"/>\n'
            
            annotation_string += '        </rdf:Bag>\n'
            annotation_string += f'      </bqbiol:{relation}>\n'
    
    # Close the tags
    annotation_string += '    </rdf:Description>\n'
    annotation_string += '  </rdf:RDF>\n'
    annotation_string += '</annotation>'
    
    return annotation_string

def validate_identifier(identifier: str) -> dict:
    """
    Validate and classify a spreadsheet identifier.
    
    Args:
        identifier: The identifier string from the spreadsheet
        
    Returns:
        Dictionary with classification and processed URI
    """
    if not identifier or not isinstance(identifier, str):
        return {
            'is_valid': False,
            'type': 'invalid',
            'uri': identifier,
            'error': 'Empty or non-string identifier'
        }
    
    s = identifier.strip()
    if not s:
        return {
            'is_valid': False,
            'type': 'invalid',
            'uri': identifier,
            'error': 'Empty identifier after stripping'
        }
    
    # Check if it's already a URL/URI
    if s.startswith(("http://", "https://", "ftp://")):
        return {
            'is_valid': True,
            'type': 'url',
            'uri': s,
            'original': identifier
        }
    
    # Check if it's a URN
    if s.startswith("urn:"):
        return {
            'is_valid': True,
            'type': 'urn',
            'uri': s,
            'original': identifier
        }
    
    # Check if it's a DOI
    if s.startswith("doi:"):
        return {
            'is_valid': True,
            'type': 'doi',
            'uri': s,
            'original': identifier
        }
    
    # Check if it's a compact identifier (prefix:accession pattern)
    if ":" in s and not s.startswith(":"):
        # For compact identifiers, we expect at least one colon
        # The first colon separates prefix from accession, but prefix may contain colons
        
        # Split on first colon only
        first_colon_pos = s.find(":")
        if first_colon_pos > 0:  # prefix exists and is not empty
            prefix = s[:first_colon_pos]
            accession = s[first_colon_pos + 1:]
            
            # Basic validation: prefix should not be empty, accession should not be empty
            if prefix and accession:
                return {
                    'is_valid': True,
                    'type': 'compact_identifier',
                    'uri': f"https://identifiers.org/{s}",
                    'original': identifier,
                    'prefix': prefix,
                    'accession': accession
                }
            else:
                return {
                    'is_valid': False,
                    'type': 'malformed_compact',
                    'uri': identifier,
                    'error': 'Empty prefix or accession in compact identifier'
                }
        else:
            return {
                'is_valid': False,
                'type': 'malformed_compact',
                'uri': identifier,
                'error': 'Invalid compact identifier format'
            }
    
    # For identifiers without colons, assume they might be compact identifiers
    # but this is less certain
    return {
        'is_valid': True,
        'type': 'assumed_compact',
        'uri': f"https://identifiers.org/{s}",
        'original': identifier,
        'warning': 'No colon found, assuming compact identifier'
    }