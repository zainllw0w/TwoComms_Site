"""No-network coverage gate for the active csrf_exempt contract."""

import tempfile
import textwrap
import unittest
from pathlib import Path

from scripts.check_csrf_exempt_contract import (
    ContractError,
    discover_active_exemptions,
    discover_legacy_scope,
    read_contract_ids,
    validate_contract,
)


class CsrfExemptContractTests(unittest.TestCase):
    """Keep every active non-DTF exemption represented in the security doc."""

    def _write_legacy_fixture(self, repo_root: Path, loader_body: str) -> None:
        storefront = repo_root / "twocomms" / "storefront"
        views_package = storefront / "views"
        views_package.mkdir(parents=True)
        (storefront / "views.py.backup").write_text(
            "from django.views.decorators.csrf import csrf_exempt\n"
            "@csrf_exempt\n"
            "def legacy(request):\n"
            "    return request\n",
            encoding="utf-8",
        )
        (views_package / "__init__.py").write_text(
            textwrap.dedent(
                """
                import importlib.machinery
                import importlib.util

                _LEGACY_VIEW_NAMES = ("legacy",)

                def _load_legacy_views():
                """
            )
            + textwrap.indent(textwrap.dedent(loader_body), "    "),
            encoding="utf-8",
        )
        (storefront / "urls.py").write_text(
            "from django.urls import path\n"
            "urlpatterns = ["
            "path('legacy/', _legacy_view('legacy'), name='legacy')"
            "]\n",
            encoding="utf-8",
        )

    def test_active_exemptions_are_all_contracted(self):
        result = validate_contract()
        self.assertEqual(result.active_count, 25)
        self.assertEqual(result.active_ids, result.contract_ids)
        self.assertEqual(result.legacy_decorator_count, 7)
        self.assertEqual(result.legacy_loaded_count, 4)
        self.assertEqual(result.legacy_decorator_ids, result.legacy_contract_ids)
        self.assertEqual(
            result.legacy_loaded_ids,
            frozenset(
                {
                    "legacy:backup:function:generate_wholesale_invoice",
                    "legacy:backup:function:delete_wholesale_invoice",
                    "legacy:backup:function:create_wholesale_payment",
                    "legacy:backup:function:wholesale_payment_webhook",
                }
            ),
        )
        self.assertEqual(result.legacy_wrapper_not_exempt_ids, result.legacy_loaded_ids)

    def test_url_wrappers_are_discovered_only_from_named_path_callbacks(self):
        """A runtime helper call must not become a URL wrapper contract row."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            source_path = repo_root / "twocomms" / "routes.py"
            source_path.parent.mkdir(parents=True)
            source_path.write_text(
                textwrap.dedent(
                    """
                    from django.urls import path, re_path
                    from django.views.decorators.csrf import csrf_exempt

                    @csrf_exempt
                    def decorated(request):
                        return request

                    runtime_helper = csrf_exempt(not_a_callback)

                    urlpatterns = [
                        path(
                            "multiline/",
                            csrf_exempt(multiline_callback),
                            name="multiline_callback",
                        ),
                        re_path(
                            r"^regex/$",
                            csrf_exempt(regex_callback),
                            name="regex_callback",
                        ),
                    ]
                    """
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                discover_active_exemptions(repo_root),
                (
                    "function:twocomms.routes.decorated",
                    "wrapper:twocomms.routes:multiline_callback",
                    "wrapper:twocomms.routes:regex_callback",
                ),
            )

    def test_unnamed_url_wrapper_fails_with_an_actionable_contract_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            source_path = repo_root / "twocomms" / "routes.py"
            source_path.parent.mkdir(parents=True)
            source_path.write_text(
                "from django.urls import path\n"
                "from django.views.decorators.csrf import csrf_exempt\n"
                "urlpatterns = [path('unnamed/', csrf_exempt(callback))]\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ContractError,
                r"unnamed csrf_exempt callback route: twocomms\.routes",
            ):
                discover_active_exemptions(repo_root)

    def test_legacy_loader_requires_one_dataflow_chain(self):
        """Unrelated loader/spec/module calls must not satisfy the legacy gate."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            storefront = repo_root / "twocomms" / "storefront"
            views_package = storefront / "views"
            views_package.mkdir(parents=True)
            (storefront / "views.py.backup").write_text(
                "from django.views.decorators.csrf import csrf_exempt\n"
                "@csrf_exempt\n"
                "def legacy(request):\n"
                "    return request\n",
                encoding="utf-8",
            )
            (views_package / "__init__.py").write_text(
                textwrap.dedent(
                    """
                    import importlib.machinery
                    import importlib.util

                    _LEGACY_VIEW_NAMES = ("legacy",)

                    def _load_legacy_views():
                        backup_name = "views.py.backup"
                        SourceFileLoader("unrelated", "unrelated.py")
                        loader = object()
                        spec = importlib.util.spec_from_loader(loader, loader)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                    """
                ),
                encoding="utf-8",
            )
            (storefront / "urls.py").write_text(
                "from django.urls import path\n"
                "urlpatterns = [path('legacy/', _legacy_view('legacy'), name='legacy')]\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ContractError,
                r"legacy backup loader contract changed",
            ):
                discover_legacy_scope(repo_root)

    def test_legacy_exec_module_must_use_the_spec_that_created_module(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            storefront = repo_root / "twocomms" / "storefront"
            views_package = storefront / "views"
            views_package.mkdir(parents=True)
            (storefront / "views.py.backup").write_text(
                "from django.views.decorators.csrf import csrf_exempt\n"
                "@csrf_exempt\n"
                "def legacy(request):\n"
                "    return request\n",
                encoding="utf-8",
            )
            (views_package / "__init__.py").write_text(
                textwrap.dedent(
                    """
                    import importlib.machinery
                    import importlib.util

                    _LEGACY_VIEW_NAMES = ("legacy",)

                    def _load_legacy_views():
                        legacy_path = "views.py.backup"
                        loader = importlib.machinery.SourceFileLoader("legacy", legacy_path)
                        spec_one = importlib.util.spec_from_loader(loader.name, loader)
                        spec_two = importlib.util.spec_from_loader(loader.name, loader)
                        legacy_module = importlib.util.module_from_spec(spec_two)
                        spec_one.loader.exec_module(legacy_module)
                    """
                ),
                encoding="utf-8",
            )
            (storefront / "urls.py").write_text(
                "from django.urls import path\n"
                "urlpatterns = [path('legacy/', _legacy_view('legacy'), name='legacy')]\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ContractError,
                r"legacy backup loader contract changed",
            ):
                discover_legacy_scope(repo_root)

    def test_spec_from_loader_must_bind_its_actual_loader_argument(self):
        """A loader name in spec_from_loader's first arg is not its loader."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            storefront = repo_root / "twocomms" / "storefront"
            views_package = storefront / "views"
            views_package.mkdir(parents=True)
            (storefront / "views.py.backup").write_text(
                "from django.views.decorators.csrf import csrf_exempt\n"
                "@csrf_exempt\n"
                "def legacy(request):\n"
                "    return request\n",
                encoding="utf-8",
            )
            (views_package / "__init__.py").write_text(
                textwrap.dedent(
                    """
                    import importlib.machinery
                    import importlib.util

                    _LEGACY_VIEW_NAMES = ("legacy",)

                    def _load_legacy_views():
                        legacy_path = "views.py.backup"
                        loader = importlib.machinery.SourceFileLoader("legacy", legacy_path)
                        unrelated_loader = object()
                        spec = importlib.util.spec_from_loader(
                            loader.name,
                            unrelated_loader,
                        )
                        legacy_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(legacy_module)
                    """
                ),
                encoding="utf-8",
            )
            (storefront / "urls.py").write_text(
                "from django.urls import path\n"
                "urlpatterns = [path('legacy/', _legacy_view('legacy'), name='legacy')]\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ContractError,
                r"legacy backup loader contract changed",
            ):
                discover_legacy_scope(repo_root)

    def test_source_file_loader_must_bind_its_actual_path_argument(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            self._write_legacy_fixture(
                repo_root,
                """
                backup_name = "views.py.backup"
                loader = importlib.machinery.SourceFileLoader(
                    backup_name,
                    "unrelated.py",
                )
                spec = importlib.util.spec_from_loader(loader.name, loader)
                legacy_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(legacy_module)
                """,
            )

            with self.assertRaisesRegex(
                ContractError,
                r"legacy backup loader contract changed",
            ):
                discover_legacy_scope(repo_root)

    def test_backup_path_expression_must_resolve_to_the_backup(self):
        path_expressions = (
            '("views.py.backup", "unrelated.py")[1]',
            '"views.py.backup" if use_backup else "unrelated.py"',
            'Path(__file__).arbitrary() / "views.py.backup"',
            'Path(__file__).resolve().arbitrary / "views.py.backup"',
        )
        for path_expression in path_expressions:
            with self.subTest(path_expression=path_expression), tempfile.TemporaryDirectory() as temporary_directory:
                repo_root = Path(temporary_directory)
                self._write_legacy_fixture(
                    repo_root,
                    f"""
                    legacy_path = {path_expression}
                    loader = importlib.machinery.SourceFileLoader(
                        "legacy",
                        legacy_path,
                    )
                    spec = importlib.util.spec_from_loader(loader.name, loader)
                    legacy_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(legacy_module)
                    """,
                )

                with self.assertRaisesRegex(
                    ContractError,
                    r"legacy backup loader contract changed",
                ):
                    discover_legacy_scope(repo_root)

    def test_spec_must_bind_the_actual_loader_name(self):
        factories = {
            "spec_from_loader": """
                spec = importlib.util.spec_from_loader("unrelated", loader)
            """,
            "spec_from_file_location": """
                spec = importlib.util.spec_from_file_location(
                    "unrelated",
                    legacy_path,
                    loader=loader,
                )
            """,
        }
        for factory, spec_statement in factories.items():
            with self.subTest(factory=factory), tempfile.TemporaryDirectory() as temporary_directory:
                repo_root = Path(temporary_directory)
                self._write_legacy_fixture(
                    repo_root,
                    f"""
                    legacy_path = "views.py.backup"
                    loader = importlib.machinery.SourceFileLoader(
                        "legacy",
                        legacy_path,
                    )
                    {textwrap.dedent(spec_statement).strip()}
                    legacy_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(legacy_module)
                    """,
                )

                with self.assertRaisesRegex(
                    ContractError,
                    r"legacy backup loader contract changed",
                ):
                    discover_legacy_scope(repo_root)

    def test_legacy_loader_chain_rejects_rebound_variables(self):
        cases = {
            "loader": """
                legacy_path = "views.py.backup"
                loader = importlib.machinery.SourceFileLoader("legacy", legacy_path)
                loader = unrelated_loader
                spec = importlib.util.spec_from_loader(loader.name, loader)
                legacy_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(legacy_module)
            """,
            "spec": """
                legacy_path = "views.py.backup"
                loader = importlib.machinery.SourceFileLoader("legacy", legacy_path)
                spec = importlib.util.spec_from_loader(loader.name, loader)
                legacy_module = importlib.util.module_from_spec(spec)
                spec = unrelated_spec
                spec.loader.exec_module(legacy_module)
            """,
            "module": """
                legacy_path = "views.py.backup"
                loader = importlib.machinery.SourceFileLoader("legacy", legacy_path)
                spec = importlib.util.spec_from_loader(loader.name, loader)
                legacy_module = importlib.util.module_from_spec(spec)
                legacy_module = unrelated_module
                spec.loader.exec_module(legacy_module)
            """,
        }
        for variable, loader_body in cases.items():
            with self.subTest(variable=variable), tempfile.TemporaryDirectory() as temporary_directory:
                repo_root = Path(temporary_directory)
                self._write_legacy_fixture(repo_root, loader_body)
                with self.assertRaisesRegex(
                    ContractError,
                    r"legacy backup loader contract changed",
                ):
                    discover_legacy_scope(repo_root)

    def test_spec_from_file_location_accepts_the_actual_loader_chain(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            self._write_legacy_fixture(
                repo_root,
                """
                legacy_path = "views.py.backup"
                loader = importlib.machinery.SourceFileLoader("legacy", legacy_path)
                spec = importlib.util.spec_from_file_location(
                    loader.name,
                    legacy_path,
                    loader=loader,
                )
                legacy_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(legacy_module)
                """,
            )

            scope = discover_legacy_scope(repo_root)

            self.assertEqual(
                scope.loaded_ids,
                frozenset({"legacy:backup:function:legacy"}),
            )

    def test_each_active_contract_row_requires_all_security_cells(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            contract_path = Path(temporary_directory) / "contract.md"
            contract_path.write_text(
                textwrap.dedent(
                    """
                    | ID | Route(s) | Method | Auth/signature | Replay/idempotency | Rate limit | Origin/host | Observability | Owner | Removal plan | Negative tests |
                    | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
                    | `function:twocomms.example.webhook` | `/hook/` | POST | signature | replay marker | 10/m | main host | structured warning | Example | remove after migration | missing signature |
                    | `function:twocomms.example.incomplete` | `/incomplete/` | POST |  | replay marker | 10/m | main host | structured warning | Example | remove after migration | missing signature |
                    """
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ContractError,
                r"empty auth/signature cell for contract function:twocomms\.example\.incomplete",
            ):
                read_contract_ids(contract_path)

    def test_observability_owner_and_removal_plan_cells_are_required(self):
        columns = ("Observability", "Owner", "Removal plan")
        for empty_column in columns:
            with self.subTest(empty_column=empty_column), tempfile.TemporaryDirectory() as temporary_directory:
                contract_path = Path(temporary_directory) / "contract.md"
                row = {
                    "Observability": "structured warning",
                    "Owner": "Storefront",
                    "Removal plan": "remove after signed migration",
                }
                row[empty_column] = ""
                contract_path.write_text(
                    textwrap.dedent(
                        f"""
                        | ID | Route(s) | Method | Auth/signature | Replay/idempotency | Rate limit | Origin/host | Observability | Owner | Removal plan | Negative tests |
                        | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
                        | `function:twocomms.example.webhook` | `/hook/` | POST | signature | replay marker | 10/m | main host | {row["Observability"]} | {row["Owner"]} | {row["Removal plan"]} | missing signature |
                        """
                    ),
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(
                    ContractError,
                    rf"empty {empty_column.casefold()} cell",
                ):
                    read_contract_ids(contract_path)

    def test_legacy_chain_cannot_cross_control_flow_branches(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            self._write_legacy_fixture(
                repo_root,
                """
                legacy_path = "views.py.backup"
                if enabled:
                    loader = importlib.machinery.SourceFileLoader(
                        "legacy",
                        legacy_path,
                    )
                else:
                    spec = importlib.util.spec_from_loader(loader.name, loader)
                legacy_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(legacy_module)
                """,
            )

            with self.assertRaisesRegex(
                ContractError,
                r"legacy backup loader contract changed",
            ):
                discover_legacy_scope(repo_root)

    def test_compound_assignment_invalidates_a_loader_binding(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            self._write_legacy_fixture(
                repo_root,
                """
                legacy_path = "views.py.backup"
                loader = importlib.machinery.SourceFileLoader(
                    "legacy",
                    legacy_path,
                )
                loader = unrelated = object()
                spec = importlib.util.spec_from_loader(loader.name, loader)
                legacy_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(legacy_module)
                """,
            )

            with self.assertRaisesRegex(
                ContractError,
                r"legacy backup loader contract changed",
            ):
                discover_legacy_scope(repo_root)

    def test_control_flow_assignment_invalidates_a_loader_binding(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            self._write_legacy_fixture(
                repo_root,
                """
                legacy_path = "views.py.backup"
                loader = importlib.machinery.SourceFileLoader(
                    "legacy",
                    legacy_path,
                )
                if enabled:
                    loader = unrelated_loader
                spec = importlib.util.spec_from_loader(loader.name, loader)
                legacy_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(legacy_module)
                """,
            )

            with self.assertRaisesRegex(
                ContractError,
                r"legacy backup loader contract changed",
            ):
                discover_legacy_scope(repo_root)

    def test_non_linear_rebindings_are_fail_closed(self):
        rebindings = {
            "named expression": "if enabled:\n    (loader := unrelated_loader)",
            "loop target": "for loader in loaders:\n    pass",
            "with target": "with manager as loader:\n    pass",
            "delete": "if enabled:\n    del loader",
            "function definition": "if enabled:\n    def loader():\n        pass",
            "import alias": "if enabled:\n    import unrelated as loader",
        }
        for case, rebinding in rebindings.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary_directory:
                repo_root = Path(temporary_directory)
                indented_rebinding = textwrap.indent(rebinding, "                    " ).lstrip()
                self._write_legacy_fixture(
                    repo_root,
                    f"""
                    legacy_path = "views.py.backup"
                    loader = importlib.machinery.SourceFileLoader(
                        "legacy",
                        legacy_path,
                    )
                    {indented_rebinding}
                    spec = importlib.util.spec_from_loader(loader.name, loader)
                    legacy_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(legacy_module)
                    """,
                )

                with self.assertRaisesRegex(
                    ContractError,
                    r"legacy backup loader contract changed",
                ):
                    discover_legacy_scope(repo_root)

    def test_top_level_named_expression_invalidates_a_loader_binding(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            self._write_legacy_fixture(
                repo_root,
                """
                legacy_path = "views.py.backup"
                loader = importlib.machinery.SourceFileLoader(
                    "legacy",
                    legacy_path,
                )
                (loader := unrelated_loader)
                spec = importlib.util.spec_from_loader(loader.name, loader)
                legacy_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(legacy_module)
                """,
            )

            with self.assertRaisesRegex(
                ContractError,
                r"legacy backup loader contract changed",
            ):
                discover_legacy_scope(repo_root)

    def test_rhs_named_expression_invalidates_a_loader_binding(self):
        rhs_expressions = (
            "(loader := unrelated_loader)",
            "[(loader := unrelated_loader)]",
            "consume(value=(loader := unrelated_loader))",
        )
        for rhs_expression in rhs_expressions:
            with self.subTest(rhs_expression=rhs_expression), tempfile.TemporaryDirectory() as temporary_directory:
                repo_root = Path(temporary_directory)
                self._write_legacy_fixture(
                    repo_root,
                    f"""
                legacy_path = "views.py.backup"
                loader = importlib.machinery.SourceFileLoader(
                    "legacy",
                    legacy_path,
                )
                ignored = {rhs_expression}
                spec = importlib.util.spec_from_loader(loader.name, loader)
                legacy_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(legacy_module)
                """,
                )

                with self.assertRaisesRegex(
                    ContractError,
                    r"legacy backup loader contract changed",
                ):
                    discover_legacy_scope(repo_root)

    def test_named_expression_inside_lambda_keeps_outer_loader_binding(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo_root = Path(temporary_directory)
            self._write_legacy_fixture(
                repo_root,
                """
                legacy_path = "views.py.backup"
                loader = importlib.machinery.SourceFileLoader(
                    "legacy",
                    legacy_path,
                )
                deferred = lambda: (loader := unrelated_loader)
                spec = importlib.util.spec_from_loader(loader.name, loader)
                legacy_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(legacy_module)
                """,
            )

            scope = discover_legacy_scope(repo_root)

            self.assertEqual(
                scope.loaded_ids,
                frozenset({"legacy:backup:function:legacy"}),
            )


if __name__ == "__main__":
    unittest.main()
