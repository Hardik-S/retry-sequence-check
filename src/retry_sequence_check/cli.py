"""Command line interface for retry-sequence-check."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_HELP = """usage: retry-sequence-check ATTEMPTS.jsonl

Check normalized retry attempt numbers in a UTF-8 JSON Lines fixture.
Each row must contain exactly: id (unique non-empty string), operation
(non-empty string), and attempt (integer from 1 through 1000000).
The checker does not execute retries or infer runtime behavior.
"""


class _InvalidInput(Exception):
    pass


def _reject_constant(_: str) -> None:
    raise _InvalidInput


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidInput
        result[key] = value
    return result


def _validate_unicode(value: Any) -> None:
    # JSON permits escaped lone surrogates in some decoders; they are not valid
    # Unicode scalar values and cannot be safely emitted or compared.
    if isinstance(value, str):
        if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
            raise _InvalidInput
    elif isinstance(value, list):
        for item in value:
            _validate_unicode(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            _validate_unicode(key)
            _validate_unicode(item)


def _read_rows(path: str) -> list[dict[str, Any]]:
    try:
        raw = Path(path).read_bytes()
        source = raw.decode("utf-8", errors="strict")
        # split only on JSON Lines delimiters. str.splitlines() would also
        # treat Unicode separators inside JSON strings as line boundaries.
        lines = re.split(r"\r\n|\r|\n", source)
        if lines[-1] == "":
            lines.pop()  # one optional final LF; empty input remains zero rows
        rows: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        seen_pairs: set[tuple[str, int]] = set()
        for line in lines:
            if not line:
                raise _InvalidInput
            row = json.loads(line, object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
            _validate_unicode(row)
            if not isinstance(row, dict) or set(row) != {"id", "operation", "attempt"}:
                raise _InvalidInput
            event_id, operation, attempt = row["id"], row["operation"], row["attempt"]
            if not isinstance(event_id, str) or not event_id or not isinstance(operation, str) or not operation:
                raise _InvalidInput
            if isinstance(attempt, bool) or not isinstance(attempt, int) or not 1 <= attempt <= 1_000_000:
                raise _InvalidInput
            pair = (operation, attempt)
            if event_id in seen_ids or pair in seen_pairs:
                raise _InvalidInput
            seen_ids.add(event_id)
            seen_pairs.add(pair)
            rows.append(row)
        return rows
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError,
            ValueError, TypeError, _InvalidInput):
        raise _InvalidInput from None


def _result(path: str) -> tuple[dict[str, Any], int]:
    rows = _read_rows(path)
    previous: dict[str, int] = {}
    issues: list[int] = []
    for line_number, row in enumerate(rows, start=1):
        operation = row["operation"]
        attempt = row["attempt"]
        expected = previous.get(operation, 0) + 1
        if attempt != expected:
            issues.append(line_number)
        # Compare each row with the immediately preceding observed attempt,
        # even when that preceding row was itself out of sequence.
        previous[operation] = attempt
    status = "sequence_issues" if issues else "valid"
    return {"status": status, "record_count": len(rows), "issue_lines": issues}, (1 if issues else 0)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args in (["-h"], ["--help"]):
        sys.stdout.write(_HELP)
        return 0
    if len(args) != 1 or args[0].startswith("-"):
        sys.stdout.write('{"status":"invalid_input"}\n')
        return 2
    try:
        payload, code = _result(args[0])
    except _InvalidInput:
        sys.stdout.write('{"status":"invalid_input"}\n')
        return 2
    sys.stdout.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
