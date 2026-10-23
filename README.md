# Retry Sequence Check

`retry-sequence-check` validates a UTF-8 JSON Lines fixture containing normalized retry attempt records. It is an offline, standard-library runtime CLI; it does not execute retries or infer runtime behavior.

## Install and run

Python 3.10 or newer is required. From a fresh virtual environment, install the project without editable mode:

```console
python -m venv .venv
# Activate .venv using the command for your shell, then:
python -m pip install .
retry-sequence-check examples/valid.jsonl
```

Alternatively, run `python -m retry_sequence_check ATTEMPTS.jsonl` after installation. The package has no runtime dependencies.

Each non-empty physical line must be an object with exactly these fields:

```json
{"id":"event-1","operation":"send","attempt":1}
```

`id` is a unique, non-empty string; `operation` is a non-empty string; and `attempt` is an integer from 1 through 1,000,000. Event IDs and `(operation, attempt)` pairs must be unique across the complete file. For each operation, the first observed attempt must be 1 and every later observed attempt must equal the immediately previous observed attempt plus one. Rows from different operations can be interleaved. Rows are checked in file order and are never sorted.

The command emits one JSON object. `valid` exits 0, `sequence_issues` exits 1 and reports the physical line numbers that fail the observed-sequence rule, and `invalid_input` exits 2. Invalid input always emits `{"status":"invalid_input"}` and no diagnostic details, so IDs, operations, values, paths, and parser exceptions are not disclosed. Empty files are valid. Input must be strict UTF-8 JSON Lines; blank records, duplicate JSON keys, non-finite numbers, and lone surrogate values are rejected.

## Limits

The result describes only the normalized sequence in this fixture. It does not establish that a retry occurred, succeeded, was safe, idempotent, timed, or compatible with any provider. It does not assess backoff policies or execute requests. Use synthetic examples and do not place sensitive identifiers in fixtures.

## Development

Install with `python -m pip install . pytest` and run `python -m pytest`. CI covers Python 3.10 and 3.13 on Ubuntu and Windows and also runs the installed command-line acceptance check.
