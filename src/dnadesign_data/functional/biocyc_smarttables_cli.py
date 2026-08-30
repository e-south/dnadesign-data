"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/functional/biocyc_smarttables_cli.py

Provides the CLI surface for authenticated BioCyc SmartTable artifacts.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from dnadesign_data.functional.biocyc_client import BioCycSmartTableClient
from dnadesign_data.functional.biocyc_credentials import (
    DEFAULT_KEYCHAIN_SERVICE,
    DEFAULT_TRANSIENT_PASSWORD_PATH,
    initialize_transient_password_file,
    read_private_password_file,
    resolve_biocyc_credentials,
    store_biocyc_keychain_password,
)
from dnadesign_data.functional.biocyc_smarttables import (
    build_biocyc_smarttable_artifacts,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build authenticated BioCyc SmartTable regulator GO artifacts."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Data repository root. Defaults to the current working directory.",
    )
    parser.add_argument("--orgid", default="ECOLI")
    parser.add_argument(
        "--username",
        default=os.environ.get("BIOCYC_USERNAME", ""),
        help=(
            "BioCyc account email. Defaults to BIOCYC_USERNAME and is required "
            "for authenticated requests."
        ),
    )
    parser.add_argument(
        "--password-env",
        default="BIOCYC_PASSWORD",
        help="Environment variable containing the BioCyc password.",
    )
    parser.add_argument(
        "--password-file",
        default=os.environ.get("BIOCYC_PASSWORD_FILE", ""),
        help=(
            "Path to a local password file. The file must not be group/world "
            "accessible. Defaults to BIOCYC_PASSWORD_FILE."
        ),
    )
    parser.add_argument(
        "--prompt-password",
        action="store_true",
        help="Prompt for the BioCyc password without echoing it.",
    )
    parser.add_argument(
        "--keychain-service",
        default=os.environ.get("BIOCYC_KEYCHAIN_SERVICE", DEFAULT_KEYCHAIN_SERVICE),
        help="macOS Keychain generic-password service name.",
    )
    parser.add_argument(
        "--no-keychain",
        action="store_true",
        help="Disable default macOS Keychain password lookup.",
    )
    parser.add_argument(
        "--init-password-file",
        nargs="?",
        const=DEFAULT_TRANSIENT_PASSWORD_PATH,
        default="",
        metavar="PATH",
        help=(
            "Create an empty 0600 transient password file and open it locally. "
            f"Defaults to {DEFAULT_TRANSIENT_PASSWORD_PATH} when no path is given."
        ),
    )
    parser.add_argument(
        "--no-open-password-file",
        action="store_true",
        help="Create --init-password-file without opening it in a desktop editor.",
    )
    parser.add_argument(
        "--store-keychain-from-file",
        default="",
        metavar="PATH",
        help=(
            "Read a private password file and store it in macOS Keychain. "
            "Requires --username or BIOCYC_USERNAME."
        ),
    )
    parser.add_argument(
        "--delete-password-file",
        action="store_true",
        help="Delete the password file after --store-keychain-from-file succeeds.",
    )
    parser.add_argument(
        "--allow-empty-go-terms",
        action="store_true",
        help="Do not fail if the retrieved SmartTable has no GO terms.",
    )
    parser.add_argument(
        "--allow-missing-go-ontology",
        action="store_true",
        help=(
            "Allow SmartTable output without the release-pinned GO ontology used "
            "to name GO IDs."
        ),
    )
    parser.add_argument(
        "--json-errors",
        action="store_true",
        help="Emit runtime errors as machine-readable JSON on stderr.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return _run(args)
    except Exception as exc:
        if args.json_errors:
            print(
                json.dumps(
                    {
                        "error": {
                            "type": type(exc).__name__,
                            "message": str(exc),
                        }
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 1
        raise


def _run(args: argparse.Namespace) -> int:
    if args.init_password_file:
        password_path = initialize_transient_password_file(
            args.init_password_file,
            open_file=not args.no_open_password_file,
        )
        print(
            json.dumps(
                {
                    "created_password_file": str(password_path),
                    "mode": "0600",
                    "next_step": (
                        "Paste the BioCyc password into the file, save it, then run "
                        "with --store-keychain-from-file or --password-file."
                    ),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.store_keychain_from_file:
        username = (
            args.username.strip() or os.environ.get("BIOCYC_USERNAME", "").strip()
        )
        password_path = Path(args.store_keychain_from_file).expanduser()
        password = read_private_password_file(password_path)
        store_biocyc_keychain_password(
            username=username,
            password=password,
            keychain_service=args.keychain_service,
        )
        if args.delete_password_file:
            password_path.unlink()
        print(
            json.dumps(
                {
                    "stored": True,
                    "keychain_service": args.keychain_service,
                    "deleted_password_file": bool(args.delete_password_file),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    credentials = resolve_biocyc_credentials(
        username=args.username,
        password_env=args.password_env,
        password_file=args.password_file,
        prompt_password=args.prompt_password,
        use_keychain=not args.no_keychain,
        keychain_service=args.keychain_service,
    )
    client = BioCycSmartTableClient(
        username=credentials.username,
        password=credentials.password,
    )
    manifest = build_biocyc_smarttable_artifacts(
        args.root,
        client=client,
        orgid=args.orgid,
        allow_empty_go_terms=args.allow_empty_go_terms,
        require_go_ontology=not args.allow_missing_go_ontology,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
