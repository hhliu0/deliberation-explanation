"""Single-key credentials and a fixed-endpoint, non-retrying HTTPS transport."""

import http.client
import json
import os
import socket
import ssl
import stat
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

ENDPOINT = "https://api.deepseek.com/chat/completions"
KEY_NAME = "DEEPSEEK_API_KEY"
MAX_RESPONSE_BYTES = 16 * 1024 * 1024


class RatingError(Exception):
    """An application-controlled error safe to display without credentials."""


class TransportError(RatingError):
    def __init__(
        self,
        code: str,
        message: str,
        uncertain: bool = False,
        raw: Optional[bytes] = None,
    ):
        super().__init__(message)
        self.code = code
        self.uncertain = uncertain
        self.raw = raw


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TransportError("redirect_refused", "DeepSeek redirected the request.")


def load_key(path: Path) -> str:
    """Read one environment value or one literal, owner-only file assignment."""
    value = os.environ.get(KEY_NAME, "").strip()
    if not value:
        descriptor = None
        try:
            descriptor = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise RatingError("The key file must be a regular, non-symlink file.")
            if os.name == "posix" and (
                info.st_mode & 0o077 or info.st_uid != os.getuid()
            ):
                raise RatingError("The key file must be owned by you with mode 600.")
            with os.fdopen(descriptor, encoding="utf-8") as stream:
                descriptor = None
                lines = stream.read().splitlines()
        except FileNotFoundError:
            raise RatingError(
                "Missing DEEPSEEK_API_KEY. Fill ratings.local.env or set the environment variable."
            ) from None
        except (OSError, UnicodeError):
            raise RatingError("Cannot safely read the local key file.") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)
        found = False
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, candidate = line.partition("=")
            if not separator or name.strip() != KEY_NAME or found:
                raise RatingError(
                    "Expected one DEEPSEEK_API_KEY assignment in the key file."
                )
            found = True
            value = candidate.strip()
            if value.startswith(("'", '"')):
                if len(value) < 2 or value[-1] != value[0]:
                    raise RatingError("Unmatched quote in the key file.")
                value = value[1:-1]
    if not value:
        raise RatingError("DEEPSEEK_API_KEY is empty. Fill it locally before running.")
    if any(ord(char) < 33 or ord(char) > 126 for char in value):
        raise RatingError("API keys must be printable ASCII without spaces.")
    return value


def ensure_no_secret(value: Any, key: str) -> None:
    """Block credentials in non-credential data, including decoded JSON strings."""
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str) and key in item:
            raise RatingError("A credential appeared in non-credential data; stopped.")
        if isinstance(item, bytes) and key.encode("ascii") in item:
            raise RatingError("A credential appeared in non-credential data; stopped.")
        if isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, (list, tuple)):
            pending.extend(item)


def complete(payload: Dict[str, Any], key: str) -> bytes:
    """Return raw response bytes for strict validation and credential checks."""
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(
        NoRedirects(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    try:
        with opener.open(request, timeout=180) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        status = error.code
        try:
            raw = error.read(MAX_RESPONSE_BYTES + 1)
        except (OSError, http.client.HTTPException):
            raw = None
        finally:
            error.close()
        messages = {
            400: "DeepSeek rejected the request; check the model and context size.",
            401: "DeepSeek rejected the API key.",
            402: "DeepSeek reported insufficient balance.",
            403: "DeepSeek denied this request.",
            429: "DeepSeek rate limit reached.",
        }
        raise TransportError(
            "http_" + str(status),
            messages.get(status, "DeepSeek returned an HTTP error."),
            uncertain=status >= 500,
            raw=raw,
        ) from None
    except (urllib.error.URLError, OSError, socket.timeout, http.client.HTTPException):
        raise TransportError(
            "network_error",
            "Connection failed or timed out; the remote outcome and charge are unknown.",
            uncertain=True,
        ) from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise TransportError(
            "response_too_large",
            "The response exceeded the transport safety limit; stopped.",
            uncertain=True,
            raw=raw,
        )
    return raw
