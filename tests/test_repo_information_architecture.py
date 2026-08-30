import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_repo_has_progressive_disclosure_entrypoints() -> None:
    required_paths = [
        "AGENTS.md",
        "ARCHITECTURE.md",
        "DESIGN.md",
        "SECURITY.md",
        "QUALITY_SCORE.md",
        "docs/README.md",
        "docs/dev/README.md",
    ]

    missing = [path for path in required_paths if not (ROOT / path).exists()]

    assert missing == []


def test_agents_md_is_a_short_router_not_a_monolith() -> None:
    agents_path = ROOT / "AGENTS.md"
    lines = agents_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) <= 120
    assert "ARCHITECTURE.md" in agents_path.read_text(encoding="utf-8")
    assert "QUALITY_SCORE.md" in agents_path.read_text(encoding="utf-8")


def test_readme_is_a_light_router_with_banner() -> None:
    readme_path = ROOT / "README.md"
    text = readme_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    assert len(lines) <= 120
    assert "assets/dnadesign-data-wordmark.svg" in text
    assert "docs/data-sources/README.md" in text
    assert "docs/functional-annotations.md" in text
    assert "https://github.com/e-south/dnadesign" in text
    assert "## Package Boundary" not in text
    assert "## Common Commands" not in text
    assert "## Functional Annotation Artifacts" not in text
    assert "## Data Sources by Category" not in text


def test_data_source_catalog_lives_under_docs() -> None:
    catalog_path = ROOT / "docs/data-sources/README.md"
    text = catalog_path.read_text(encoding="utf-8")

    assert "# Data Sources" in text
    assert "regulatory-parts.md" in text
    assert "comparative-omics.md" in text
    assert "promoter-engineering.md" in text
    assert "other-literature.md" in text


def test_data_source_catalog_is_progressively_disclosed() -> None:
    assert not (ROOT / "docs/data-sources.md").exists()

    source_pages = [
        ROOT / "docs/data-sources/regulatory-parts.md",
        ROOT / "docs/data-sources/comparative-omics.md",
        ROOT / "docs/data-sources/promoter-engineering.md",
        ROOT / "docs/data-sources/other-literature.md",
        ROOT / "docs/data-sources/folder-organization.md",
    ]
    oversized = {
        str(path.relative_to(ROOT)): len(path.read_text(encoding="utf-8").splitlines())
        for path in source_pages
        if len(path.read_text(encoding="utf-8").splitlines()) > 275
    }

    assert oversized == {}


def test_folder_organization_documents_active_semantic_layout() -> None:
    text = (ROOT / "docs/data-sources/folder-organization.md").read_text(
        encoding="utf-8"
    )

    assert "sources/databases/regulondb/<release>/" in text
    assert "sources/databases/ecocyc/<release>/" in text
    assert "sources/databases/jaspar/<release>/" in text
    assert "sources/literature/<citation_slug>/" in text
    assert "sources/" in text
    assert "databases/" in text
    assert "generated/" in text
    assert "functional_annotations/" in text
    assert "motif_models/" in text
    assert "fail fast" in text
    assert "Source shelves do not contain active scripts." in text


def test_legacy_root_data_shelves_are_not_present() -> None:
    legacy_shelves = [
        "RegulonDB_11",
        "RegulonDB_13",
        "EcoCyc_28",
        "GeneOntology",
        "BioCyc",
        "primary_literature",
    ]

    present = [path for path in legacy_shelves if (ROOT / path).exists()]

    assert present == []


def test_docs_index_routes_major_workflows() -> None:
    text = (ROOT / "docs/README.md").read_text(encoding="utf-8")

    required_routes = (
        "data-sources/README.md",
        "motif-sources/README.md",
        "package-apis.md",
        "functional-annotations.md",
        "dev/README.md",
        "../SECURITY.md",
        "../AGENTS.md",
    )

    for route in required_routes:
        assert route in text


def test_motif_source_docs_are_progressive_and_routable() -> None:
    index = ROOT / "docs/motif-sources/README.md"
    contracts = ROOT / "docs/motif-sources/contracts.md"
    providers = ROOT / "docs/motif-sources/providers.md"

    assert index.is_file()
    assert contracts.is_file()
    assert providers.is_file()
    index_text = index.read_text(encoding="utf-8")
    assert index_text.startswith("---\n")
    assert "contracts.md" in index_text
    assert "providers.md" in index_text
    assert "Motif Balance" in index_text
    assert "universal adapter" in index_text
    oversized = {
        str(path.relative_to(ROOT)): len(path.read_text(encoding="utf-8").splitlines())
        for path in (index, contracts, providers)
        if len(path.read_text(encoding="utf-8").splitlines()) > 220
    }
    assert oversized == {}


def test_motif_source_docs_keep_product_and_study_policy_out() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "docs/motif-sources").glob("*.md"))
    )

    assert "manuscript figure" not in text.lower()
    assert "benchmark conclusion" not in text.lower()
    assert "site window" in text.lower()
    assert "study-owned" in text.lower()
    assert "binding-site-set/v1" in text


def test_ci_uses_uv_cache_precommit_and_docs_checks() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "astral-sh/setup-uv" in workflow
    assert "enable-cache: true" in workflow
    assert "uv lock --check" in workflow
    assert "uv run pre-commit run --all-files" in workflow
    assert "uv run python -m dnadesign_data.devtools.docs_check" in workflow
    assert "uv run python -m dnadesign_data.devtools.publication_check" in workflow
    assert "uv run pip-audit --local" in workflow
    assert "uv run dnadesign-data-sources list --kind all --indent 0" in workflow
    assert "uv run dnadesign-data-sources schema --indent 0" in workflow
    assert (
        "uv run dnadesign-data-sources check --require-source "
        "regulondb_13_tf_riset --summary-only --indent 0"
    ) in workflow
    assert "uv build" in workflow


def test_dependency_and_security_automation_are_declared() -> None:
    dependabot = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
    codeql = (ROOT / ".github/workflows/codeql.yml").read_text(encoding="utf-8")

    assert "package-ecosystem: uv" in dependabot
    assert "package-ecosystem: github-actions" in dependabot
    assert "package-ecosystem: pre-commit" in dependabot
    assert "github/codeql-action/init" in codeql
    assert "github/codeql-action/analyze" in codeql
    assert (ROOT / ".github/workflows/dependency-review.yml").is_file()


def test_tracked_python_lives_under_src_or_tests() -> None:
    result = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    misplaced = [
        path
        for path in result.stdout.splitlines()
        if not path.startswith(("src/", "tests/"))
    ]

    assert misplaced == []


def test_source_modules_stay_below_monolith_threshold() -> None:
    max_source_module_lines = 550
    source_paths = sorted((ROOT / "src").rglob("*.py"))
    oversized = {
        str(path.relative_to(ROOT)): len(path.read_text(encoding="utf-8").splitlines())
        for path in source_paths
        if len(path.read_text(encoding="utf-8").splitlines()) > max_source_module_lines
    }

    assert oversized == {}


def test_source_modules_use_canonical_header_contract() -> None:
    source_paths = sorted((ROOT / "src").rglob("*.py"))
    bad_headers: dict[str, str] = {}
    forbidden_claims: dict[str, list[str]] = {}
    forbidden_patterns = ("OpenAI", "Codex", "Coded by", "Generated by")

    for path in source_paths:
        relative = path.relative_to(ROOT).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        expected_prefix = [
            '"""',
            "--------------------------------------------------------------------------------",
            "dnadesign-data",
            f"dnadesign-data/{relative}",
            "",
        ]
        expected_suffix = [
            "",
            "Module Author(s): Eric J. South",
            "--------------------------------------------------------------------------------",
            '"""',
        ]
        if (
            lines[:5] != expected_prefix
            or len(lines) < 10
            or not lines[5].endswith(".")
            or lines[6:10] != expected_suffix
        ):
            bad_headers[relative] = "\n".join(lines[:10])
        matches = [
            pattern for pattern in forbidden_patterns if pattern in "\n".join(lines)
        ]
        if matches:
            forbidden_claims[relative] = matches

    assert bad_headers == {}
    assert forbidden_claims == {}


def test_source_discovery_api_uses_catalog_package_without_legacy_shims() -> None:
    assert (ROOT / "src/dnadesign_data/catalog/sources.py").exists()
    assert (ROOT / "src/dnadesign_data/catalog/regulatory_parts.py").exists()
    assert (ROOT / "src/dnadesign_data/catalog/functional_annotations.py").exists()
    assert not (ROOT / "src/dnadesign_data/regulatory_parts.py").exists()
    assert not (ROOT / "src/dnadesign_data/functional_annotations.py").exists()
    assert not (ROOT / "src/dnadesign_data/layout.py").exists()

    assert importlib.util.find_spec("dnadesign_data.regulatory_parts") is None
    assert importlib.util.find_spec("dnadesign_data.functional_annotations") is None
    assert importlib.util.find_spec("dnadesign_data.layout") is None
