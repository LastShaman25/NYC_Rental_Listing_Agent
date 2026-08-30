"""Persist owner-entered configuration into the local ``.env`` file.

The Settings page lets the single local operator store their own LLM API key /
endpoint (owner request 2026-08-29). Settings are pydantic-settings backed by
``.env``, and pipeline jobs run as separate processes that re-read ``.env`` —
so the file is the one durable place a UI-entered value must land.

Rules: the file is rewritten line-by-line so unrelated keys and comments are
preserved; values are never logged; a ``None`` value removes the key. Always
UTF-8 (PS5.1 round-trips have GBK-mangled files before — never edit .env with
shell tools).
"""

from pathlib import Path

_QUOTE_TRIGGERS = (" ", "#", '"', "'")


def _format_line(key: str, value: str) -> str:
    if any(ch in value for ch in _QUOTE_TRIGGERS):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'{key}="{escaped}"'
    return f"{key}={value}"


def update_env_file(path: Path, values: dict[str, str | None]) -> None:
    """Upsert ``values`` into the env file at ``path`` (None deletes the key)."""
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    remaining = dict(values)
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped else None
        if key and not stripped.startswith("#") and key in remaining:
            value = remaining.pop(key)
            if value is not None:
                output.append(_format_line(key, value))
            # None: drop the line entirely.
        else:
            output.append(line)
    for key, value in remaining.items():
        if value is not None:
            output.append(_format_line(key, value))
    path.write_text("\n".join(output) + "\n", encoding="utf-8")
