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
        if ch.isalnum() or ch == '_' or ch == ':':  # allow compact IDs like A:2 (threshold TODO)
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
        raise ValueError(f"Unexpected character in rule: {ch}")
    return tokens


# A minimal AST represented as nested tuples for simplicity
# ('or', left, right) | ('and', left, right) | ('not', node) | ('id', name)


def parse(expr: str):
    tokens = tokenize(expr)
    pos = 0

    def peek() -> Token | None:
        nonlocal pos
        return tokens[pos] if pos < len(tokens) else None

    def consume(kind: str | None = None) -> Token:
        nonlocal pos
        t = peek()
        if t is None:
            raise ValueError("Unexpected end of expression")
        if kind and t.kind != kind:
            raise ValueError(f"Expected {kind}, got {t.kind}")
        pos += 1
        return t

    def parse_factor():
        t = peek()
        if t is None:
            raise ValueError("Unexpected end")
        if t.kind == 'NOT':
            consume('NOT')
            node = parse_factor()
            return ('not', node)
        if t.kind == 'LP':
            consume('LP')
            node = parse_expr()
            consume('RP')
            return node
        if t.kind == 'ID':
            name = consume('ID').value
            # TODO: support thresholds like A:2 -> ('ge', 'A', 2)
            if ':' in name:
                # TODO multi-valued threshold semantics per spec
                name = name.split(':', 1)[0]
            return ('id', name)
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
        # For simple identifiers, we need to create a boolean expression
        return f"<apply><eq/><ci>{name}</ci><cn type=\"integer\">1</cn></apply>"
    if ast[0] == 'not':
        return f"<apply><not/>{ast_to_mathml(ast[1])}</apply>"
    if ast[0] == 'and':
        return f"<apply><and/>{ast_to_mathml(ast[1])}{ast_to_mathml(ast[2])}</apply>"
    if ast[0] == 'or':
        return f"<apply><or/>{ast_to_mathml(ast[1])}{ast_to_mathml(ast[2])}</apply>"
    raise ValueError(f"Unknown AST node {ast[0]}")