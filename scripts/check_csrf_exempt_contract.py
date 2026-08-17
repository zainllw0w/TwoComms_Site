"""Validate the non-DTF ``csrf_exempt`` security contract.

The check is intentionally static and no-network: it parses active source files
with the standard-library AST and compares the discovered exemption sites with
the machine-readable IDs in ``docs/security/csrf-exempt-contracts.md``.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "docs" / "security" / "csrf-exempt-contracts.md"
LEGACY_BACKUP_PATH = REPO_ROOT / "twocomms" / "storefront" / "views.py.backup"
LEGACY_INIT_PATH = REPO_ROOT / "twocomms" / "storefront" / "views" / "__init__.py"
LEGACY_URLS_PATH = REPO_ROOT / "twocomms" / "storefront" / "urls.py"
_CONTRACT_ID_RE = re.compile(r"^\|\s*`(?P<id>(?:function|wrapper):[^`]+)`\s*\|")
_LEGACY_CONTRACT_ID_RE = re.compile(r"^\|\s*`(?P<id>legacy:[^`]+)`\s*\|(?P<row>.*)\|\s*$")
_REQUIRED_COLUMNS = (
    "auth/signature",
    "replay/idempotency",
    "rate limit",
    "origin/host",
    "observability",
    "owner",
    "removal plan",
    "negative tests",
)


@dataclass(frozen=True)
class ContractResult:
    """Static validation result exposed for the focused unit test."""

    active_count: int
    active_ids: frozenset[str]
    contract_ids: frozenset[str]
    legacy_decorator_count: int
    legacy_loaded_count: int
    legacy_decorator_ids: frozenset[str]
    legacy_contract_ids: frozenset[str]
    legacy_loaded_ids: frozenset[str]
    legacy_wrapper_not_exempt_ids: frozenset[str]


class ContractError(RuntimeError):
    """Raised when source and the security contract diverge."""


@dataclass(frozen=True)
class LegacyScope:
    """Runtime loader map for the legacy backup source."""

    decorator_ids: frozenset[str]
    loaded_ids: frozenset[str]
    route_names: dict[str, tuple[str, ...]]
    wrapper_exempt_ids: frozenset[str]


def _is_csrf_exempt_symbol(node: ast.AST) -> bool:
    return (isinstance(node, ast.Name) and node.id == "csrf_exempt") or (
        isinstance(node, ast.Attribute) and node.attr == "csrf_exempt"
    )


def _module_name(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT).with_suffix("")
    return ".".join(relative.parts)


def _parse(path: Path) -> tuple[ast.Module, str]:
    """Parse a local Python file without importing project code."""

    if not path.exists():
        raise ContractError(f"missing runtime source: {path}")
    source = path.read_text(encoding="utf-8")
    try:
        return ast.parse(source, filename=str(path)), source
    except SyntaxError as exc:
        raise ContractError(f"cannot parse {path}: {exc}") from exc


def _string_tuple_assignment(tree: ast.Module, name: str) -> frozenset[str]:
    """Read a literal tuple/list assignment from an AST."""

    for node in tree.body:
        value = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            value = node.value
        if not isinstance(value, (ast.Tuple, ast.List, ast.Set)):
            continue
        strings = {
            item.value
            for item in value.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        }
        return frozenset(strings)
    raise ContractError(f"literal assignment {name} was not found")


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _qualified_name(node: ast.AST) -> tuple[str, ...] | None:
    """Return a dotted name only for a plain Name/Attribute chain."""

    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return tuple(reversed(parts))


def _call_argument(
    call: ast.Call,
    *,
    position: int,
    keyword: str,
) -> ast.AST | None:
    """Return one semantic call argument from positional or keyword syntax."""

    if len(call.args) > position:
        return call.args[position]
    return next(
        (item.value for item in call.keywords if item.arg == keyword),
        None,
    )


def _route_wrapper_names(tree: ast.Module, module: str) -> tuple[str, ...]:
    """Return names for ``csrf_exempt`` used as a path/re_path callback.

    URL wrappers are recognized from the route call's callback AST only.  This
    avoids treating an unrelated runtime ``csrf_exempt(...)`` helper call as a
    public endpoint and keeps multiline formatting irrelevant to discovery.
    """

    names: list[str] = []
    for route_call in ast.walk(tree):
        if not isinstance(route_call, ast.Call) or _call_name(route_call.func) not in {
            "path",
            "re_path",
        }:
            continue
        callback = route_call.args[1] if len(route_call.args) >= 2 else next(
            (
                keyword.value
                for keyword in route_call.keywords
                if keyword.arg == "view"
            ),
            None,
        )
        if not isinstance(callback, ast.Call) or not _is_csrf_exempt_symbol(callback.func):
            continue
        route_name = next(
            (
                keyword.value.value
                for keyword in route_call.keywords
                if keyword.arg == "name"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
                and keyword.value.value.strip()
            ),
            None,
        )
        if route_name is None:
            raise ContractError(
                "unnamed csrf_exempt callback route: "
                f"{module}:{route_call.lineno}"
            )
        names.append(f"wrapper:{module}:{route_name}")
    return tuple(names)


def _assigned_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        return target.id if isinstance(target, ast.Name) else None
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _assigned_names(node: ast.AST) -> frozenset[str]:
    """Return all simple names changed by an assignment statement."""

    targets: tuple[ast.AST, ...]
    if isinstance(node, ast.Assign):
        targets = tuple(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = (node.target,)
    else:
        return frozenset()
    return frozenset(
        item.id
        for target in targets
        for item in ast.walk(target)
        if isinstance(item, ast.Name)
    )


def _rebound_names(node: ast.AST) -> frozenset[str]:
    """Return local names that a non-linear statement may replace."""

    names: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_Lambda(self, item: ast.Lambda) -> None:
            # A walrus in an unexecuted lambda does not rebind this scope.
            return

        def visit_Name(self, item: ast.Name) -> None:
            if isinstance(item.ctx, (ast.Store, ast.Del)):
                names.add(item.id)

        def visit_FunctionDef(self, item: ast.FunctionDef) -> None:
            names.add(item.name)
            self.generic_visit(item)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, item: ast.ClassDef) -> None:
            names.add(item.name)
            self.generic_visit(item)

        def visit_Import(self, item: ast.Import) -> None:
            for alias in item.names:
                if alias.name != "*":
                    names.add(alias.asname or alias.name.partition(".")[0])

        def visit_ImportFrom(self, item: ast.ImportFrom) -> None:
            for alias in item.names:
                if alias.name != "*":
                    names.add(alias.asname or alias.name)

        def visit_ExceptHandler(self, item: ast.ExceptHandler) -> None:
            if item.name:
                names.add(item.name)
            self.generic_visit(item)

    Visitor().visit(node)
    return frozenset(names)


def _rhs_named_expression_targets(node: ast.AST) -> frozenset[str]:
    """Return outer-scope names rebound by ``:=`` in an assignment RHS."""

    names: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_NamedExpr(self, item: ast.NamedExpr) -> None:
            names.update(
                target.id
                for target in ast.walk(item.target)
                if isinstance(target, ast.Name)
            )
            self.visit(item.value)

        def visit_Lambda(self, item: ast.Lambda) -> None:
            # A walrus in a nested lambda binds in that lambda, not this function.
            return

    Visitor().visit(node)
    return frozenset(names)


@dataclass(frozen=True)
class _LegacyBinding:
    """One current symbolic binding in the legacy loader function."""

    kind: str
    token: int
    dependency: int | None = None
    module_name: str | None = None


def _is_backup_path_expression(
    node: ast.AST | None,
    bindings: dict[str, _LegacyBinding],
) -> bool:
    """Return whether the semantic path expression resolves to the backup."""

    if node is None:
        return False
    if isinstance(node, ast.Constant):
        return node.value == "views.py.backup"
    if isinstance(node, ast.Name):
        binding = bindings.get(node.id)
        return binding is not None and binding.kind == "path"
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "str"
        and len(node.args) == 1
        and not node.keywords
    ):
        return _is_backup_path_expression(node.args[0], bindings)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _is_path_base_expression(node.left) and (
            isinstance(node.right, ast.Constant)
            and node.right.value == "views.py.backup"
        )
    return False


def _is_path_base_expression(node: ast.AST) -> bool:
    """Recognize the Path-derived base used by the production loader."""

    if not isinstance(node, ast.Attribute) or node.attr != "parent":
        return False
    parent_chain = node.value
    while isinstance(parent_chain, ast.Attribute) and parent_chain.attr == "parent":
        parent_chain = parent_chain.value
    return (
        isinstance(parent_chain, ast.Call)
        and isinstance(parent_chain.func, ast.Attribute)
        and parent_chain.func.attr == "resolve"
        and not parent_chain.args
        and not parent_chain.keywords
        and isinstance(parent_chain.func.value, ast.Call)
        and isinstance(parent_chain.func.value.func, ast.Name)
        and parent_chain.func.value.func.id == "Path"
        and len(parent_chain.func.value.args) == 1
        and not parent_chain.func.value.keywords
        and isinstance(parent_chain.func.value.args[0], ast.Name)
        and parent_chain.func.value.args[0].id == "__file__"
    )


def _has_stdlib_importlib_provenance(
    module_tree: ast.Module,
    loader_function: ast.FunctionDef | None,
) -> bool:
    """Require the exact stdlib imports that establish ``importlib``."""

    required_imports = {"importlib.machinery", "importlib.util"}
    discovered_imports: set[str] = set()

    for node in module_tree.body:
        if node is loader_function:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound_name = alias.asname or alias.name.partition(".")[0]
                if bound_name != "importlib":
                    continue
                if alias.asname is not None or alias.name not in required_imports:
                    return False
                discovered_imports.add(alias.name)
            continue
        if isinstance(node, ast.ImportFrom):
            if any((alias.asname or alias.name) == "importlib" for alias in node.names):
                return False
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == "importlib":
                return False
            continue
        if "importlib" in _rebound_names(node):
            return False

    return required_imports <= discovered_imports


def _binding_for_name(
    node: ast.AST | None,
    bindings: dict[str, _LegacyBinding],
    kind: str,
) -> _LegacyBinding | None:
    if not isinstance(node, ast.Name):
        return None
    binding = bindings.get(node.id)
    return binding if binding is not None and binding.kind == kind else None


def _spec_name_matches_loader(
    name_argument: ast.AST | None,
    loader_argument: ast.AST | None,
    loader_binding: _LegacyBinding,
) -> bool:
    """Require a spec name derived from the exact loader binding."""

    if (
        isinstance(loader_argument, ast.Name)
        and isinstance(name_argument, ast.Attribute)
        and name_argument.attr == "name"
        and isinstance(name_argument.value, ast.Name)
        and name_argument.value.id == loader_argument.id
    ):
        return True
    return bool(
        loader_binding.module_name is not None
        and isinstance(name_argument, ast.Constant)
        and name_argument.value == loader_binding.module_name
    )


def _legacy_loader_chain_is_valid(
    module_tree: ast.Module,
    loader_function: ast.FunctionDef | None,
) -> bool:
    """Trace one exact backup loader -> spec -> module -> exec chain.

    Bindings represent the current value of each local name. Every assignment
    replaces the previous binding, so a later loader/spec/module rewire cannot
    reuse stale provenance merely because the original assignment remains in
    the AST. The analysis is deliberately fail-closed for branch-dependent
    constructions; the production loader is a straight-line chain.
    """

    if loader_function is None or not _has_stdlib_importlib_provenance(
        module_tree, loader_function
    ):
        return False
    bindings: dict[str, _LegacyBinding] = {}
    next_token = 0

    for node in loader_function.body:
        if "importlib" in _rebound_names(node):
            return False
        if isinstance(node, ast.Expr):
            for changed_name in _rebound_names(node):
                bindings.pop(changed_name, None)
            call = node.value
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            loader_attribute = call.func.value
            if call.func.attr != "exec_module" or not isinstance(
                loader_attribute, ast.Attribute
            ):
                continue
            if loader_attribute.attr != "loader":
                continue
            spec_binding = _binding_for_name(
                loader_attribute.value, bindings, "spec"
            )
            module_argument = _call_argument(
                call, position=0, keyword="module"
            )
            module_binding = _binding_for_name(
                module_argument, bindings, "module"
            )
            if (
                spec_binding is not None
                and module_binding is not None
                and module_binding.dependency == spec_binding.token
            ):
                return True
            continue

        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for changed_name in _rebound_names(node):
                bindings.pop(changed_name, None)
            continue

        changed_names = _assigned_names(node)
        rhs_rebound_names = _rhs_named_expression_targets(node.value)
        for changed_name in changed_names | rhs_rebound_names:
            bindings.pop(changed_name, None)
        name = _assigned_name(node)
        if name is None or len(changed_names) != 1:
            continue
        value = node.value
        next_token += 1
        binding: _LegacyBinding | None = None

        if _is_backup_path_expression(value, bindings):
            binding = _LegacyBinding("path", next_token)
        if isinstance(value, ast.Call):
            qualified_call = _qualified_name(value.func)
            if qualified_call == ("importlib", "machinery", "SourceFileLoader"):
                name_argument = _call_argument(
                    value, position=0, keyword="fullname"
                )
                path_argument = _call_argument(
                    value, position=1, keyword="path"
                )
                if _is_backup_path_expression(path_argument, bindings):
                    module_name = (
                        name_argument.value
                        if isinstance(name_argument, ast.Constant)
                        and isinstance(name_argument.value, str)
                        else None
                    )
                    binding = _LegacyBinding(
                        "loader", next_token, module_name=module_name
                    )
            elif qualified_call == ("importlib", "util", "spec_from_loader"):
                name_argument = _call_argument(
                    value, position=0, keyword="name"
                )
                loader_argument = _call_argument(
                    value, position=1, keyword="loader"
                )
                loader_binding = _binding_for_name(
                    loader_argument, bindings, "loader"
                )
                if loader_binding is not None and _spec_name_matches_loader(
                    name_argument, loader_argument, loader_binding
                ):
                    binding = _LegacyBinding(
                        "spec", next_token, loader_binding.token
                    )
            elif qualified_call == ("importlib", "util", "spec_from_file_location"):
                name_argument = _call_argument(
                    value, position=0, keyword="name"
                )
                location_argument = _call_argument(
                    value, position=1, keyword="location"
                )
                loader_argument = next(
                    (
                        item.value
                        for item in value.keywords
                        if item.arg == "loader"
                    ),
                    None,
                )
                loader_binding = _binding_for_name(
                    loader_argument, bindings, "loader"
                )
                if (
                    loader_binding is not None
                    and _is_backup_path_expression(location_argument, bindings)
                    and _spec_name_matches_loader(
                        name_argument, loader_argument, loader_binding
                    )
                ):
                    binding = _LegacyBinding(
                        "spec", next_token, loader_binding.token
                    )
            elif qualified_call == ("importlib", "util", "module_from_spec"):
                spec_argument = _call_argument(
                    value, position=0, keyword="spec"
                )
                spec_binding = _binding_for_name(
                    spec_argument, bindings, "spec"
                )
                if spec_binding is not None:
                    binding = _LegacyBinding(
                        "module", next_token, spec_binding.token
                    )

        if binding is None:
            bindings.pop(name, None)
        else:
            bindings[name] = binding

    return False


def discover_legacy_scope(repo_root: Path = REPO_ROOT) -> LegacyScope:
    """Map backup decorators to the loader and their outer URL wrappers.

    ``views.py.backup`` is executed through ``SourceFileLoader``. A decorator
    on the loaded function does not reach Django's middleware when the route
    exposes only the undecorated ``_legacy_view`` closure, so this distinction
    is part of the contract rather than an assumption in the Markdown.
    """

    backup_path = repo_root / LEGACY_BACKUP_PATH.relative_to(REPO_ROOT)
    init_path = repo_root / LEGACY_INIT_PATH.relative_to(REPO_ROOT)
    urls_path = repo_root / LEGACY_URLS_PATH.relative_to(REPO_ROOT)
    backup_tree, _ = _parse(backup_path)
    init_tree, _ = _parse(init_path)
    urls_tree, _ = _parse(urls_path)

    loader_function = next(
        (
            node
            for node in init_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_load_legacy_views"
        ),
        None,
    )
    if not _legacy_loader_chain_is_valid(init_tree, loader_function):
        raise ContractError(
            "legacy backup loader contract changed: expected SourceFileLoader "
            "of views.py.backup followed by exec_module"
        )

    decorated_names = {
        node.name
        for node in ast.walk(backup_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(_is_csrf_exempt_symbol(decorator) for decorator in node.decorator_list)
    }
    loader_names = _string_tuple_assignment(init_tree, "_LEGACY_VIEW_NAMES")
    decorated_ids = frozenset(f"legacy:backup:function:{name}" for name in decorated_names)
    loaded_ids = frozenset(
        f"legacy:backup:function:{name}"
        for name in decorated_names & loader_names
    )

    # Build parent links to inspect the path() call that owns each
    # _legacy_view('function_name') argument.
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(urls_tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    route_names: dict[str, list[str]] = {name: [] for name in decorated_names}
    wrapper_exempt_names: set[str] = set()
    for node in ast.walk(urls_tree):
        if not isinstance(node, ast.Call) or _call_name(node.func) != "_legacy_view":
            continue
        if (
            not node.args
            or not isinstance(node.args[0], ast.Constant)
            or not isinstance(node.args[0].value, str)
        ):
            continue
        target = node.args[0].value
        if target not in decorated_names:
            continue

        path_call = None
        wrapper_exempt = False
        ancestor: ast.AST | None = node
        while ancestor is not None:
            ancestor = parents.get(id(ancestor))
            if not isinstance(ancestor, ast.Call):
                continue
            if _is_csrf_exempt_symbol(ancestor.func):
                wrapper_exempt = True
            if _call_name(ancestor.func) == "path":
                path_call = ancestor
                break
        if path_call is None:
            continue
        route_name = next(
            (
                keyword.value.value
                for keyword in path_call.keywords
                if keyword.arg == "name"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ),
            None,
        )
        route_names[target].append(route_name or ast.unparse(path_call.args[0]))
        if wrapper_exempt:
            wrapper_exempt_names.add(target)

    route_names_frozen = {
        name: tuple(sorted(names)) for name, names in route_names.items()
    }
    wrapper_exempt_ids = frozenset(
        f"legacy:backup:function:{name}" for name in wrapper_exempt_names
    )
    return LegacyScope(
        decorator_ids=decorated_ids,
        loaded_ids=loaded_ids,
        route_names=route_names_frozen,
        wrapper_exempt_ids=wrapper_exempt_ids,
    )


def discover_active_exemptions(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    """Return stable IDs for every active non-DTF exemption occurrence."""

    try:
        tracked = subprocess.run(
            ["git", "ls-files", "-z", "--", "twocomms"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContractError(
            f"cannot enumerate tracked Python sources in {repo_root}: {exc}"
        ) from exc

    try:
        tracked_paths = sorted(
            Path(item.decode("utf-8"))
            for item in tracked.split(b"\0")
            if item and item.endswith(b".py")
        )
    except UnicodeDecodeError as exc:
        raise ContractError(
            f"tracked source path is not UTF-8 in {repo_root}: {exc}"
        ) from exc

    entries: list[str] = []
    for relative in tracked_paths:
        path = repo_root / relative
        # Resolve exclusions against the supplied root, not the module global.
        if path.name.endswith(".py.backup") or any(
            part in {"dtf", "Ideas", "migrations", "__pycache__"}
            for part in relative.parts
        ):
            continue
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:  # make parser failures actionable in CI
            raise ContractError(f"cannot parse {path}: {exc}") from exc

        module = _module_name(path) if repo_root == REPO_ROOT else ".".join(
            path.relative_to(repo_root).with_suffix("").parts
        )
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(_is_csrf_exempt_symbol(decorator) for decorator in node.decorator_list):
                entries.append(f"function:{module}.{node.name}")

        # URL-level wrappers are separate active occurrences.  They are needed
        # when a lazy module wrapper hides the inner function from CSRF middleware.
        entries.extend(_route_wrapper_names(tree, module))

    return tuple(entries)


def read_contract_ids(path: Path = CONTRACT_PATH) -> tuple[str, ...]:
    """Read machine-readable contract IDs from the Markdown table."""

    if not path.exists():
        raise ContractError(f"missing contract document: {path}")
    ids: list[str] = []
    active_header: tuple[str, ...] | None = None
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        cells = tuple(cell.strip() for cell in line.strip().split("|")[1:-1])
        lowered_cells = tuple(cell.casefold() for cell in cells)
        if "id" in lowered_cells and all(
            column in lowered_cells for column in _REQUIRED_COLUMNS
        ):
            active_header = lowered_cells
            break
    if active_header is None:
        raise ContractError(
            "contract document is missing active table columns: "
            + ", ".join(_REQUIRED_COLUMNS)
        )

    required_indexes = {
        column: active_header.index(column) for column in _REQUIRED_COLUMNS
    }
    for line in lines:
        match = _CONTRACT_ID_RE.match(line)
        if not match:
            continue
        contract_id = match.group("id")
        cells = tuple(cell.strip() for cell in line.strip().split("|")[1:-1])
        if len(cells) != len(active_header):
            raise ContractError(
                f"contract {contract_id} has {len(cells)} columns; "
                f"expected {len(active_header)}"
            )
        for column, index in required_indexes.items():
            if not cells[index]:
                raise ContractError(
                    f"empty {column} cell for contract {contract_id}"
                )
        ids.append(contract_id)
    return tuple(ids)


def read_legacy_contract_rows(path: Path = CONTRACT_PATH) -> dict[str, str]:
    """Read the legacy loader table rows keyed by backup function ID."""

    if not path.exists():
        raise ContractError(f"missing contract document: {path}")
    rows: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _LEGACY_CONTRACT_ID_RE.match(line)
        if match:
            legacy_id = match.group("id")
            if legacy_id in rows:
                raise ContractError(f"duplicate legacy contract ID: {legacy_id}")
            rows[legacy_id] = match.group("row").casefold()
    return rows


def validate_contract(
    repo_root: Path = REPO_ROOT,
    contract_path: Path = CONTRACT_PATH,
) -> ContractResult:
    """Validate exact source coverage and return the compared ID sets."""

    active_entries = discover_active_exemptions(repo_root)
    contract_entries = read_contract_ids(contract_path)
    legacy_scope = discover_legacy_scope(repo_root)
    legacy_rows = read_legacy_contract_rows(contract_path)
    active_ids = frozenset(active_entries)
    contract_ids = frozenset(contract_entries)
    legacy_contract_ids = frozenset(legacy_rows)
    legacy_wrapper_not_exempt_ids = frozenset(
        legacy_id
        for legacy_id in legacy_scope.loaded_ids - legacy_scope.wrapper_exempt_ids
        if legacy_scope.route_names.get(legacy_id.rsplit(":", 1)[-1])
    )

    errors: list[str] = []
    if len(active_entries) != len(active_ids):
        errors.append("duplicate active exemption IDs: " + ", ".join(sorted(
            item for item in active_ids if active_entries.count(item) > 1
        )))
    if len(contract_entries) != len(contract_ids):
        errors.append("duplicate contract IDs: " + ", ".join(sorted(
            item for item in contract_ids if contract_entries.count(item) > 1
        )))
    missing = sorted(active_ids - contract_ids)
    extra = sorted(contract_ids - active_ids)
    if missing:
        errors.append("missing contracts: " + ", ".join(missing))
    if extra:
        errors.append("contracts without active exemption: " + ", ".join(extra))
    legacy_missing = sorted(legacy_scope.decorator_ids - legacy_contract_ids)
    legacy_extra = sorted(legacy_contract_ids - legacy_scope.decorator_ids)
    if legacy_missing:
        errors.append("missing legacy loader contracts: " + ", ".join(legacy_missing))
    if legacy_extra:
        errors.append("legacy contracts without backup decorator: " + ", ".join(legacy_extra))

    for legacy_id in sorted(legacy_scope.decorator_ids & legacy_contract_ids):
        name = legacy_id.rsplit(":", 1)[-1]
        row = legacy_rows[legacy_id]
        if legacy_id not in legacy_scope.loaded_ids:
            if "not-loaded" not in row:
                errors.append(f"legacy contract {legacy_id} must say not-loaded")
            continue
        routes = legacy_scope.route_names.get(name, ())
        if not routes:
            errors.append(f"loaded legacy decorator has no _legacy_view route: {legacy_id}")
            continue
        required_status = (
            "wrapper-exempt"
            if legacy_id in legacy_scope.wrapper_exempt_ids
            else "wrapper-not-exempt"
        )
        if "loaded" not in row or required_status not in row:
            errors.append(
                f"legacy contract {legacy_id} must say loaded and {required_status}"
            )
    if errors:
        raise ContractError("; ".join(errors))

    return ContractResult(
        active_count=len(active_entries),
        active_ids=active_ids,
        contract_ids=contract_ids,
        legacy_decorator_count=len(legacy_scope.decorator_ids),
        legacy_loaded_count=len(legacy_scope.loaded_ids),
        legacy_decorator_ids=legacy_scope.decorator_ids,
        legacy_contract_ids=legacy_contract_ids,
        legacy_loaded_ids=legacy_scope.loaded_ids,
        legacy_wrapper_not_exempt_ids=legacy_wrapper_not_exempt_ids,
    )


def main() -> int:
    try:
        result = validate_contract()
    except ContractError as exc:
        print(f"csrf-exempt contract FAILED: {exc}", file=sys.stderr)
        return 1
    print(
        "csrf-exempt contract OK: "
        f"{result.active_count} active non-DTF exemptions, "
        f"{len(result.contract_ids)} contract rows; "
        f"legacy backup decorators={result.legacy_decorator_count}, "
        f"loaded={result.legacy_loaded_count}, "
        f"wrapper-not-exempt={len(result.legacy_wrapper_not_exempt_ids)}; "
        "no network"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
