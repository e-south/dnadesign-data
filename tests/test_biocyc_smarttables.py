from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from dnadesign_data.functional.biocyc_client import BioCycSmartTableClient
from dnadesign_data.functional.biocyc_credentials import (
    initialize_transient_password_file,
    resolve_biocyc_credentials,
    store_biocyc_keychain_password,
)
from dnadesign_data.functional.biocyc_smarttables import (
    build_biocyc_smarttable_artifacts,
)
from dnadesign_data.functional.biocyc_smarttables_cli import main
from dnadesign_data.functional.go_parsers import parse_smarttable_go_tsv


def _write_network_regulator_gene(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(  # noqa: FLY002 - fixture lines are intentionally tabular
            [
                "# fixture",
                (
                    "1)regulatorId\t2)regulatorName\t3)RegulatorGeneName"
                    "\t4)regulatedId\t5)regulatedName\t6)function\t7)confidenceLevel "
                ),
                "RDBECOLITFC00170\tCpxR\tcpxR\tRDBECOLIGNC00001\tspy\t+\tS ",
                "RDBECOLITFC00214\tLexA\tlexA\tRDBECOLIGNC00002\trecA\t-\tS ",
            ]
        ),
        encoding="utf-8",
    )


def _write_go_basic_obo(root: Path) -> None:
    path = (
        root
        / "generated/functional_annotations/gene_ontology/2026-03-25/ontology/go-basic.obo"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(  # noqa: FLY002 - fixture lines are intentionally tabular
            [
                "format-version: 1.2",
                "",
                "[Term]",
                "id: GO:0003700",
                "name: DNA-binding transcription factor activity",
                "namespace: molecular_function",
                "",
                "[Term]",
                "id: GO:0045892",
                "name: negative regulation of transcription",
                "namespace: biological_process",
                "",
                "[Term]",
                "id: GO:0005829",
                "name: cytosol",
                "namespace: cellular_component",
                "",
                "[Term]",
                "id: GO:0001217",
                "name: DNA-binding transcription repressor activity",
                "namespace: molecular_function",
                "",
                "[Term]",
                "id: GO:0009432",
                "name: SOS response",
                "namespace: biological_process",
                "",
                "[Term]",
                "id: GO:0006974",
                "name: DNA damage response",
                "namespace: biological_process",
            ]
        ),
        encoding="utf-8",
    )


class FakeSmartTableClient(BioCycSmartTableClient):
    def __init__(self) -> None:
        super().__init__(username="user", password="secret")  # pragma: allowlist secret
        self.created_payloads: list[dict[str, object]] = []
        self.transforms: list[str] = []

    def kb_version(self, *, orgid: str = "ECOLI") -> str:
        assert orgid == "ECOLI"
        return "29.6"

    def create_gene_smarttable(
        self,
        *,
        gene_symbols: list[str],
        name: str,
        description: str,
        orgid: str = "ECOLI",
    ) -> tuple[str, bytes]:
        payload = {
            "name": name,
            "description": description,
            "pgdb": orgid,
            "type": "Genes",
            "values": gene_symbols,
        }
        self.created_payloads.append(payload)
        return "biocyc-test-123", json.dumps(
            {
                "id": "biocyc-test-123",
                "login-token": ["session-material"],
            }
        ).encode()

    def add_transform(self, smarttable_id: str, transform_id: str) -> bytes:
        assert smarttable_id == "biocyc-test-123"
        self.transforms.append(transform_id)
        return f"added {transform_id}".encode()

    def add_property(self, smarttable_id: str, property_id: str) -> bytes:
        assert smarttable_id == "biocyc-test-123"
        return f"added {property_id}".encode()

    def get_tsv(self, smarttable_id: str, *, orgid: str = "ECOLI") -> bytes:
        assert smarttable_id == "biocyc-test-123"
        assert orgid == "ECOLI"
        return (
            b"Gene\tGO terms (molecular function)\t"
            b"GO terms (biological process)\tGO terms (cellular component)\n"
            b"cpxR\tGO:0003700 // DNA-binding transcription factor activity\t"
            b"GO:0045892 // negative regulation of transcription\t"
            b"GO:0005829 // cytosol\n"
            b"lexA\tGO:0001217 // DNA-binding transcription repressor activity\t"
            b"GO:0009432 // SOS response; GO:0006974 // DNA damage response\t\n"
        )


def test_parse_smarttable_go_tsv_extracts_go_ids_and_names() -> None:
    rows = parse_smarttable_go_tsv(
        b"Gene\tGO terms (molecular function)\tGO terms (biological process)\n"
        b"cpxR\tGO:0003700 // DNA-binding transcription factor activity\t"
        b"GO:0045892 // negative regulation of transcription\n"
    )

    assert rows == [
        {
            "gene_symbol": "cpxR",
            "go_aspect": "molecular_function",
            "go_id": "GO:0003700",
            "go_name": "",
            "source_column": "GO terms (molecular function)",
        },
        {
            "gene_symbol": "cpxR",
            "go_aspect": "biological_process",
            "go_id": "GO:0045892",
            "go_name": "",
            "source_column": "GO terms (biological process)",
        },
    ]


def test_parse_smarttable_go_tsv_prefers_common_name_over_frame_id() -> None:
    rows = parse_smarttable_go_tsv(
        b"Genes\tCommon-Name\tGO terms (biological process)\n"
        b"EG10533\tlexA\tGO:0009432 // SOS response\n"
    )

    assert rows == [
        {
            "gene_symbol": "lexA",
            "go_aspect": "biological_process",
            "go_id": "GO:0009432",
            "go_name": "",
            "source_column": "GO terms (biological process)",
        }
    ]


def test_biocyc_smarttable_artifact_builder_persists_raw_and_processed_outputs(
    tmp_path: Path,
) -> None:
    _write_network_regulator_gene(
        tmp_path
        / "sources/databases/regulondb/13.0/network_interactions/NetworkRegulatorGene.tsv"
    )
    _write_go_basic_obo(tmp_path)
    client = FakeSmartTableClient()

    manifest = build_biocyc_smarttable_artifacts(tmp_path, client=client)

    output_root = (
        tmp_path
        / "generated/functional_annotations/biocyc/29.6/smarttables/regulator_go_terms"
    )
    annotations = output_root / "processed/regulator_go_terms.tsv"
    coverage = output_root / "processed/regulator_go_coverage.tsv"

    assert manifest["row_counts"]["regulator_go_terms"] == 6
    assert manifest["schema_version"] == "biocyc_smarttable_regulator_go_terms.v2"
    assert manifest["sources"]["biocyc"]["kb_version"] == "29.6"
    assert manifest["sources"]["ontology"]["source_id"] == (
        "gene_ontology_2026_03_25_go_basic_obo"
    )
    assert annotations.exists()
    assert coverage.exists()
    assert (output_root / "raw/create_request.json").exists()
    create_response = json.loads(
        (output_root / "raw/create_response.json").read_text(encoding="utf-8")
    )
    assert create_response == {
        "id": "biocyc-test-123",
        "login-token": "<redacted>",
    }
    assert (output_root / "raw/st_get.tsv").exists()
    assert (output_root / "raw/property_common-name.bin").exists()
    assert client.created_payloads[0]["values"] == ["cpxR", "lexA"]
    assert client.transforms == ["go-mf", "go-bp", "go-cc"]


def test_biocyc_smarttable_get_tsv_sends_orgid() -> None:
    class RecordingClient(BioCycSmartTableClient):
        def __init__(self) -> None:
            super().__init__(
                username="user",
                password="secret",  # pragma: allowlist secret
            )
            self.urls: list[str] = []

        def _request(
            self,
            method: str,
            url: str,
            *,
            data: bytes | None = None,
            content_type: str | None = None,
            authenticated: bool,
        ) -> bytes:
            self.urls.append(url)
            return b"Gene\tGO terms (biological process)\nlexA\tGO:0009432 // SOS response\n"

    client = RecordingClient()

    client.get_tsv("biocyc-test-123", orgid="ECOLI")

    assert client.urls == [
        "https://websvc.biocyc.org/st-get?id=biocyc-test-123&format=tsv&orgid=ECOLI"
    ]


def test_biocyc_smarttable_artifact_builder_fails_without_go_terms(
    tmp_path: Path,
) -> None:
    _write_network_regulator_gene(
        tmp_path
        / "sources/databases/regulondb/13.0/network_interactions/NetworkRegulatorGene.tsv"
    )
    _write_go_basic_obo(tmp_path)

    class EmptyClient(FakeSmartTableClient):
        def get_tsv(self, smarttable_id: str, *, orgid: str = "ECOLI") -> bytes:
            assert orgid == "ECOLI"
            return b"Gene\tGO terms (molecular function)\ncpxR\t\n"

    with pytest.raises(ValueError, match="No GO terms parsed"):
        build_biocyc_smarttable_artifacts(tmp_path, client=EmptyClient())


def test_resolve_biocyc_credentials_rejects_missing_username_without_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BIOCYC_USERNAME", raising=False)
    monkeypatch.delenv("BIOCYC_PASSWORD", raising=False)
    password_file = tmp_path / "biocyc_password.txt"
    password_file.write_text("from-file\n", encoding="utf-8")
    password_file.chmod(0o600)

    with pytest.raises(ValueError, match="BioCyc username is required"):
        resolve_biocyc_credentials(
            username="",
            password_env="BIOCYC_PASSWORD",  # pragma: allowlist secret
            password_file=str(password_file),
            prompt_password=False,
            use_keychain=True,
            keychain_service="fixture",
            keychain_reader=lambda _username, _service: "from-keychain",
        )


def test_resolve_biocyc_credentials_uses_env_username_and_reads_private_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIOCYC_USERNAME", "user@example.org")
    monkeypatch.delenv("BIOCYC_PASSWORD", raising=False)
    password_file = tmp_path / "biocyc_password.txt"
    password_file.write_text("from-file\n", encoding="utf-8")
    password_file.chmod(0o600)

    credentials = resolve_biocyc_credentials(
        username="",
        password_env="BIOCYC_PASSWORD",  # pragma: allowlist secret
        password_file=str(password_file),
        prompt_password=False,
        use_keychain=True,
        keychain_service="fixture",
        keychain_reader=lambda _username, _service: "from-keychain",
    )

    assert credentials.username == "user@example.org"
    assert credentials.password == "from-file"  # pragma: allowlist secret
    assert credentials.source == "password_file"


def test_resolve_biocyc_credentials_rejects_overly_permissive_password_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BIOCYC_PASSWORD", raising=False)
    password_file = tmp_path / "biocyc_password.txt"
    password_file.write_text("from-file\n", encoding="utf-8")
    password_file.chmod(0o644)

    with pytest.raises(ValueError, match="must not be group/world accessible"):
        resolve_biocyc_credentials(
            username="user@example.org",
            password_env="BIOCYC_PASSWORD",  # pragma: allowlist secret
            password_file=str(password_file),
            prompt_password=False,
            use_keychain=False,
            keychain_service="fixture",
        )


def test_resolve_biocyc_credentials_uses_keychain_when_no_explicit_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BIOCYC_PASSWORD", raising=False)

    credentials = resolve_biocyc_credentials(
        username="user@example.org",
        password_env="BIOCYC_PASSWORD",  # pragma: allowlist secret
        password_file="",
        prompt_password=False,
        use_keychain=True,
        keychain_service="fixture",
        keychain_reader=lambda username, service: f"{username}:{service}",
    )

    assert (
        credentials.password == "user@example.org:fixture"  # pragma: allowlist secret
    )
    assert credentials.source == "keychain"


def test_initialize_transient_password_file_creates_empty_private_file(
    tmp_path: Path,
) -> None:
    password_path = initialize_transient_password_file(
        tmp_path / "biocyc_password.transient.txt",
        open_file=False,
    )

    assert password_path.read_text(encoding="utf-8") == ""
    assert stat.S_IMODE(password_path.stat().st_mode) == 0o600


def test_store_biocyc_keychain_password_uses_writer_and_verifies_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "dnadesign_data.functional.biocyc_credentials.read_macos_keychain_password",
        lambda _username, _service: "fixture-password",
    )

    def fake_writer(username: str, service: str, password: str) -> None:
        captured["username"] = username
        captured["service"] = service
        captured["password"] = password

    store_biocyc_keychain_password(
        username="user@example.org",
        password="fixture-password",  # pragma: allowlist secret
        keychain_service="fixture-service",
        writer=fake_writer,
    )

    assert captured == {
        "username": "user@example.org",
        "service": "fixture-service",
        "password": "fixture-password",  # pragma: allowlist secret
    }


def test_biocyc_smarttable_main_can_emit_json_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("BIOCYC_PASSWORD", raising=False)

    exit_code = main(
        [
            "--json-errors",
            "--username",
            "user@example.org",
            "--no-keychain",
        ]
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["type"] == "ValueError"
    assert "No BioCyc password found" in payload["error"]["message"]
