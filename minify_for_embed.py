#!/usr/bin/env python3
"""Safe minifier for prism32.py — strips comments, docstrings, and excess whitespace.
Preserves all functionality. Outputs to stdout."""
import ast, sys, io, tokenize

SOURCE = "/home/labcomputer5/Documents/Programs/Palmcoder95/prism32.py"

def get_docstring_lines(source):
    """Return a set of line numbers that belong to docstrings."""
    doc_lines = set()
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"Syntax error during docstring scan: {e}", file=sys.stderr)
        return doc_lines

    def add_docstring(node):
        # Module, FunctionDef, AsyncFunctionDef, ClassDef
        body = getattr(node, 'body', [])
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            start = body[0].lineno
            end = body[0].end_lineno
            for ln in range(start, end + 1):
                doc_lines.add(ln)

    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add_docstring(node)
    return doc_lines

def minify(source):
    doc_lines = get_docstring_lines(source)
    lines = source.splitlines(keepends=True)
    result_lines = []
    prev_blank = False

    for i, line in enumerate(lines, start=1):
        # Skip docstring lines
        if i in doc_lines:
            continue

        stripped = line.lstrip()
        # Skip pure comment lines (but keep shebang/encoding)
        if stripped.startswith('#'):
            if stripped.startswith('#!') or 'coding' in stripped[:20]:
                result_lines.append(line)
            continue

        # Remove inline comments, but carefully preserve strings
        # Use tokenization for the line to safely strip trailing comments
        new_line = strip_inline_comment(line)

        # Collapse multiple blank lines
        if not new_line.strip():
            if not prev_blank:
                result_lines.append('\n')
                prev_blank = True
            continue

        result_lines.append(new_line)
        prev_blank = False

    return ''.join(result_lines)

def strip_inline_comment(line):
    """Strip trailing comments from a line using tokenization."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(line).readline))
    except tokenize.TokenError:
        return line
    # Find the first COMMENT token
    comment_start = None
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            comment_start = tok.start[1]
            break
    if comment_start is not None:
        return line[:comment_start].rstrip() + '\n'
    return line

if __name__ == "__main__":
    with open(SOURCE, "r", encoding="utf-8") as f:
        src = f.read()
    out = minify(src)
    sys.stdout.write(out)
