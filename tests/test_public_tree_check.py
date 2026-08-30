"""Fail-closed tests for the complete public-tree publication gate."""

from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path

from dnadesign_data.devtools.public_tree_check import (
    build_public_data_inventory,
    check_public_tree,
    check_tag_state,
)


def _write_rights(root: Path, *, status: str = "redistributable") -> Path:
    release = root / "sources/databases/example/1.0"
    release.mkdir(parents=True)
    rights = release / "rights.json"
    rights.write_text(
        json.dumps(
            {
                "attribution": "ExampleDB 1.0.",
                "database": "ExampleDB",
                "redistribution_status": status,
                "release": "1.0",
                "reviewed_on": "2026-08-30",
                "reviewer": "test-maintainer",
                "rights_url": "https://example.test/rights",
                "schema_version": "dnadesign-data.database-rights/v1",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return release


def _seal(root: Path) -> None:
    inventory = build_public_data_inventory(root)
    (root / "PUBLIC_DATA_INVENTORY.json").write_text(
        json.dumps(inventory, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _init_repository(root: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)


def test_full_tree_rejects_database_payload_without_rights_metadata(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "sources/databases/example/1.0/model.txt"
    payload.parent.mkdir(parents=True)
    payload.write_text("model\n", encoding="utf-8")

    errors = check_public_tree(tmp_path)

    assert any("invalid rights metadata" in error for error in errors)


def test_full_tree_rejects_nonredistributable_database_payload(tmp_path: Path) -> None:
    release = _write_rights(tmp_path, status="review_blocked")
    (release / "model.txt").write_text("model\n", encoding="utf-8")
    _seal(tmp_path)

    errors = check_public_tree(tmp_path)

    assert any(
        "review_blocked database payload cannot be published" in error
        for error in errors
    )


def test_full_tree_rejects_closed_inventory_drift(tmp_path: Path) -> None:
    release = _write_rights(tmp_path)
    (release / "model.txt").write_text("model\n", encoding="utf-8")
    _seal(tmp_path)
    (release / "unreviewed.txt").write_text("new bytes\n", encoding="utf-8")

    errors = check_public_tree(tmp_path)

    assert any(
        "not declared in PUBLIC_DATA_INVENTORY.json" in error for error in errors
    )


def test_full_tree_rejects_inventory_digest_drift(tmp_path: Path) -> None:
    release = _write_rights(tmp_path)
    payload = release / "model.txt"
    payload.write_text("model\n", encoding="utf-8")
    _seal(tmp_path)
    payload.write_text("changed\n", encoding="utf-8")

    errors = check_public_tree(tmp_path)

    assert any(
        "content digest disagrees with public inventory" in error for error in errors
    )


def test_full_tree_rejects_duplicate_inventory_paths(tmp_path: Path) -> None:
    release = _write_rights(tmp_path)
    (release / "model.txt").write_text("model\n", encoding="utf-8")
    _seal(tmp_path)
    inventory_path = tmp_path / "PUBLIC_DATA_INVENTORY.json"
    inventory = json.loads(inventory_path.read_text())
    inventory["entries"].append(inventory["entries"][0])
    inventory_path.write_text(
        json.dumps(inventory, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    errors = check_public_tree(tmp_path)

    assert any("inventory repeats path" in error for error in errors)


def test_full_tree_rejects_machine_path_embedded_in_office_archive(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "review.xlsx"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(
            "xl/workbook.xml",
            "<path>/" + "Users/example/private/source.tsv</path>",
        )

    errors = check_public_tree(tmp_path)

    assert any("contains an embedded local machine path" in error for error in errors)


def test_full_tree_rejects_forbidden_payload_outside_data_shelves(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "docs/regulondb-private.tsv"
    payload.parent.mkdir(parents=True)
    payload.write_text("regulator\tsite\n", encoding="utf-8")
    _init_repository(tmp_path)
    subprocess.run(
        ["git", "add", "docs/regulondb-private.tsv"], cwd=tmp_path, check=True
    )

    errors = check_public_tree(tmp_path)

    assert any("forbidden private source payload name" in error for error in errors)


def test_full_tree_rejects_forbidden_payload_content_outside_data_shelves(
    tmp_path: Path,
) -> None:
    payload = tmp_path / "docs/source-review.tsv"
    payload.parent.mkdir(parents=True)
    payload.write_text("redistribution_status\tprivate_storage\n", encoding="utf-8")

    errors = check_public_tree(tmp_path)

    assert any(
        "forbidden nonpublic redistribution posture" in error for error in errors
    )


def test_motif_development_shelf_rejects_undeclared_payload(tmp_path: Path) -> None:
    payload = tmp_path / "sources/motif-development/private-regulondb.tsv"
    payload.parent.mkdir(parents=True)
    payload.write_text("private source bytes\n", encoding="utf-8")

    errors = check_public_tree(tmp_path)

    assert any(
        "public data path has no rights classification" in error for error in errors
    )


def test_full_tree_rejects_absolute_symlink_outside_data_shelves(
    tmp_path: Path,
) -> None:
    target = tmp_path / "outside.txt"
    target.write_text("private\n", encoding="utf-8")
    link = tmp_path / "docs/review-link"
    link.parent.mkdir(parents=True)
    link.symlink_to(target.resolve())
    _init_repository(tmp_path)
    subprocess.run(["git", "add", "docs/review-link"], cwd=tmp_path, check=True)

    errors = check_public_tree(tmp_path)

    assert any(
        "docs/review-link: symbolic links are forbidden" in error for error in errors
    )


def test_full_tree_accepts_closed_redistributable_database_release(
    tmp_path: Path,
) -> None:
    release = _write_rights(tmp_path)
    (release / "model.txt").write_text("model\n", encoding="utf-8")
    _seal(tmp_path)

    assert check_public_tree(tmp_path) == []


def test_tag_gate_requires_head_to_equal_named_clean_tag(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.test"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "README.md").write_text("fixture\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.1.0a2"\n', encoding="utf-8"
    )
    subprocess.run(
        ["git", "add", "README.md", "pyproject.toml"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    subprocess.run(["git", "tag", "v0.1.0a2"], cwd=tmp_path, check=True)

    assert check_tag_state(tmp_path, "v0.1.0a2") == []

    (tmp_path / "README.md").write_text("dirty\n", encoding="utf-8")
    assert check_tag_state(tmp_path, "v0.1.0a2") == [
        "tag publication requires a clean closed worktree"
    ]


def test_tag_gate_binds_tag_to_project_version(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.test"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.1.0a2"\n', encoding="utf-8"
    )
    subprocess.run(["git", "add", "pyproject.toml"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    subprocess.run(["git", "tag", "v0.1.0a1"], cwd=tmp_path, check=True)

    assert check_tag_state(tmp_path, "v0.1.0a1") == [
        "release tag 'v0.1.0a1' does not match project version '0.1.0a2'"
    ]


def test_tag_gate_rejects_multiple_root_histories(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.test"],
        cwd=tmp_path,
        check=True,
    )
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "fixture"\nversion = "0.1.0a2"\n', encoding="utf-8"
    )
    subprocess.run(["git", "add", "pyproject.toml"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "public root"], cwd=tmp_path, check=True)
    subprocess.run(["git", "tag", "v0.1.0a2"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "checkout", "-q", "--orphan", "unrelated"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "rm", "-fq", "pyproject.toml"], cwd=tmp_path, check=True)
    (tmp_path / "unrelated.txt").write_text("other root\n", encoding="utf-8")
    subprocess.run(["git", "add", "unrelated.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "unrelated root"], cwd=tmp_path, check=True)
    subprocess.run(["git", "checkout", "-q", "main"], cwd=tmp_path, check=True)

    assert check_tag_state(tmp_path, "v0.1.0a2") == [
        "tag publication requires one rooted public history"
    ]
