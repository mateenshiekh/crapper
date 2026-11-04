"""Dart functions, methods, and cyclomatic complexity.

Decision points follow the same structural rule as the other languages: `if`
and a collection `if`, loops (`for`, `for-in`, `await for`, a collection
`for`, `while`, `do`), each `on` / `catch` handler, `?:`, each `switch`
case and `default`, each switch-expression arm, `&&` / `||`, and the
null-aware operators `??`, `??=`, `?.`, `?[]`, and `?..`.

Top-level functions, getters, and setters are entries, as are the methods,
getters, setters, operators, and bodied constructors of a class, mixin, enum,
extension, or extension type. A local function or closure stays inside the
enclosing entry. A declaration with no body — abstract, external, or a
constructor that has only an initializer list — is not an entry, so a
Flutter widget's `const` constructor adds no row and a `fromJson` factory does.

The namespace is the library path under the nearest `pubspec.yaml`, with
`lib/` dropped and `/` replaced by `.`: `app.src.cart`, or `app.src.cart.Cart`
for a member. That is the dotted library name Dart itself used to require.
"""

import re
from pathlib import Path

from crapper.languages.treesitter import (
    absolute_path as _absolute,
    child_of_type,
    complexity,
    descendants,
    end_line,
    node_text,
    parse,
    start_line,
)
from crapper.model import Function

_DECISIONS = {
    "if_statement",
    "if_element",
    "for_statement",
    "for_element",
    "while_statement",
    "do_statement",
    "catch_clause",
    "conditional_expression",
    "switch_statement_case",
    "switch_statement_default",
    "switch_expression_case",
    "logical_and_operator",
    "logical_or_operator",
    "conditional_assignable_selector",
}
_NULL_AWARE_TOKENS = {"??", "??=", "?.."}
_BODIES = {"program", "class_body", "enum_body", "extension_body"}
_CONTAINERS = {
    "class_definition",
    "mixin_declaration",
    "enum_declaration",
    "extension_declaration",
    "extension_type_declaration",
}
_SIGNATURES = {
    "function_signature",
    "getter_signature",
    "setter_signature",
    "method_signature",
}
_CONSTRUCTORS = {
    "constructor_signature",
    "constant_constructor_signature",
    "factory_constructor_signature",
}
_PUBSPEC_NAME = re.compile(r"(?m)^name:\s*['\"]?([A-Za-z_][\w.-]*)")
_OPERATOR = re.compile(r"\boperator\b")


def _is_bare_on_clause(node) -> bool:
    """`on E { }` without `catch` has no node of its own.

    The handler's type is a direct child of the `try`, followed by its block.
    With `catch`, the `catch_clause` that follows is the decision instead.
    """

    parent = node.parent
    if node.type != "type_identifier" or parent is None or parent.type != "try_statement":
        return False
    following = node.next_named_sibling
    return following is None or following.type != "catch_clause"


def _is_decision(node) -> bool:
    if node.type in _DECISIONS or node.type in _NULL_AWARE_TOKENS:
        return True
    return _is_bare_on_clause(node)


def _skip(_node) -> bool:
    return False


def _pubspec_name(pubspec: Path) -> str | None:
    match = _PUBSPEC_NAME.search(pubspec.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else None


def _package_of(file: Path) -> tuple[str, Path] | None:
    """Package name and directory from the nearest pubspec.yaml, like Go's go.mod."""

    current = file.parent
    while True:
        pubspec = current / "pubspec.yaml"
        if pubspec.is_file():
            name = _pubspec_name(pubspec)
            if name is None:
                return None
            return name, current
        if current.parent == current:
            return None
        current = current.parent


def _strip_root_prefix(relative: str, source_root: str | None) -> str:
    root = (source_root or "").replace("\\", "/").rstrip("/")
    if root and root != "." and relative.startswith(root + "/"):
        return relative[len(root) + 1 :]
    if relative.startswith("./"):
        return relative[2:]
    return relative


def _strip_lib_dir(relative: str) -> str:
    if relative.startswith("lib/"):
        return relative[4:]
    if "/lib/" in relative:
        return relative.split("/lib/", 1)[1]
    return relative


def _dotted(relative: str) -> str:
    if relative.endswith(".dart"):
        relative = relative[: -len(".dart")]
    return relative.replace("/", ".")


def library_namespace(path: str, source_root: str | None) -> str:
    """`package.path.under.lib`, or the path itself when there is no pubspec.yaml."""

    file = Path(_absolute(path, source_root))
    found = _package_of(file)
    if found is not None:
        name, package_dir = found
        relative = file.relative_to(package_dir).as_posix()
        inner = _dotted(_strip_lib_dir(relative))
        return f"{name}.{inner}" if inner else name
    relative = _strip_root_prefix(path.replace("\\", "/"), source_root)
    return _dotted(_strip_lib_dir(relative))


def _inner_signature(signature):
    if signature.type != "method_signature":
        return signature
    for child in signature.children:
        if child.type.endswith("_signature"):
            return child
    return None


def _identifier_text(data: bytes, node) -> str | None:
    ident = child_of_type(node, "identifier")
    if ident is None:
        return None
    return node_text(data, ident)


def _constructor_name(data: bytes, node) -> str | None:
    """`Widget` for the unnamed constructor, `Widget.fromJson` for a named one."""

    parts = [node_text(data, child) for child in node.children if child.type == "identifier"]
    return ".".join(parts) if parts else None


def _operator_name(data: bytes, node) -> str | None:
    """`operator ==`, `operator []=`: the text between the keyword and the parameters."""

    params = child_of_type(node, "formal_parameter_list")
    stop = params.start_byte if params is not None else node.end_byte
    head = data[node.start_byte : stop].decode("utf-8")
    matches = list(_OPERATOR.finditer(head))
    if not matches:
        return None
    symbol = head[matches[-1].end() :].strip()
    return f"operator {symbol}" if symbol else None


def _name(data: bytes, signature) -> str | None:
    inner = _inner_signature(signature)
    if inner is None:
        return None
    if inner.type in {"function_signature", "getter_signature"}:
        return _identifier_text(data, inner)
    if inner.type == "setter_signature":
        ident = _identifier_text(data, inner)
        return f"{ident}=" if ident else None
    if inner.type in _CONSTRUCTORS:
        return _constructor_name(data, inner)
    if inner.type == "operator_signature":
        return _operator_name(data, inner)
    return None


def _namespace(data: bytes, module: str, signature) -> str:
    current = signature.parent
    while current is not None:
        if current.type in _CONTAINERS:
            owner = _identifier_text(data, current)
            return f"{module}.{owner}" if owner else module
        current = current.parent
    return module


def _signature_before(body):
    """The signature that owns a body, stepping back over a comment between them."""

    previous = body.prev_named_sibling
    while previous is not None and previous.type == "comment":
        previous = previous.prev_named_sibling
    if previous is None or previous.type not in _SIGNATURES:
        return None
    return previous


def _complexity(signature, body) -> int:
    """One plus every decision in the body and in the signature.

    A constructor's initializer list is part of its signature, and a default
    parameter value can hold a conditional, so both halves are walked.
    """

    return complexity(body, _is_decision, _skip) + complexity(signature, _is_decision, _skip) - 1


def functions_in_source(
    source: str, path: str, source_root: str | None = None
) -> list[Function]:
    data, tree = parse(source, "dart")
    module = library_namespace(path, source_root)
    found: list[Function] = []
    for body in descendants(tree.root_node):
        if body.type != "function_body" or body.parent is None:
            continue
        if body.parent.type not in _BODIES:
            continue
        signature = _signature_before(body)
        if signature is None:
            continue
        name = _name(data, signature)
        if name is None:
            continue
        found.append(
            Function(
                name=name,
                namespace=_namespace(data, module, signature),
                complexity=_complexity(signature, body),
                start_line=start_line(signature),
                end_line=end_line(body),
                path=path,
                language="dart",
                start_byte=signature.start_byte,
                end_byte=body.end_byte,
            )
        )
    return found
