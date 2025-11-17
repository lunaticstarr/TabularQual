from __future__ import annotations

from typing import List, Tuple


class Token:
    def __init__(self, kind: str, value: str):
        self.kind = kind
        self.value = value


def tokenize(expr: str) -> List[Token]:
    s = expr.replace(" ", "")
    tokens: List[Token] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch.isalnum() or ch == '_' or ch == ':':  # allow compact IDs like A:2 (threshold)
            j = i + 1
            while j < len(s) and (s[j].isalnum() or s[j] in ['_', ':']):
                j += 1
            tokens.append(Token('ID', s[i:j]))
            i = j
            continue
        if ch == '&':
            tokens.append(Token('AND', ch))
            i += 1
            continue
        if ch == '|':
            tokens.append(Token('OR', ch))
            i += 1
            continue
        if ch == '!':
            # Check for != first
            if i + 1 < len(s) and s[i + 1] == '=':
                tokens.append(Token('NEQ', '!='))
                i += 2
            else:
                tokens.append(Token('NOT', ch))
                i += 1
            continue
        if ch == '(':
            tokens.append(Token('LP', ch))
            i += 1
            continue
        if ch == ')':
            tokens.append(Token('RP', ch))
            i += 1
            continue
        if ch == '>':
            # Check for >=
            if i + 1 < len(s) and s[i + 1] == '=':
                tokens.append(Token('GEQ', '>='))
                i += 2
            else:
                tokens.append(Token('GT', '>'))
                i += 1
            continue
        if ch == '<':
            # Check for <=
            if i + 1 < len(s) and s[i + 1] == '=':
                tokens.append(Token('LEQ', '<='))
                i += 2
            else:
                tokens.append(Token('LT', '<'))
                i += 1
            continue
        if ch == '=':
            tokens.append(Token('EQ', '='))
            i += 1
            continue
        raise ValueError(f"Unexpected character in rule: {ch}")
    return tokens


# A minimal AST represented as nested tuples for simplicity
# ('or', left, right) | ('and', left, right) | ('not', node) | ('id', name) 
# | ('eq', name, threshold) | ('le', name, threshold) | ('ge', name, threshold) | ('gt', name, threshold) | ('lt', name, threshold) | ('neq', name, threshold)


def parse(expr: str):
    tokens = tokenize(expr)
    pos = 0
    paren_stack = []  # Track parentheses for better error messages

    def peek() -> Token | None:
        nonlocal pos
        return tokens[pos] if pos < len(tokens) else None

    def consume(kind: str | None = None) -> Token:
        nonlocal pos
        t = peek()
        if t is None:
            if kind == 'RP' and paren_stack:
                # Specific error for missing closing parenthesis
                open_count = sum(1 for tk in tokens if tk.kind == 'LP')
                close_count = sum(1 for tk in tokens if tk.kind == 'RP')
                raise ValueError(
                    f"Unexpected end of expression. Missing closing parenthesis ')'. "
                    f"Found {open_count} opening '(' but only {close_count} closing ')' in: {expr}"
                )
            raise ValueError(f"Unexpected end of expression. Expected more tokens after: {expr}")
        if kind and t.kind != kind:
            if kind == 'RP':
                open_count = sum(1 for tk in tokens if tk.kind == 'LP')
                close_count = sum(1 for tk in tokens if tk.kind == 'RP')
                raise ValueError(
                    f"Expected closing parenthesis ')', got {t.kind}. "
                    f"Check parentheses balance: {open_count} opening '(' vs {close_count} closing ')'"
                )
            raise ValueError(f"Expected {kind}, got {t.kind}")
        pos += 1
        return t

    def parse_factor():
        """Parse comparison expressions like A>=1, B<3, C=2"""
        t = peek()
        if t is None:
            raise ValueError("Unexpected end")
        
        if t.kind == 'ID':
            species_name = consume('ID').value
            # Look for comparison operator
            op_t = peek()
            if op_t and op_t.kind in ('GEQ', 'LEQ', 'GT', 'LT', 'EQ', 'NEQ'):
                op = consume().kind
                # Look for number
                num_t = peek()
                if num_t and num_t.kind == 'ID':
                    # Check if it's a number
                    try:
                        threshold = int(num_t.value)
                        consume('ID')  # consume the number
                        # Map operator to AST node type
                        op_map = {
                            'GEQ': 'ge',
                            'LEQ': 'le', 
                            'GT': 'gt',
                            'LT': 'lt',
                            'EQ': 'eq',
                            'NEQ': 'neq'
                        }
                        return (op_map[op], species_name, threshold)
                    except ValueError:
                        # Not a number, treat as regular ID
                        return ('id', species_name)
                else:
                    # No number after operator, treat as regular ID
                    return ('id', species_name)
            else:
                # No comparison operator, check for colon notation
                if ':' in species_name:
                    parts = species_name.split(':', 1)
                    species_name = parts[0]
                    threshold = int(parts[1]) if parts[1] else 1
                    return ('ge', species_name, threshold)  # A:2 means A >= 2
                return ('id', species_name)
        
        # Handle other cases
        if t.kind == 'NOT':
            consume('NOT')
            # Check if the next token is an ID (species name)
            next_t = peek()
            if next_t and next_t.kind == 'ID':
                # This could be !CI or !CI:2
                species_name = consume('ID').value
                # Check for colon notation in negated species
                if ':' in species_name:
                    parts = species_name.split(':', 1)
                    species_name = parts[0]
                    threshold = int(parts[1]) if parts[1] else 1
                    return ('lt', species_name, threshold)  # !CI:2 means CI < 2
                else:
                    return ('not_species', species_name)  # !CI means CI = 0
            else:
                # Regular negation of a complex expression
                node = parse_factor()
                return ('not', node)
        if t.kind == 'LP':
            paren_stack.append(pos)  # Track opening parenthesis position
            consume('LP')
            node = parse_expr()
            consume('RP')
            paren_stack.pop() if paren_stack else None  # Remove tracked position
            return node
        raise ValueError(f"Unexpected token {t.kind}")

    def parse_term():
        node = parse_factor()
        while True:
            t = peek()
            if t and t.kind == 'AND':
                consume('AND')
                rhs = parse_factor()
                node = ('and', node, rhs)
            else:
                break
        return node

    def parse_expr():
        node = parse_term()
        while True:
            t = peek()
            if t and t.kind == 'OR':
                consume('OR')
                rhs = parse_term()
                node = ('or', node, rhs)
            else:
                break
        return node

    ast = parse_expr()
    if peek() is not None:
        raise ValueError("Unexpected trailing tokens")
    return ast


def ast_to_mathml(ast) -> str:
    if ast[0] == 'id':
        name = ast[1]
        # Check if it's a numeric constant (e.g., "1", "0", "2")
        if name.isdigit():
            # For numeric constants, interpret as boolean: 0 = false, non-zero = true
            if name == '0':
                return "<false/>"
            else:
                return "<true/>"
        # For simple identifiers (species names), create a boolean expression (species >= 1)
        return f"<apply><geq/><ci>{name}</ci><cn type=\"integer\">1</cn></apply>"
    if ast[0] == 'eq':
        name = ast[1]
        threshold = ast[2]
        return f"<apply><eq/><ci>{name}</ci><cn type=\"integer\">{threshold}</cn></apply>"
    if ast[0] == 'le':
        name = ast[1]
        threshold = ast[2]
        return f"<apply><leq/><ci>{name}</ci><cn type=\"integer\">{threshold}</cn></apply>"
    if ast[0] == 'ge':
        name = ast[1]
        threshold = ast[2]
        return f"<apply><geq/><ci>{name}</ci><cn type=\"integer\">{threshold}</cn></apply>"
    if ast[0] == 'gt':
        name = ast[1]
        threshold = ast[2]
        return f"<apply><gt/><ci>{name}</ci><cn type=\"integer\">{threshold}</cn></apply>"
    if ast[0] == 'lt':
        name = ast[1]
        threshold = ast[2]
        return f"<apply><lt/><ci>{name}</ci><cn type=\"integer\">{threshold}</cn></apply>"
    if ast[0] == 'neq':
        name = ast[1]
        threshold = ast[2]
        return f"<apply><neq/><ci>{name}</ci><cn type=\"integer\">{threshold}</cn></apply>"
    if ast[0] == 'not_species':
        name = ast[1]
        # For multi-valued species, !CI means CI = 0
        return f"<apply><eq/><ci>{name}</ci><cn type=\"integer\">0</cn></apply>"
    if ast[0] == 'not':
        return f"<apply><not/>{ast_to_mathml(ast[1])}</apply>"
    if ast[0] == 'and':
        return f"<apply><and/>{ast_to_mathml(ast[1])}{ast_to_mathml(ast[2])}</apply>"
    if ast[0] == 'or':
        return f"<apply><or/>{ast_to_mathml(ast[1])}{ast_to_mathml(ast[2])}</apply>"
    raise ValueError(f"Unknown AST node {ast[0]}")


def ast_to_mathml_with_comment(ast, rule: str) -> str:
    """Convert AST to MathML with the original rule as a comment"""
    mathml_content = ast_to_mathml(ast)
    # Add the original rule as a comment
    comment = f"<!-- {rule} -->"
    return f"{comment}\n{mathml_content}"