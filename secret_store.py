import base64
import getpass
import hashlib
import json
import os
import sys
import uuid
from functools import lru_cache
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_SALT: bytes = b"servicenow-developer-panel.secret-store.v1"
KEY_LENGTH: int = 32
NONCE_LENGTH: int = 12
SCRYPT_COST: int = 2 ** 14
SCRYPT_BLOCK_SIZE: int = 8
SCRYPT_PARALLELISM: int = 1
SCRYPT_MAX_MEMORY: int = 64 * 1024 * 1024
MACHINE_ID_PATHS: tuple[str, ...] = ("/etc/machine-id", "/var/lib/dbus/machine-id")
WINDOWS_CRYPTOGRAPHY_KEY: str = "SOFTWARE\\Microsoft\\Cryptography"
WINDOWS_MACHINE_GUID_NAME: str = "MachineGuid"
UNKNOWN_IDENTIFIER: str = "unknown-host"


class SecretError(Exception):
    pass


def encode_details(details: dict[str, str]) -> str:
    payload = json.dumps(details, separators=(",", ":")).encode("utf-8")
    nonce = os.urandom(NONCE_LENGTH)
    cipher = AESGCM(_encryption_key())
    return base64.b64encode(nonce + cipher.encrypt(nonce, payload, None)).decode("ascii")


def decode_details(payload: str) -> dict[str, str]:
    try:
        raw = base64.b64decode(payload.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as error:
        raise SecretError("stored authentication details are malformed") from error
    if len(raw) <= NONCE_LENGTH:
        raise SecretError("stored authentication details are truncated")
    cipher = AESGCM(_encryption_key())
    try:
        plain = cipher.decrypt(raw[:NONCE_LENGTH], raw[NONCE_LENGTH:], None)
    except InvalidTag as error:
        raise SecretError("stored authentication details belong to another machine") from error
    try:
        details = json.loads(plain.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SecretError("stored authentication details are not valid json") from error
    if not isinstance(details, dict):
        raise SecretError("stored authentication details are not an object")
    return {str(key): str(value) for key, value in details.items()}


@lru_cache(maxsize=1)
def _encryption_key() -> bytes:
    seed = "|".join((_machine_identifier(), _user_identifier())).encode("utf-8")
    return hashlib.scrypt(
        seed,
        salt=KEY_SALT,
        n=SCRYPT_COST,
        r=SCRYPT_BLOCK_SIZE,
        p=SCRYPT_PARALLELISM,
        maxmem=SCRYPT_MAX_MEMORY,
        dklen=KEY_LENGTH,
    )


def _machine_identifier() -> str:
    if sys.platform.startswith("win"):
        return _windows_machine_identifier()
    for path in MACHINE_ID_PATHS:
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if value:
            return value
    return _node_identifier()


def _windows_machine_identifier() -> str:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, WINDOWS_CRYPTOGRAPHY_KEY) as key:
            value, _ = winreg.QueryValueEx(key, WINDOWS_MACHINE_GUID_NAME)
    except (ImportError, OSError):
        return _node_identifier()
    return str(value).strip() or _node_identifier()


def _node_identifier() -> str:
    node = uuid.getnode()
    return f"{node:012x}" if node else UNKNOWN_IDENTIFIER


def _user_identifier() -> str:
    try:
        return getpass.getuser()
    except (OSError, KeyError):
        return UNKNOWN_IDENTIFIER
