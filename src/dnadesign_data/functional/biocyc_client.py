"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/functional/biocyc_client.py

Implements the authenticated BioCyc SmartTable web-service client.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import base64
import http.cookiejar
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

import certifi

BIOCYC_BASE_URL = "https://websvc.biocyc.org"
TRANSFORM_IDS = ("go-mf", "go-bp", "go-cc")
PROPERTY_IDS = ("common-name",)
TRANSFORM_ASPECTS = {
    "go-mf": "molecular_function",
    "go-bp": "biological_process",
    "go-cc": "cellular_component",
}


class BioCycSmartTableClient:
    """Small authenticated client for the BioCyc SmartTable web services."""

    def __init__(
        self,
        *,
        username: str,
        password: str,
        base_url: str = BIOCYC_BASE_URL,
        timeout: int = 120,
    ) -> None:
        if not username:
            raise ValueError("BioCyc username is required")
        if not password:
            raise ValueError("BioCyc password is required")
        self.username = username
        self.password = password
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())
        self._cookie_jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookie_jar),
            urllib.request.HTTPSHandler(context=self._ssl_context),
        )
        self._logged_in = False

    def kb_version(self, *, orgid: str = "ECOLI") -> str:
        url = self._url("/kb-version", {"orgid": orgid})
        payload = self._request("GET", url, authenticated=False)
        data = json.loads(payload.decode("utf-8"))
        version = str(data.get("kb-version", "")).strip()
        if not version:
            raise ValueError("BioCyc kb-version response lacked kb-version")
        return version

    def create_gene_smarttable(
        self,
        *,
        gene_symbols: list[str],
        name: str,
        description: str,
        orgid: str = "ECOLI",
    ) -> tuple[str, bytes]:
        if not gene_symbols:
            raise ValueError("Cannot create a BioCyc SmartTable with no genes")
        payload = {
            "name": name,
            "description": description,
            "pgdb": orgid,
            "type": "Genes",
            "values": gene_symbols,
        }
        url = self._url("/st-create", {"format": "json"})
        response = self._request(
            "PUT",
            url,
            data=json.dumps(payload, sort_keys=True).encode("utf-8"),
            content_type="application/json",
            authenticated=True,
        )
        return _extract_smarttable_id(response), response

    def add_transform(self, smarttable_id: str, transform_id: str) -> bytes:
        if transform_id not in TRANSFORM_IDS:
            raise ValueError(f"Unsupported BioCyc SmartTable transform: {transform_id}")
        url = self._url(
            "/st-transform",
            {"id": smarttable_id, "transformid": transform_id, "index": "0"},
        )
        return self._request("GET", url, authenticated=True)

    def add_property(self, smarttable_id: str, property_id: str) -> bytes:
        if property_id not in PROPERTY_IDS:
            raise ValueError(f"Unsupported BioCyc SmartTable property: {property_id}")
        url = self._url(
            "/st-property",
            {"id": smarttable_id, "propertyid": property_id, "index": "0"},
        )
        return self._request("GET", url, authenticated=True)

    def get_tsv(self, smarttable_id: str, *, orgid: str = "ECOLI") -> bytes:
        url = self._url(
            "/st-get",
            {"id": smarttable_id, "format": "tsv", "orgid": orgid},
        )
        return self._request("GET", url, authenticated=True)

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: bytes | None = None,
        content_type: str | None = None,
        authenticated: bool,
    ) -> bytes:
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        if authenticated:
            self._ensure_session()
            token = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode("ascii")
            headers["Authorization"] = f"Basic {token}"
        request = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"BioCyc request failed with HTTP {exc.code}: {url}"
            ) from exc
        if not payload:
            raise ValueError(f"BioCyc request returned an empty response: {url}")
        return payload

    def _ensure_session(self) -> None:
        if self._logged_in:
            return
        url = self._url("/credentials/login/", {})
        data = urllib.parse.urlencode(
            {"email": self.username, "password": self.password}
        ).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"BioCyc login failed with HTTP {exc.code}: {url}"
            ) from exc
        if not self._cookie_jar:
            raise RuntimeError("BioCyc login succeeded but returned no session cookies")
        self._logged_in = True

    def _url(self, path: str, params: dict[str, str]) -> str:
        return f"{self.base_url}{path}?{urllib.parse.urlencode(params)}"


def _extract_smarttable_id(response: bytes) -> str:
    text = response.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        found = _find_id_in_json(parsed)
        if found:
            return found
    match = re.search(r"biocyc[0-9A-Za-z_-]+", text)
    if match:
        return match.group(0)
    raise ValueError("Could not extract BioCyc SmartTable ID from create response")


def _find_id_in_json(value: object) -> str:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in {"id", "smarttable-id", "smarttable_id"} and isinstance(
                child, str
            ):
                return child
            found = _find_id_in_json(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_id_in_json(child)
            if found:
                return found
    return ""
