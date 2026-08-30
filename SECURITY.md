# Security

This is a public repository. Treat every tracked file as publishable.

## Secrets And Credentials

Do not commit:

- passwords, API tokens, cookies, or session material;
- personal account identifiers;
- local credential handoff files;
- `.env` files or local key material;
- machine-local absolute paths.

Authenticated adapters must resolve credentials at runtime from explicit
operator input:

- `--username` or `BIOCYC_USERNAME` for account identity;
- private password file with mode `0600`;
- prompt without echo;
- OS credential store such as macOS Keychain.

Manifests may record that authentication was required, but must not record the
username, password source content, or credential values.

## BioCyc Credential Handoff

Use a transient private file when a password needs to be handed to the tool
without echoing it in the shell:

```bash
uv run dnadesign-data-biocyc-smarttables \
  --init-password-file ~/Desktop/biocyc_password.transient.txt
```

Paste the password into the opened file, save it, then either use it once:

```bash
export BIOCYC_USERNAME="<your BioCyc account email>"
uv run dnadesign-data-biocyc-smarttables \
  --root . \
  --password-file ~/Desktop/biocyc_password.transient.txt
```

or import it into macOS Keychain and delete the transient file:

```bash
export BIOCYC_USERNAME="<your BioCyc account email>"
uv run dnadesign-data-biocyc-smarttables \
  --store-keychain-from-file ~/Desktop/biocyc_password.transient.txt \
  --delete-password-file
```

The Keychain path writes through macOS Security.framework so the password is not
placed in process arguments, then verifies that the stored value can be read
back. BioCyc SmartTable create responses may include session material; the
adapter persists only a sanitized JSON response with that field redacted.

## Network And Egress

Network access should happen only inside explicit CLI adapter commands. Importing
`dnadesign_data` must not contact external services.

Downloaded or service-derived artifacts should retain enough provenance for
review: source URL or service route, release or reported version, hashes where
available, row counts, and schema version.

The public tree contains no literature shelf. Every retained database release
must declare a `redistributable` posture in its release-local `rights.json`.
Private, review-blocked, link-only, and unclassified source payloads remain
outside this repository.

## Review Checklist

Before committing:

```bash
rg -n "password|token|secret|BIOCYC_USERNAME|@.*\\." README.md src tests || true
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run python -m dnadesign_data.devtools.publication_check
uv run python -m dnadesign_data.devtools.public_tree_check
uv run pip-audit --local
git diff --check
```

The grep is a review aid, not a substitute for inspecting the diff.
