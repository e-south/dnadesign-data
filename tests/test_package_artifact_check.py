"""Tests the built-package privacy and inventory gate."""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

from dnadesign_data.devtools.package_artifact_check import check_package_artifacts


def _write_distributions(
    root: Path,
    *,
    wheel_members: dict[str, bytes] | None = None,
    sdist_members: dict[str, bytes] | None = None,
) -> Path:
    dist = root / "dist"
    dist.mkdir()
    wheel_payload = wheel_members or {"dnadesign_data/module.py": b"value = 1\n"}
    sdist_payload = sdist_members or {"dnadesign_data-1.0/module.py": b"value = 1\n"}
    with zipfile.ZipFile(dist / "dnadesign_data-1.0-py3-none-any.whl", "w") as archive:
        for name, raw in wheel_payload.items():
            archive.writestr(name, raw)
    with tarfile.open(dist / "dnadesign_data-1.0.tar.gz", "w:gz") as archive:
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
