"""Minimal DeepSeek transport and local credential loading."""

import json
import os
import socket
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict

ENDPOINT = "https://api.deepseek.com/chat/completions"
KEY_NAMES = {"agent_a": "DEEPSEEK_API_KEY_A", "agent_b": "DEEPSEEK_API_KEY_B"}
MAX_RESPONSE_BYTES = 16 * 1024 * 1024


class DialogueError(Exception):
    """An application-controlled message safe to display without secrets."""


class APIError(DialogueError):
    def __init__(self, code: str, message: str, uncertain: bool = False):
        """Store an API error's code, message, and uncertain-outcome flag."""
        super().__init__(message)
        self.code = code
        self.uncertain = uncertain


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Reject redirects from the API endpoint."""
        raise APIError("redirect_refused", "DeepSeek redirected the request; stopped.")


def load_keys(path: Path) -> Dict[str, str]:
    """Load both API keys, preferring environment values over literal file entries."""
    values = {}
    for name in KEY_NAMES.values():
        value = os.environ.get(name, "").strip()
        if value:
            values[name] = value
    if len(values) < 2 and path.exists():
        try:
            if path.is_symlink() or not path.is_file():
                raise DialogueError("The key file must be a regular, non-symlink file.")
            if os.name == "posix" and path.stat().st_mode & 0o077:
                raise DialogueError(
                    "The key file must be owner-only. Run chmod 600 on your key file."
                )
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise DialogueError("Cannot read the local key file.") from None
        entries = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, value = line.partition("=")
            name, value = name.strip(), value.strip()
            if not separator or name not in KEY_NAMES.values() or name in entries:
                raise DialogueError("Invalid or duplicate assignment in the key file.")
            if value.startswith(("'", '"')):
                if len(value) < 2 or value[-1] != value[0]:
                    raise DialogueError("Unmatched quote in the key file.")
                value = value[1:-1]
            entries[name] = value
        for name, value in entries.items():
            if value and name not in values:
                values[name] = value
    for label, name in KEY_NAMES.items():
        if not values.get(name):
            raise DialogueError(
                "Missing "
                + name
                + ". Fill the local key file or set this environment variable."
            )
        if any(ord(char) < 33 or ord(char) > 126 for char in values[name]):
            raise DialogueError(
                "API keys must contain only printable ASCII without spaces."
            )
    return {agent: values[name] for agent, name in KEY_NAMES.items()}


def ensure_no_keys(value: Any, keys: Dict[str, str]) -> None:
    """Reject nested data containing either agent's API key."""
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            if any(secret in item for secret in keys.values()):
                raise DialogueError(
                    "A credential appeared in non-credential data; stopped without saving it."
                )
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, (list, tuple)):
            pending.extend(item)


def complete(payload: Dict[str, Any], key: str) -> Dict[str, Any]:
    """Send one DeepSeek request and return its decoded JSON response."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
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
        error.close()
        messages = {
            400: "DeepSeek rejected the request; check the model and prompt/context size.",
            401: "DeepSeek rejected the API key for this agent.",
            402: "DeepSeek reported insufficient account balance.",
            403: "DeepSeek denied this request.",
            429: "DeepSeek rate limit reached; start a new run later.",
        }
        raise APIError(
            "http_" + str(status),
            messages.get(
                status, "DeepSeek returned an HTTP error; the run has stopped."
            ),
            uncertain=status >= 500,
        ) from None
    except (urllib.error.URLError, OSError, socket.timeout):
        raise APIError(
            "network_error",
            "The connection failed or timed out. The remote outcome and charge are unknown.",
            uncertain=True,
        ) from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise APIError(
            "response_too_large", "The API response exceeded the local size limit."
        )
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        raise APIError(
            "invalid_json", "DeepSeek returned an unreadable response."
        ) from None
    if not isinstance(result, dict):
        raise APIError(
            "invalid_response", "DeepSeek returned an unexpected response format."
        )
    return result
