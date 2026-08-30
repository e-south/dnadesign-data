"""Tests the built-package privacy and inventory gate."""

from __future__ import annotations

import io
import json
import tarfile
import zipfile
from pathlib import Path

from dnadesign_data.devtools.package_artifact_check import check_package_artifacts


def _write_distributions(
    root: Path,
    *,
    wheel_members: dict[str, bytes] | None = None,
    sdist_members: dict[str, bytes] | None = None,
    archive_name: str = "dnadesign_data",
    archive_version: str = "1.0",
    metadata_name: str = "dnadesign-data",
) -> Path:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "dnadesign-data"\nversion = "1.0"\n', encoding="utf-8"
    )
    dist = root / "dist"
    dist.mkdir()
    metadata = (
        f"Metadata-Version: 2.4\nName: {metadata_name}\nVersion: {archive_version}\n"
    ).encode()
    wheel_payload = {
        "dnadesign_data/__init__.py": b'"""Package."""\n',
        f"{archive_name}-{archive_version}.dist-info/METADATA": metadata,
        f"{archive_name}-{archive_version}.dist-info/RECORD": b"",
        f"{archive_name}-{archive_version}.dist-info/WHEEL": b"Wheel-Version: 1.0\n",
        **(wheel_members or {}),
    }
    sdist_root = f"{archive_name}-{archive_version}"
    sdist_payload = {
        f"{sdist_root}/PKG-INFO": metadata,
        f"{sdist_root}/pyproject.toml": (
            f'[project]\nname = "{metadata_name}"\nversion = "{archive_version}"\n'
        ).encode(),
        f"{sdist_root}/src/dnadesign_data/__init__.py": b'"""Package."""\n',
        **(sdist_members or {}),
    }
    wheel_name = f"{archive_name}-{archive_version}-py3-none-any.whl"
    with zipfile.ZipFile(dist / wheel_name, "w") as archive:
        for name, raw in wheel_payload.items():
            archive.writestr(name, raw)
    with tarfile.open(
        dist / f"{archive_name}-{archive_version}.tar.gz", "w:gz"
    ) as archive:
        for name, raw in sdist_payload.items():
            member = tarfile.TarInfo(name)
            member.size = len(raw)
            archive.addfile(member, io.BytesIO(raw))
    return dist


def test_package_gate_accepts_adapter_module_names(tmp_path: Path) -> None:
    dist = _write_distributions(
        tmp_path,
        wheel_members={
            "dnadesign_data/motifs/regulondb.py": b"class Adapter: pass\n",
            "dnadesign_data/functional/ecocyc_go.py": b"class Adapter: pass\n",
        },
    )

    assert check_package_artifacts(dist) == []


def test_package_gate_rejects_source_or_generated_data_shelf(tmp_path: Path) -> None:
    dist = _write_distributions(
        tmp_path,
        sdist_members={
            "dnadesign_data-1.0/sources/databases/example/model.tsv": b"private\n",
            "dnadesign_data-1.0/generated/motif_models/model.json": b"{}\n",
        },
    )

    errors = check_package_artifacts(dist)

    assert (
        sum("private or repository data shelf is packaged" in error for error in errors)
        == 2
    )


def test_package_gate_rejects_neutral_data_members(tmp_path: Path) -> None:
    dist = _write_distributions(
        tmp_path,
        wheel_members={"dnadesign_data/review.tsv": b"record\tvalue\n"},
        sdist_members={"dnadesign_data-1.0/review.parquet": b"PAR1"},
    )

    errors = check_package_artifacts(dist)

    assert (
        sum("data-like member is not allowed in package" in error for error in errors)
        == 2
    )


def test_package_gate_rejects_canonical_nonpublic_posture_json(tmp_path: Path) -> None:
    posture_key = "redistribution_" + "status"
    private_posture = "private_" + "storage"
    review_posture = "review_" + "blocked"
    private_json = (
        json.dumps(
            {"records": ["ACTG"], posture_key: private_posture},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    review_json = (
        json.dumps(
            {"records": ["ACTG"], posture_key: review_posture},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    dist = _write_distributions(
        tmp_path,
        wheel_members={"dnadesign_data/private.json": private_json},
        sdist_members={"dnadesign_data-1.0/review.json": review_json},
    )

    errors = check_package_artifacts(dist)

    assert (
        sum("nonpublic redistribution posture is packaged" in error for error in errors)
        == 2
    )


def test_package_gate_rejects_unrelated_distribution_identity(tmp_path: Path) -> None:
    dist = _write_distributions(
        tmp_path,
        archive_name="unrelated",
        archive_version="2.0",
        metadata_name="unrelated",
    )

    errors = check_package_artifacts(dist)

    assert any("wheel filename does not match pyproject" in error for error in errors)
    assert any("sdist filename does not match pyproject" in error for error in errors)
    assert any("required package member is missing" in error for error in errors)


def test_package_gate_rejects_machine_home_and_credentials(tmp_path: Path) -> None:
    home_path = b"/" + b"Users/example/private/source.tsv"
    private_key = b"-----BEGIN " + b"PRIVATE KEY-----\nsecret\n"
    dist = _write_distributions(
        tmp_path,
        wheel_members={
            "dnadesign_data/config.py": b"SOURCE = b'" + home_path + b"'\n",
            "dnadesign_data/.env": b"TOKEN=secret\n",
            "dnadesign_data/key.txt": private_key,
        },
    )

    errors = check_package_artifacts(dist)

    assert any("local machine home path is packaged" in error for error in errors)
    assert any(
        "credential-bearing member name is packaged" in error for error in errors
    )
    assert any("credential material is packaged" in error for error in errors)


def test_package_gate_requires_exactly_wheel_and_sdist(tmp_path: Path) -> None:
    dist = _write_distributions(tmp_path)
    (dist / "unexpected.txt").write_text("extra\n", encoding="utf-8")

    assert check_package_artifacts(dist) == [
        "distribution directory must contain exactly one wheel and one .tar.gz sdist"
    ]


def test_package_gate_accepts_uv_build_gitignore_marker(tmp_path: Path) -> None:
    dist = _write_distributions(tmp_path)
    (dist / ".gitignore").write_bytes(b"*")

    assert check_package_artifacts(dist) == []
