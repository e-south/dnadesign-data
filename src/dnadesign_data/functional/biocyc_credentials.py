"""
--------------------------------------------------------------------------------
dnadesign-data
dnadesign-data/src/dnadesign_data/functional/biocyc_credentials.py

Resolves runtime credentials for authenticated BioCyc services.

Module Author(s): Eric J. South
--------------------------------------------------------------------------------
"""

from __future__ import annotations

import ctypes
import ctypes.util
import getpass
import os
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

PathLike = str | Path

DEFAULT_KEYCHAIN_SERVICE = "dnadesign-data-biocyc"
DEFAULT_TRANSIENT_PASSWORD_PATH = "~/Desktop/biocyc_password.transient.txt"
ERR_SEC_SUCCESS = 0
ERR_SEC_DUPLICATE_ITEM = -25299
SECURITY_FRAMEWORK_PATH = "/System/Library/Frameworks/Security.framework/Security"
CORE_FOUNDATION_FRAMEWORK_PATH = (
    "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
)


@dataclass(frozen=True)
class BioCycCredentials:
    username: str
    password: str
    source: str


def resolve_biocyc_credentials(
    *,
    username: str,
    password_env: str,
    password_file: str,
    prompt_password: bool,
    use_keychain: bool,
    keychain_service: str,
    keychain_reader: Callable[[str, str], str] | None = None,
) -> BioCycCredentials:
    resolved_username = (
        username.strip() or os.environ.get("BIOCYC_USERNAME", "").strip()
    )
    if not resolved_username:
        raise ValueError(
            "BioCyc username is required. Provide --username or set BIOCYC_USERNAME."
        )

    if password_file:
        password = read_private_password_file(Path(password_file).expanduser())
        if password:
            return BioCycCredentials(resolved_username, password, "password_file")
        raise ValueError(f"BioCyc password file was empty: {password_file}")

    env_password = os.environ.get(password_env, "")
    if env_password:
        return BioCycCredentials(resolved_username, env_password, "environment")

    if prompt_password:
        password = getpass.getpass("BioCyc password: ")
        if not password:
            raise ValueError("BioCyc password prompt returned an empty password")
        return BioCycCredentials(resolved_username, password, "prompt")

    if use_keychain:
        reader = keychain_reader or read_macos_keychain_password
        password = reader(resolved_username, keychain_service)
        if password:
            return BioCycCredentials(resolved_username, password, "keychain")

    raise ValueError(
        "No BioCyc password found. Provide --password-file, set "
        f"{password_env}, use --prompt-password, or add a macOS Keychain item "
        f"with service {keychain_service!r} for the provided account."
    )


def initialize_transient_password_file(
    path: PathLike = DEFAULT_TRANSIENT_PASSWORD_PATH,
    *,
    open_file: bool = True,
) -> Path:
    """Create a local 0600 password handoff file and optionally open it."""

    password_path = Path(path).expanduser()
    password_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(password_path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8"):
        pass
    password_path.chmod(0o600)
    if open_file:
        open_local_file(password_path)
    return password_path


def store_biocyc_keychain_password(
    *,
    username: str,
    password: str,
    keychain_service: str = DEFAULT_KEYCHAIN_SERVICE,
    writer: Callable[[str, str, str], None] | None = None,
) -> None:
    """Store a BioCyc password in macOS Keychain without putting it in argv."""

    if not username.strip():
        raise ValueError(
            "BioCyc username is required. Provide --username or set BIOCYC_USERNAME."
        )
    if not password:
        raise ValueError("BioCyc password is required")
    if not keychain_service.strip():
        raise ValueError("BioCyc Keychain service is required")
    keychain_writer = writer or write_macos_keychain_password
    keychain_writer(username.strip(), keychain_service.strip(), password)

    stored = read_macos_keychain_password(username.strip(), keychain_service.strip())
    if stored != password:
        raise RuntimeError(
            "BioCyc password was not retrievable from macOS Keychain after storage"
        )


def write_macos_keychain_password(username: str, service: str, password: str) -> None:
    """Write a generic password through Security.framework, not process argv."""

    if sys.platform != "darwin":
        raise RuntimeError("macOS Keychain storage requires darwin")
    security_path = ctypes.util.find_library("Security") or SECURITY_FRAMEWORK_PATH
    core_foundation_path = (
        ctypes.util.find_library("CoreFoundation") or CORE_FOUNDATION_FRAMEWORK_PATH
    )
    if not security_path or not core_foundation_path:
        raise RuntimeError("macOS Security and CoreFoundation frameworks are required")

    security = ctypes.CDLL(security_path)
    core_foundation = ctypes.CDLL(core_foundation_path)
    _configure_security_framework_signatures(security, core_foundation)

    service_bytes = service.encode("utf-8")
    username_bytes = username.encode("utf-8")
    password_bytes = password.encode("utf-8")
    item_ref = ctypes.c_void_p()
    status = security.SecKeychainAddGenericPassword(
        None,
        len(service_bytes),
        service_bytes,
        len(username_bytes),
        username_bytes,
        len(password_bytes),
        ctypes.c_char_p(password_bytes),
        ctypes.byref(item_ref),
    )
    if status == ERR_SEC_DUPLICATE_ITEM:
        _modify_macos_keychain_password(
            security,
            core_foundation,
            service_bytes,
            username_bytes,
            password_bytes,
        )
        return
    if status != ERR_SEC_SUCCESS:
        raise RuntimeError(
            f"Could not add BioCyc password to Keychain: OSStatus {status}"
        )
    if item_ref.value:
        core_foundation.CFRelease(item_ref)


def _modify_macos_keychain_password(
    security: ctypes.CDLL,
    core_foundation: ctypes.CDLL,
    service_bytes: bytes,
    username_bytes: bytes,
    password_bytes: bytes,
) -> None:
    password_length = ctypes.c_uint32()
    password_data = ctypes.c_void_p()
    item_ref = ctypes.c_void_p()
    status = security.SecKeychainFindGenericPassword(
        None,
        len(service_bytes),
        service_bytes,
        len(username_bytes),
        username_bytes,
        ctypes.byref(password_length),
        ctypes.byref(password_data),
        ctypes.byref(item_ref),
    )
    if status != ERR_SEC_SUCCESS:
        raise RuntimeError(f"Could not find existing Keychain item: OSStatus {status}")
    try:
        status = security.SecKeychainItemModifyContent(
            item_ref,
            None,
            len(password_bytes),
            ctypes.c_char_p(password_bytes),
        )
        if status != ERR_SEC_SUCCESS:
            raise RuntimeError(f"Could not update Keychain item: OSStatus {status}")
    finally:
        if password_data.value:
            security.SecKeychainItemFreeContent(None, password_data)
        if item_ref.value:
            core_foundation.CFRelease(item_ref)


def _configure_security_framework_signatures(
    security: ctypes.CDLL,
    core_foundation: ctypes.CDLL,
) -> None:
    security.SecKeychainAddGenericPassword.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    security.SecKeychainAddGenericPassword.restype = ctypes.c_int32
    security.SecKeychainFindGenericPassword.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.c_uint32,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    security.SecKeychainFindGenericPassword.restype = ctypes.c_int32
    security.SecKeychainItemModifyContent.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    security.SecKeychainItemModifyContent.restype = ctypes.c_int32
    security.SecKeychainItemFreeContent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    security.SecKeychainItemFreeContent.restype = ctypes.c_int32
    core_foundation.CFRelease.argtypes = [ctypes.c_void_p]
    core_foundation.CFRelease.restype = None


def read_private_password_file(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"BioCyc password file does not exist: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"BioCyc password path is not a file: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise ValueError(
            f"BioCyc password file must not be group/world accessible: {path} "
            f"(mode {mode:o})"
        )
    return path.read_text(encoding="utf-8").strip()


def read_macos_keychain_password(username: str, service: str) -> str:
    if not shutil.which("security"):
        return ""
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-a",
            username,
            "-s",
            service,
            "-w",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def open_local_file(path: Path) -> None:
    if sys.platform != "darwin" or not shutil.which("open"):
        return
    subprocess.run(["open", str(path)], check=False)
